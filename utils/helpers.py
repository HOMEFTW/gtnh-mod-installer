"""
Helper functions for GTNH Mod Installer
"""
import json
import os
import shutil
import sys
import tempfile
import ntpath
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

CONTENT_SUBDIRS = ("scripts", "resourcepacks", "shaderpacks", "serverutilities", "mods", "fonts", "configs")


def safe_child_path(base, relative):
    """Reject absolute/traversing paths, including Windows paths in archives."""
    relative = str(relative).replace('\\', '/')
    if (not relative or ntpath.splitdrive(relative)[0] or relative.startswith('/')
            or '..' in relative.split('/') or ':' in relative):
        raise ValueError(f"不安全的相对路径: {relative}")
    root = Path(base).resolve()
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"路径超出目标目录: {relative}")
    return str(target)


@contextmanager
def json_file_lock(path):
    """Coordinate app instances using a stable sibling lock file (never unlink it)."""
    lock_path = Path(str(path) + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as stream:
        # Windows supports locking beyond EOF; no initialization write can race the lock.
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def staged_resource_update(source, destination, remove_paths):
    """Stage new bytes before moving old files; roll back if metadata commit fails."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, stage = tempfile.mkstemp(dir=destination.parent, suffix='.part')
    os.close(fd)
    backups = []
    published = False
    committed = False
    try:
        shutil.copy2(source, stage)
        seen = set()
        for path in [*remove_paths, destination]:
            path = Path(path)
            key = os.path.normcase(str(path.resolve()))
            if key in seen or not path.exists():
                continue
            seen.add(key)
            fd, backup = tempfile.mkstemp(dir=path.parent, suffix='.rollback')
            os.close(fd)
            os.unlink(backup)
            os.replace(path, backup)
            backups.append((path, Path(backup)))
        os.replace(stage, destination)
        published = True
        yield
        committed = True
    finally:
        if not committed:
            if published:
                destination.unlink(missing_ok=True)
            for path, backup in reversed(backups):
                os.replace(backup, path)
        Path(stage).unlink(missing_ok=True)
        if committed:
            for _, backup in backups:
                # A cleanup failure must not roll back files after metadata was committed.
                try:
                    if backup.is_dir():
                        shutil.rmtree(backup)
                    else:
                        backup.unlink(missing_ok=True)
                except OSError:
                    pass


def load_json(file_path: str) -> Optional[Dict[str, Any]]:
    """Load JSON file and return dict, or None if file doesn't exist"""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading JSON file {file_path}: {e}")
        return None


def save_json(file_path: str, data: Dict[str, Any]) -> bool:
    """Save dict to JSON file"""
    try:
        with json_file_lock(file_path):
            atomic_json(file_path, data)
        return True
    except IOError as e:
        print(f"Error saving JSON file {file_path}: {e}")
        return False


def is_frozen() -> bool:
    """Check if running as compiled exe (PyInstaller)"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_exe_dir() -> str:
    """Get the directory where the exe is located"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_dir() -> str:
    """Get application directory (for config files)"""
    if is_frozen():
        # When frozen, config files go in exe directory
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_bundled_content_dir() -> Optional[str]:
    """Get the bundled Addcontent directory inside the exe (if frozen)"""
    if is_frozen():
        # PyInstaller bundles files in _MEIPASS
        bundled = os.path.join(sys._MEIPASS, 'Addcontent')
        if os.path.exists(bundled):
            return bundled
    return None


def get_external_content_dir() -> str:
    """Get the external Addcontent directory (next to exe)"""
    return os.path.join(get_exe_dir(), 'Addcontent')


def ensure_content_version_directories(content_dir: str):
    """Ensure each GTNH version directory contains the expected resource folders."""
    if not os.path.exists(content_dir):
        return

    for item in os.listdir(content_dir):
        version_dir = os.path.join(content_dir, item)
        if not os.path.isdir(version_dir):
            continue

        for subdir in CONTENT_SUBDIRS:
            os.makedirs(os.path.join(version_dir, subdir), exist_ok=True)


def init_external_content():
    """Initialize external Addcontent folder on first run"""
    external_dir = get_external_content_dir()

    # If external already exists, nothing to do
    if os.path.exists(external_dir):
        ensure_content_version_directories(external_dir)
        return external_dir

    # If frozen and bundled content exists, extract it
    bundled_dir = get_bundled_content_dir()
    if bundled_dir and os.path.exists(bundled_dir):
        print(f"首次运行，正在解压资源文件到: {external_dir}")
        shutil.copytree(bundled_dir, external_dir)
        print("资源文件解压完成")
    else:
        # Create empty structure
        os.makedirs(external_dir, exist_ok=True)
        print(f"已创建资源目录: {external_dir}")

    ensure_content_version_directories(external_dir)
    return external_dir
