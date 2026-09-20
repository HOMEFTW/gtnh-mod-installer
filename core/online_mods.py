"""Wiki repository discovery and GitHub Release downloads into the local library."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
from app_version import APP_VERSION
from utils.helpers import json_file_lock


WIKI_URL = "https://gtnh.huijiwiki.com/wiki/%E5%8F%AF%E6%B7%BB%E5%8A%A0MOD"
WIKI_API = "https://gtnh.huijiwiki.com/api.php"
MAX_DOWNLOAD_SIZE = 512 * 1024 * 1024


class OnlineModError(Exception):
    """An actionable network, release, or library error."""


@dataclass
class OnlineMod:
    name: str
    repository: str
    description: str = ""
    server_required: bool = False
    link_label: str = "GitHub"


def normalize_repository(value):
    value = value.strip()
    if "://" in value:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise OnlineModError("请输入 https://github.com/作者/仓库 或 作者/仓库")
        value = "/".join(parsed.path.strip("/").split("/")[:2])
    value = value.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value):
        raise OnlineModError("GitHub 仓库格式无效，应为 作者/仓库")
    if value.split("/")[1] in (".", ".."):
        raise OnlineModError("GitHub 仓库名称无效")
    return value


class _WikiParser(HTMLParser):
    """Read the Wiki's extra-mod cards, preserving names, notes and link variants."""
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.card = None
        self.link = None
        self.mods = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag in self.VOID_TAGS:
            return
        self.stack.append((tag, classes))
        if "extra-mod" in classes:
            self.card = {"depth": len(self.stack), "name": [], "text": [], "tags": [], "links": []}
        if self.card and tag == "a" and self._inside("extra-mod-links"):
            try:
                repo = normalize_repository(attrs.get("href", ""))
            except OnlineModError:
                return
            self.link = [repo, []]

    def _inside(self, name):
        return any(name in classes for _, classes in self.stack)

    def handle_data(self, data):
        if not self.card or not data.strip():
            return
        text = data.strip()
        self.card["text"].append(text)
        if self._inside("extra-mod-aside-name"):
            self.card["name"].append(text)
        if self._inside("extra-mod-tags"):
            self.card["tags"].append(text)
        if self.link:
            self.link[1].append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.link and self.card:
            self.card["links"].append(self.link)
            self.link = None
        if not self.stack or self.stack[-1][0] != tag:
            return
        if self.card and len(self.stack) == self.card["depth"]:
            for repo, label in self.card["links"]:
                self.mods.append(OnlineMod(
                    name=" / ".join(self.card["name"]) or repo.split("/")[1],
                    repository=repo,
                    description="\n".join(self.card["text"]),
                    server_required="服务端" in self.card["tags"],
                    link_label=" ".join(label) or "GitHub",
                ))
            self.card = None
        self.stack.pop()


def parse_wiki_index(html):
    parser = _WikiParser()
    parser.feed(html)
    unique = {}
    for mod in parser.mods:
        unique.setdefault(mod.repository.lower(), mod)
    if not unique:
        raise OnlineModError("索引未找到 GitHub 模组，Wiki 页面结构可能已变化；可以手动输入仓库。")
    return list(unique.values())


