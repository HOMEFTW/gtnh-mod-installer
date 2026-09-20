"""Official client archives and Wiki resource-pack discovery."""
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote, quote
from core.online_mods import OnlineModClient, OnlineModError, WIKI_API, _atomic_json
from utils.helpers import json_file_lock

GAME_URL = 'https://www.gtnewhorizons.com/version-history/'
PACK_URL = 'https://gtnh.huijiwiki.com/wiki/资源包与光影'

@dataclass
class DownloadEntry:
    name: str
    url: str
    kind: str
    description: str = ''
    preview: bool = False

class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.rows = []
        self.row = None
        self.cell = None
        self.anchor = None
        self.shaders = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == '光影': self.shaders = True
        if tag == 'tr': self.row = []
        if tag == 'td' and self.row is not None: self.cell = [[], []]
        if tag == 'a': self.anchor = [attrs.get('href', ''), []]

    def handle_data(self, data):
        if self.cell is not None: self.cell[0].append(data)
        if self.anchor is not None: self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            link = (self.anchor[0], ''.join(self.anchor[1]).strip())
            self.links.append(link)
            if self.cell is not None: self.cell[1].append(link)
            self.anchor = None
        if tag == 'td' and self.cell is not None:
            self.row.append((' '.join(''.join(self.cell[0]).split()), self.cell[1]))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            if not self.shaders: self.rows.append(self.row)
            self.row = None


def parse_games(html):
    parser = IndexParser(); parser.feed(html)
    entries = {}
    for url, label in parser.links:
        url = urljoin(GAME_URL, url)
        p = urlparse(url)
        if p.scheme != 'https' or p.netloc != 'downloads.gtnewhorizons.com': continue
        if not p.path.lower().endswith('.zip'): continue
        if not p.path.startswith(('/Multi_mc_downloads/', '/ClientPacks/')): continue
        name = unquote(p.path.rsplit('/', 1)[-1])
        kind = 'MultiMC / Prism' if '/Multi_mc_downloads/' in p.path else '客户端 ZIP'
        entries.setdefault(url, DownloadEntry(name, url, kind, label,
                           bool(re.search(r'beta|alpha|rc[-_\d]|/betas/', p.path, re.I))))
    if not entries: raise OnlineModError('官网未发现客户端 ZIP，请打开索引页面检查。')
    return list(entries.values())


def parse_packs(html):
    parser = IndexParser(); parser.feed(html)
    entries = {}
    for row in parser.rows:
        if len(row) < 4 or not row[1][0]: continue
        # Only links from the table download column, not dependencies in descriptions.
        links = row[-1][1]
        for url, label in links:
            if urlparse(url).scheme != 'https': continue
            if label.lower() in ('源码', 'source', '原地址') and len(links) > 1: continue
            entries.setdefault((row[1][0], url), DownloadEntry(row[1][0], url, '资源包',
                '\n'.join(cell[0] for cell in row[2:])))
    if not entries: raise OnlineModError('Wiki 未发现资源包下载链接，请打开索引页面检查。')
    return list(entries.values())


