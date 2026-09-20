"""Reproducible manifest roundtrips with in-memory HTTP artifacts."""
import copy
import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.downloads import DownloadClient
from core.installer import Installer, Resource, ResourceType
from core.manifest import (CLIENT_RECEIPT, ManifestInstaller, export_manifest,
                           read_manifest, validate_manifest)
from core.minecraft import MinecraftPath


def archive(files):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as stream:
        for name,content in files.items():stream.writestr(name,content)
    return data.getvalue()


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.library=self.base/'library';self.library.mkdir()
        self.cancel=threading.Event()
        self.report=lambda *_:None
        self.client=DownloadClient();self.addCleanup(self.client.session.close)
        self.service=ManifestInstaller(self.client)
        self.payloads={}
        self.get=patch.object(self.client,'_get',side_effect=self.response);self.get.start();self.addCleanup(self.get.stop)
        self.game=self.add_asset('GT_New_Horizons_2.8.4_Java_17-25.zip',archive({
            'GTNH/mmc-pack.json':'{}','GTNH/instance.cfg':'name=GTNH',
            'GTNH/.minecraft/mods/base.jar':'base','GTNH/.minecraft/config/base.cfg':'original'}),game=True)
        self.mod=self.add_asset('addon.jar',archive({'META-INF/MANIFEST.MF':'demo'}))
        self.pack=self.add_asset('pack.zip',archive({'pack.mcmeta':'{}','assets/demo/a.txt':'texture'}))
        self.manifest={'version':'2.0','gtnh_version':'2.8.X','client':self.game,'resources':{
            'mods':[{'id':'addon','name':'Addon','filename':'addon.jar','download':self.mod,'install_side':'client'}],
            'resourcepacks':[{'id':'pack','name':'Pack','filename':'pack.zip','download':self.pack,'install_side':'client'}]}}

    def add_asset(self,name,data,game=False):
        url=('https://downloads.gtnewhorizons.com/Multi_mc_downloads/' if game else 'https://github.com/demo/repo/releases/download/v1/')+name
        self.payloads[url]=data
        return {'name':name,'url':url,'size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest()}

    def response(self,url,**kwargs):
        data=self.payloads[url]
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.headers={'Content-Length':str(len(data))};response.iter_content.return_value=[data]
        return response

    def installer(self,mc):
        installer=Installer(MinecraftPath(str(mc)),'2.8.X');installer._content_base=str(self.library)
        return installer

    def test_full_install_export_and_reinstall_without_library(self):
        target=self.base/'first'
        mc=Path(self.service.install(self.manifest,target,self.library,self.cancel,self.report))
        self.assertEqual(mc.relative_to(target).as_posix(),'GTNH/.minecraft')
        self.assertTrue((target/'GTNH/mmc-pack.json').exists())
        self.assertEqual((mc/'mods/addon.jar').read_bytes(),self.payloads[self.mod['url']])
        self.assertTrue((mc/'resourcepacks/pack.zip').exists())
        data=export_manifest(self.installer(mc))
        self.assertEqual(data['client']['digest'],self.game['digest'])
        self.assertEqual(data['resources']['mods'][0]['download']['url'],self.mod['url'])
        self.assertEqual(len(data['resources']['mods']),1)
        second=Path(self.service.install(data,self.base/'second',self.library,self.cancel,self.report))
        self.assertEqual((second/'mods/addon.jar').read_bytes(),(mc/'mods/addon.jar').read_bytes())

    def test_direct_client_install_records_source(self):
        asset=dict(self.game);asset.pop('digest')
        mc=Path(self.service.install_client(asset,self.base/'new-client',self.cancel,self.report))
        receipt=json.loads((mc/CLIENT_RECEIPT).read_text(encoding='utf8'))
        self.assertEqual(receipt['digest'],self.game['digest'])

    def test_bad_checksum_and_missing_local_leave_target_empty(self):
        for mode in ('digest','local'):
            data=copy.deepcopy(self.manifest)
            if mode=='digest':data['resources']['mods'][0]['download']['digest']='sha256:'+'0'*64
            else:data['resources']['configs']=[{'id':'missing','name':'Local config'}]
            target=self.base/mode;target.mkdir()
            with self.assertRaises(Exception):self.service.install(data,target,self.library,self.cancel,self.report)
            self.assertEqual(list(target.iterdir()),[])

    def test_existing_game_is_never_overwritten_by_full_manifest(self):
        target=self.base/'existing';target.mkdir();(target/'saves').mkdir()
        with self.assertRaises(ValueError):self.service.install(self.manifest,target,self.library,self.cancel,self.report)
        self.assertTrue((target/'saves').exists())

    def test_traversal_archive_rejected_without_publishing(self):
        data=copy.deepcopy(self.manifest)
        data['client']=self.add_asset('unsafe.zip',archive({'../escaped.txt':'no','mods/base.jar':'base'}),True)
        with self.assertRaises(ValueError):self.service.install(data,self.base/'unsafe',self.library,self.cancel,self.report)
        self.assertFalse((self.base/'unsafe').exists());self.assertFalse((self.base/'escaped.txt').exists())

    def test_cancel_does_not_publish(self):
        self.cancel.set()
        with self.assertRaises(Exception):self.service.install(self.manifest,self.base/'cancel',self.library,self.cancel,self.report)
        self.assertFalse((self.base/'cancel').exists())

    def test_local_missing_preflight_does_not_install_downloaded_addon(self):
        mc=self.base/'mc';mc.mkdir()
        data=copy.deepcopy(self.manifest);data.pop('client')
        data['resources']['configs']=[{'id':'missing'}]
        with self.assertRaises(ValueError):self.service.install(data,mc,self.library,self.cancel,self.report)
        self.assertFalse((mc/'mods/addon.jar').exists())

    def test_legacy_id_manifest_remains_installable(self):
        folder=self.library/'mods';folder.mkdir();(folder/'local.jar').write_bytes(self.payloads[self.mod['url']])
        mc=self.base/'legacy';mc.mkdir()
        data={'version':'1.0','gtnh_version':'2.8.X','resources':{'mods':['local.jar']}}
        self.service.install(data,mc,self.library,self.cancel,self.report)
        self.assertTrue((mc/'mods/local.jar').exists())

    def test_modified_installed_file_is_not_advertised_as_original_download(self):
        mc=Path(self.service.install(self.manifest,self.base/'first',self.library,self.cancel,self.report))
        (mc/'mods/addon.jar').write_bytes(b'edited')
        data=export_manifest(self.installer(mc))
        self.assertIsNone(data['resources']['mods'][0]['download'])

    def test_invalid_version_path_and_missing_hash_are_rejected(self):
        for mode in ('version','hash','url'):
            data=copy.deepcopy(self.manifest)
            if mode=='version':data['gtnh_version']='../escape'
            elif mode=='hash':data['resources']['mods'][0]['download'].pop('digest')
            else:data['client']['url']='https://example.org/game.zip'
            with self.assertRaises(ValueError):validate_manifest(data)

    def test_export_includes_actual_installed_side_and_excludes_uninstalled(self):
        mc=self.base/'mc';mc.mkdir();server=self.base/'server';server.mkdir()
        installer=self.installer(mc);installer.set_server_path(str(server))
        jar=self.base/'addon.jar';jar.write_bytes(self.payloads[self.mod['url']])
        res=Resource('addon','Addon','addon.jar',str(jar),ResourceType.MOD,server_required=True,download=self.mod)
        self.assertTrue(installer.install_resource(res,install_side='server')[0])
        data=export_manifest(installer)
        self.assertEqual(data['resources']['mods'][0]['install_side'],'server')
        self.assertEqual(data['resources']['resourcepacks'],[])

    def test_ui_import_runs_worker_and_selects_installed_client(self):
        from gui.main_window import MainWindow
        from utils.logger import logger
        manifest_path=self.base/'shared pack.hflist'
        manifest_path.write_text(json.dumps(self.manifest),encoding='utf8')
        target=self.base/'ui-client'
        with patch.object(MainWindow,'_load_config'), patch.object(MainWindow,'_refresh_versions'), \
             patch('gui.main_window.init_external_content',return_value=str(self.library)), \
             patch.object(MainWindow,'_save_config'), \
             patch('gui.main_window.filedialog.askdirectory',return_value=str(target)), \
             patch('gui.main_window.messagebox.showinfo'), \
             patch('gui.main_window.messagebox.showerror') as error, \
             patch.object(DownloadClient,'_get',side_effect=self.response):
            window=MainWindow()
            try:
                window.root.withdraw()
                window._load_install_list(str(manifest_path))
                error.assert_not_called()
                self.assertFalse(window._manifest_busy)
                self.assertEqual(window.version_var.get(),'2.8.X')
                self.assertTrue((Path(window.mc_path.mc_path)/'mods/addon.jar').exists())
            finally:
                logger.set_gui_callback(None)
                window.root.destroy()