def _atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class OnlineModClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": f"GTNH-Mod-Installer/{APP_VERSION}"})

    def _get(self, url, **kwargs):
        try:
            response = self.session.get(url, timeout=(10, 30), **kwargs)
            if response.status_code in (403, 429):
                response.close()
                raise OnlineModError("服务器拒绝访问或请求额度已用尽，请稍后重试。")
            if response.status_code == 404:
                response.close()
                raise OnlineModError("仓库不存在或尚未发布正式 Release，请检查仓库及发布页面。")
            try:
                response.raise_for_status()
            except requests.RequestException:
                response.close()
                raise
            return response
        except requests.RequestException as exc:
            raise OnlineModError(f"网络请求失败：{exc}") from exc

    def load_index(self, cache_path):
        with self._get(WIKI_API, params={"action": "parse", "page": "可添加MOD",
                                       "prop": "text", "format": "json"}) as response:
            try:
                html = response.json()["parse"]["text"]["*"]
                mods = parse_wiki_index(html)
            except (ValueError, KeyError, TypeError) as exc:
                raise OnlineModError("Wiki 返回的数据格式不正确，可以手动输入 GitHub 仓库。") from exc
        _atomic_json(cache_path, [asdict(mod) for mod in mods])
        return mods

    @staticmethod
    def cached_index(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as stream:
                mods = [OnlineMod(**item) for item in json.load(stream)]
            for mod in mods:
                mod.repository = normalize_repository(mod.repository)
            return mods
        except (OSError, ValueError, TypeError, OnlineModError):
            return []

    def latest_release(self, repository):
        repository = normalize_repository(repository)
        with self._get(f"https://api.github.com/repos/{repository}/releases/latest",
                       headers={"Accept": "application/vnd.github+json"}) as response:
            release = response.json()
        if release.get("draft") or release.get("prerelease"):
            raise OnlineModError("该 Release 不是正式版本。")
        assets = [asset for asset in release.get("assets", [])
                  if asset.get("name", "").lower().endswith(".jar")
                  and not re.search(r"(?:^|[-_.])(sources?|javadoc|dev|deobf)(?:[-_.]|$)",
                                    asset["name"], re.I)]
        if not assets:
            raise OnlineModError("最新正式 Release 没有可安装的 JAR 附件，请查看发布页面。")
        return {"tag": release.get("tag_name", ""), "assets": assets,
                "url": f"https://github.com/{repository}/releases/latest"}

    def download(self, mod, release, asset, content_base, server_required=None, progress=None):
        """Stage and verify a JAR, then register it without replacing existing resources."""
        name = asset["name"]
        if (not name.lower().endswith(".jar") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or name.rstrip(". ") != name or name.split(".")[0].upper() in
                {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}):
            raise OnlineModError("Release 附件文件名无效。")
        repository = normalize_repository(mod.repository)
        url = asset.get("browser_download_url", "")
        parsed = urlparse(url)
        prefix = f"/{repository}/releases/download/".lower()
        if (parsed.scheme != "https" or parsed.netloc.lower() != "github.com"
                or not parsed.path.lower().startswith(prefix)):
            raise OnlineModError("附件下载地址不是该仓库的 GitHub Release 地址。")
        expected_size = asset.get("size", 0)
        if not isinstance(expected_size, int) or not 0 < expected_size <= MAX_DOWNLOAD_SIZE:
            raise OnlineModError("附件大小无效或超过 512 MB 限制。")
        base = Path(content_base)
        mods_dir = base / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        destination = mods_dir / name
        if destination.exists():
            raise OnlineModError("资源库已有同名文件，请直接使用现有资源，或先在资源编辑器中处理。")
        metadata_path = base / "resources.json"
        # Never silently replace unreadable metadata with an empty library.
        if metadata_path.exists():
            with metadata_path.open(encoding="utf-8") as stream:
                metadata = json.load(stream)
        else:
            metadata = {}
        if not isinstance(metadata, dict) or not isinstance(metadata.get("mods", []), list):
            raise OnlineModError("resources.json 格式无效，请先修复资源元数据。")
        if any(item.get("filename") == name for item in metadata.get("mods", [])):
            raise OnlineModError("资源元数据中已有同名附件，请先在资源编辑器中处理。")
        fd, temporary = tempfile.mkstemp(dir=mods_dir, suffix=".part")
        published = False
        try:
            digest = hashlib.sha256()
            downloaded = 0
            with os.fdopen(fd, "wb") as stream, self._get(url, stream=True) as response:
                for chunk in response.iter_content(chunk_size=128 * 1024):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > expected_size:
                        raise OnlineModError("下载大小超过 Release 标注大小，已丢弃文件。")
                    stream.write(chunk)
                    digest.update(chunk)
                    if progress:
                        progress(downloaded, expected_size)
            if downloaded != expected_size:
                raise OnlineModError("下载不完整，已丢弃文件，请重试。")
            expected_digest = asset.get("digest")
            if expected_digest and expected_digest.startswith("sha256:"):
                if digest.hexdigest() != expected_digest[7:]:
                    raise OnlineModError("SHA-256 校验失败，已丢弃文件。")
            if not zipfile.is_zipfile(temporary):
                raise OnlineModError("下载的附件不是有效 JAR 文件，已丢弃文件。")
            with zipfile.ZipFile(temporary) as archive:
                if not archive.namelist():
                    raise OnlineModError("下载的 JAR 内容为空。")
            entry = {"id": f"github:{repository.lower()}:{name}", "name": mod.name,
                     "filename": name, "version": release["tag"], "mc_version": "",
                     "description": f"{mod.description}\n来源：https://github.com/{repository}\n"
                                    "兼容性请查看 Wiki 与 Release 说明；旧版需卸载后再安装。",
                     "server_required": mod.server_required if server_required is None else server_required,
                     "github_repository": repository,
                     "download": {"name": name, "url": url, "size": downloaded,
                                  "digest": "sha256:" + digest.hexdigest()}}
            with json_file_lock(metadata_path):
                # Re-read after the network operation; another instance may have saved meanwhile.
                if metadata_path.exists():
                    with metadata_path.open(encoding="utf-8") as stream:
                        metadata = json.load(stream)
                else:
                    metadata = {}
                if not isinstance(metadata, dict) or not isinstance(metadata.get("mods", []), list):
                    raise OnlineModError("resources.json 格式无效，未导入下载文件。")
                if any(item.get("filename", "").casefold() == name.casefold()
                       for item in metadata.get("mods", [])):
                    raise OnlineModError("下载期间其他操作已添加同名资源，请刷新后重试。")
                metadata.setdefault("mods", []).append(entry)
                with destination.open("xb") as output, open(temporary, "rb") as source:
                    published = True
                    shutil.copyfileobj(source, output)
                _atomic_json(metadata_path, metadata)
            return str(destination)
        except requests.RequestException as exc:
            raise OnlineModError(f"下载中断：{exc}") from exc
        except Exception:
            if published:
                destination.unlink(missing_ok=True)
            raise
        finally:
            Path(temporary).unlink(missing_ok=True)
