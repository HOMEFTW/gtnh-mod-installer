"""Versioned, reproducible installation manifests and staged client installation."""
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from core.downloads import DownloadClient, artifact_source
from core.installer import Installer, Resource, ResourceType
from core.minecraft import MinecraftPath
from utils.helpers import atomic_json, safe_child_path

CLIENT_RECEIPT = 'gtnh_installer_data/client-source.json'


def check_cancel(cancel):
    if cancel.is_set():
        raise ValueError('安装已取消。')


def file_digest(path):
    with open(path, 'rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_source(source, extension, checksum=True):
    if not isinstance(source, dict):
        raise ValueError('下载来源必须是对象。')
    name = source.get('name', '')
    if (not isinstance(name, str) or not name.lower().endswith(extension)
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.rstrip('. ') != name
            or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',
                *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}):
        raise ValueError('清单中的下载文件名无效。')
    url = source.get('url')
    if not isinstance(url,str): raise ValueError('清单缺少下载地址。')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('清单仅支持不含凭据的 HTTPS 下载链接。')
    digest = source.get('digest')
    if checksum or digest:
        if not isinstance(digest,str) or not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest):
            raise ValueError('清单缺少有效 SHA-256 校验信息。')
    size = source.get('size', 0)
    if not isinstance(size,int) or isinstance(size,bool) or size < 0:
        raise ValueError('清单文件大小无效。')
    return dict(source)


def validate_manifest(data):
    if not isinstance(data,dict) or data.get('version') not in ('1.0','2.0'):
        raise ValueError('不支持的安装清单版本。')
    version = data.get('gtnh_version','')
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',version) or version in ('.','..'):
        raise ValueError('清单中的 GTNH 资源版本无效。')
    resources = data.get('resources')
    if not isinstance(resources,dict): raise ValueError('清单资源列表无效。')
    result = dict(data); result['resources'] = {}
    total = 0
    for kind, entries in resources.items():
        ResourceType(kind)
        if not isinstance(entries,list): raise ValueError('清单资源分类必须为数组。')
        normalized = []
        seen = set()
        filenames = set()
        for entry in entries:
            if data['version']=='1.0' and isinstance(entry,str): entry={'id':entry,'install_side':'both'}
            if not isinstance(entry,dict) or not isinstance(entry.get('id'),str) or not entry['id']:
                raise ValueError('清单资源缺少 ID。')
            if entry['id'] in seen: raise ValueError('清单有重复资源 ID。')
            seen.add(entry['id'])
            item=dict(entry)
            for field in ('name', 'version', 'description', 'filename'):
                if field in item and not isinstance(item[field], str):
                    raise ValueError('清单资源字段类型无效：' + field)
            if 'server_required' in item and not isinstance(item['server_required'], bool):
                raise ValueError('清单服务端标记必须为布尔值。')
            filename = item.get('filename')
            if filename:
                if filename.casefold() in filenames:
                    raise ValueError('清单有重复的目标文件名。')
                filenames.add(filename.casefold())
            if item.get('install_side','client') not in ('client','server','both'):
                raise ValueError('清单安装位置无效。')
            source=item.get('download')
            if source:
                if kind not in ('mods','resourcepacks'):
                    raise ValueError('仅模组和资源包支持清单自动下载。')
                item['download']=validate_source(source,'.jar' if kind=='mods' else '.zip')
                if item.get('filename') != source['name']: raise ValueError('清单文件名与下载来源不匹配。')
            normalized.append(item)
        result['resources'][kind]=normalized
        total += len(normalized)
    if total>5000: raise ValueError('清单资源数量过多。')
    if result.get('client'):
        source=validate_source(result['client'],'.zip')
        p=urlparse(source['url'])
        if p.netloc != 'downloads.gtnewhorizons.com' or not p.path.startswith(('/Multi_mc_downloads/','/ClientPacks/')):
            raise ValueError('客户端来源必须是 GTNH 官方客户端下载地址。')
        result['client']=source
    return result