class DownloadClient(OnlineModClient):
    def load_entries(self, game):
        if game:
            with self._get(GAME_URL) as response: return parse_games(response.text)
        with self._get(WIKI_API, params={'action':'parse','page':'资源包与光影','prop':'text','format':'json'}) as response:
            return parse_packs(response.json()['parse']['text']['*'])

    def assets(self, entry):
        p = urlparse(entry.url)
        if p.scheme != 'https': raise OnlineModError('仅支持 HTTPS 下载。')
        if p.path.lower().endswith('.zip'):
            return [{'name':unquote(p.path.rsplit('/',1)[-1]), 'url':entry.url, 'size':0}]
        if p.netloc != 'github.com': return []
        parts = p.path.strip('/').split('/')
        if len(parts) < 2: return []
        repo = '/'.join(parts[:2])
        endpoint = 'latest'
        if len(parts) >= 5 and parts[2:4] == ['releases','tag']:
            endpoint = 'tags/' + quote(unquote('/'.join(parts[4:])), safe='')
        with self._get(f'https://api.github.com/repos/{repo}/releases/{endpoint}') as response:
            release = response.json()
        return [{'name':a['name'], 'url':a['browser_download_url'], 'size':a.get('size',0),
                 'digest':a.get('digest')} for a in release.get('assets', [])
                if a.get('name','').lower().endswith('.zip')]

    def download_zip(self, asset, destination, cancel, progress, resource=False, extension='.zip'):
        """Stream to a temporary file, validate, publish exclusively; never extract."""
        name = asset['name']
        if (extension not in ('.zip', '.jar') or not name.lower().endswith(extension) or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.rstrip('. ') != name or name.split('.')[0].upper() in
            {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}):
            raise OnlineModError('下载文件名无效。')
        if urlparse(asset['url']).scheme != 'https': raise OnlineModError('仅支持 HTTPS 下载。')
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name
        if target.exists(): raise OnlineModError('同名文件已存在，未覆盖。')
        fd, temporary = tempfile.mkstemp(dir=destination, suffix='.part')
        published = False
        limit = (1024 if resource else 8192) * 1024 * 1024
        try:
            import hashlib
            digest = hashlib.sha256()
            with os.fdopen(fd,'wb') as stream, self._get(asset['url'], stream=True, headers={'Accept-Encoding':'identity'}) as response:
                total = asset.get('size') or int(response.headers.get('Content-Length') or 0)
                if total > limit: raise OnlineModError('文件超过下载大小限制。')
                done = 0
                for chunk in response.iter_content(256*1024):
                    if cancel.is_set(): raise OnlineModError('下载已取消。')
                    if not chunk: continue
                    done += len(chunk)
                    if done > limit or (total and done > total): raise OnlineModError('下载大小异常。')
                    stream.write(chunk); digest.update(chunk); progress(done,total)
                if total and done != total: raise OnlineModError('下载不完整，请重试。')
            if cancel.is_set(): raise OnlineModError('下载已取消。')
            if asset.get('digest', '') and asset['digest'].startswith('sha256:'):
                if digest.hexdigest() != asset['digest'][7:]: raise OnlineModError('SHA-256 校验失败。')
            with zipfile.ZipFile(temporary) as archive:
                if not archive.namelist(): raise OnlineModError('ZIP 内容为空。')
                if resource and 'pack.mcmeta' not in archive.namelist():
                    raise OnlineModError('ZIP 根目录没有 pack.mcmeta，不能直接作为资源包安装，请查看发布页。')
            with target.open('xb') as output, open(temporary,'rb') as source:
                published = True
                shutil.copyfileobj(source,output)
            return str(target)
        except Exception:
            if published: target.unlink(missing_ok=True)
            raise
        finally:
            Path(temporary).unlink(missing_ok=True)

    def download_pack(self, entry, asset, base, cancel, progress):
        base = Path(base)
        # Metadata lock covers publication so failed imports cannot leave untracked files.
        metadata_path = base / 'resources.json'
        base.mkdir(parents=True, exist_ok=True)
        with json_file_lock(metadata_path):
            metadata = json.loads(metadata_path.read_text(encoding='utf8')) if metadata_path.exists() else {}
            if not isinstance(metadata,dict) or not isinstance(metadata.get('resourcepacks',[]),list):
                raise OnlineModError('资源库元数据格式无效。')
            if any(x.get('filename','').casefold() == asset['name'].casefold() for x in metadata.get('resourcepacks',[])):
                raise OnlineModError('资源库已有同名资源包。')
            path = self.download_zip(asset,base/'resourcepacks',cancel,progress,resource=True)
            try:
                metadata.setdefault('resourcepacks',[]).append({'id':'download:'+asset['name'], 'name':entry.name,
                    'filename':asset['name'], 'version':'', 'description':entry.description+'\n来源：'+entry.url,
                    'server_required':False, 'download':artifact_source(path, asset)})
                _atomic_json(metadata_path,metadata)
            except Exception:
                Path(path).unlink(missing_ok=True)
                raise
        return path


def artifact_source(path, asset):
    """Persist the exact downloaded bytes, not a moving latest-release URL."""
    import hashlib
    with open(path, 'rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'name': Path(path).name, 'url': asset['url'],
            'size': Path(path).stat().st_size, 'digest': 'sha256:' + digest}
