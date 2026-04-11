"""
Helper functions for GTNH Mod Installer
"""
import json
import os
import shutil
import sys
from typing import Any, Dict, Optional


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
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
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


def init_external_content():
    """Initialize external Addcontent folder on first run"""
    external_dir = get_external_content_dir()

    # If external already exists, nothing to do
    if os.path.exists(external_dir):
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

    return external_dir


def get_data_dir() -> str:
    """Get data directory"""
    return os.path.join(get_app_dir(), 'data')


def get_resources_dir() -> str:
    """Get resources directory"""
    return os.path.join(get_app_dir(), 'resources')


def ensure_dir(path: str) -> bool:
    """Ensure directory exists, create if not"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False