def read_manifest(path):
    if Path(path).stat().st_size>8*1024*1024: raise ValueError('清单文件过大。')
    return validate_manifest(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def export_manifest(installer):
    """Export installed records, including exact sources that still match installed bytes."""
    installer.refresh_installed_cache()
    result={'version':'2.0','created':datetime.now().isoformat(),
            'gtnh_version':installer.gtnh_version,'resources':{}}
    receipt=Path(installer.mc_path.mc_path)/CLIENT_RECEIPT
    if receipt.exists(): result['client']=json.loads(receipt.read_text(encoding='utf8'))
    for kind in ResourceType:
        grouped={}
        for side, records, mc in [('client',installer._load_client_installed(),installer.mc_path),
                                  ('server',installer._load_server_installed(),installer.server_mc_path)]:
            for raw in records.get(kind.value,[]):
                rid=installer._entry_id(raw)
                resource=installer.get_resource_by_id(rid,kind)
                item=dict(raw) if isinstance(raw,dict) else {'id':rid}
                if resource and not item.get('filename'): item.update(filename=resource.filename,name=resource.name)
                item.setdefault('name',rid)
                source=item.get('download') or (resource.download if resource and resource.filename==item.get('filename') else None)
                filename=item.get('filename')
                dest=installer._get_dest_dir(kind,mc) if mc else None
                installed=Path(safe_child_path(dest,filename)) if dest and filename else None
                if installed and installed.is_file():
                    item['digest']=file_digest(installed)
                if source and item.get('digest') != source.get('digest'):
                    source=None  # Locally edited bytes cannot be reproduced from the original URL.
                item['download']=source
                item['install_side']=side
                if rid in grouped:
                    previous=grouped[rid]
                    if previous.get('filename')!=item.get('filename') or previous.get('digest')!=item.get('digest'):
                        raise ValueError(f'双端资源版本不同，无法合并导出：{item["name"]}')
                    previous['install_side']='both'
                else: grouped[rid]=item
        result['resources'][kind.value]=list(grouped.values())
    return validate_manifest(result)


def extract_client(archive_path, destination, cancel, report):
    """Reject traversal, symlinks and zip bombs before extracting into a private stage."""
    with zipfile.ZipFile(archive_path) as archive:
        infos=archive.infolist()
        if len(infos)>200000 or sum(i.file_size for i in infos)>32*1024**3:
            raise ValueError('客户端解压体积或文件数量超过限制。')
        targets=[]; seen=set()
        for info in infos:
            name=info.filename.replace('\\','/')
            parts=name.rstrip('/').split('/')
            if any(not p or p in ('.','..') or re.search(r'[<>:"|?*\x00-\x1f]',p) or p.rstrip('. ')!=p
                   or p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for p in parts):
                raise ValueError('客户端 ZIP 含不安全路径。')
            if stat.S_ISLNK(info.external_attr >> 16): raise ValueError('客户端 ZIP 不允许符号链接。')
            target=Path(safe_child_path(str(destination),name.rstrip('/')))
            key=str(target).casefold()
            if key in seen: raise ValueError('客户端 ZIP 含重复路径。')
            seen.add(key); targets.append((info,target))
        for index,(info,target) in enumerate(targets):
            check_cancel(cancel)
            if info.is_dir(): target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,target.open('xb') as output:
                    while chunk:=source.read(1024*1024):
                        check_cancel(cancel);output.write(chunk)
            if index%100==0:report(f'解压客户端：{index+1}/{len(targets)}')
    candidates=[p.parent for p in Path(destination).rglob('mods') if p.is_dir()]
    if len(candidates)!=1: raise ValueError('无法唯一识别客户端 mods 目录，未安装。')
    return candidates[0]


class ManifestInstaller:
    def __init__(self, client=None): self.client=client or DownloadClient()

    def install(self,data,target,library,cancel,report,server=None):
        data=validate_manifest(data)
        target=Path(target).resolve()
        if data.get('client'):
            if target.exists() and (not target.is_dir() or any(target.iterdir())):
                raise ValueError('完整整合包须安装到空目录，不能覆盖现有游戏。')
            if server: raise ValueError('完整客户端清单请先安装客户端，再单独处理服务端。')
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.gtnh-install-',dir=target.parent) as temp:
                stage=Path(temp)/'instance';stage.mkdir()
                report('正在下载客户端…')
                archive=self.client.download_zip(data['client'],Path(temp)/'downloads',cancel,
                    lambda done,total:report(f'客户端下载：{done/1048576:.1f} MB / {total/1048576:.1f} MB'))
                mc=extract_client(archive,stage,cancel,report)
                atomic_json(mc/CLIENT_RECEIPT,artifact_source(archive,data['client']))
                self._install_resources(data,mc,library,Path(temp)/'resources',cancel,report,None)
                relative=mc.relative_to(stage)
                check_cancel(cancel)
                if target.exists(): target.rmdir()  # Fails if anything appeared while downloading.
                try:os.rename(stage,target)
                except Exception:
                    target.mkdir(exist_ok=True)
                    raise
                return str(target/relative)
        if not target.is_dir(): raise ValueError('请先选择现有客户端目录。')
        with tempfile.TemporaryDirectory(prefix='gtnh-manifest-') as temp:
            self._install_resources(data,target,library,Path(temp),cancel,report,server)
        return str(target)

    def _install_resources(self,data,mc,library,stage,cancel,report,server):
        installer=Installer(MinecraftPath(str(mc)),data['gtnh_version'])
        installer._content_base=str(library)
        if server:installer.set_server_path(server)
        prepared=[]
        for kind,entries in data['resources'].items():
            for entry in entries:
                check_cancel(cancel)
                side=entry.get('install_side','client')
                if side=='server' and not server: raise ValueError('清单包含仅服务端资源，请选择服务端目录。')
                if side=='both' and not server: side='client'
                resource=installer.get_resource_by_id(entry['id'],ResourceType(kind))
                source=entry.get('download')
                if source:
                    # Fetch pinned bytes, independent of the recipient's current library or latest release.
                    folder=stage/str(len(prepared))
                    report('下载：'+entry.get('name',entry['id']))
                    path=self.client.download_zip(source,folder,cancel,
                        lambda done,total:report(f'{source["name"]}：{done/1048576:.1f} MB / {total/1048576:.1f} MB'),
                        resource=kind=='resourcepacks',extension='.jar' if kind=='mods' else '.zip')
                    resource=Resource(id=entry['id'],name=entry.get('name',entry['id']),filename=source['name'],
                        source_path=path,resource_type=ResourceType(kind),version=entry.get('version',''),
                        description=entry.get('description',''),server_required=entry.get('server_required',False),download=source)
                elif not resource:
                    raise ValueError('本地资源缺失且清单没有下载链接：'+entry.get('name',entry['id']))
                elif entry.get('digest') and (not Path(resource.source_path).is_file() or file_digest(resource.source_path)!=entry['digest']):
                    raise ValueError('本地资源与清单校验不一致：'+resource.name)
                prepared.append((resource,side))
        # All downloads and local requirements have succeeded before modifying existing game files.
        for resource,side in prepared:
            check_cancel(cancel);report('安装：'+resource.name)
            ok,message=installer.install_resource(resource,install_side=side)
            if not ok: raise ValueError(f'{resource.name}：{message}')

    def install_client(self,asset,target,cancel,report):
        """First installation has no manifest checksum yet; record one from downloaded bytes."""
        validate_source(asset,'.zip',checksum=False)
        p=urlparse(asset['url'])
        if p.netloc!='downloads.gtnewhorizons.com' or not p.path.startswith(('/Multi_mc_downloads/','/ClientPacks/')):
            raise ValueError('请选择官方客户端 ZIP。')
        target=Path(target).resolve()
        if target.exists() and (not target.is_dir() or any(target.iterdir())): raise ValueError('请选择空目录安装客户端。')
        target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.gtnh-client-',dir=target.parent) as temp:
            report('正在下载客户端…')
            archive=self.client.download_zip(asset,Path(temp)/'download',cancel,
                lambda done,total:report(f'客户端下载：{done/1048576:.1f} MB / {total/1048576:.1f} MB'))
            stage=Path(temp)/'instance';stage.mkdir()
            mc=extract_client(archive,stage,cancel,report)
            atomic_json(mc/CLIENT_RECEIPT,artifact_source(archive,asset))
            relative=mc.relative_to(stage);check_cancel(cancel)
            if target.exists():target.rmdir()
            try:os.rename(stage,target)
            except Exception:
                target.mkdir(exist_ok=True);raise
            return str(target/relative)
