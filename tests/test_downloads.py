import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from core.downloads import DownloadClient, DownloadEntry, parse_games, parse_packs
from core.online_mods import OnlineModError

class DownloadsTests(unittest.TestCase):
    def archive(self, pack=True):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('pack.mcmeta' if pack else 'instance.cfg','{}')
        return out.getvalue()

    def response(self,data):
        r=Mock();r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
        r.headers={'Content-Length':str(len(data))};r.iter_content.return_value=[data]
        return r

    def test_official_clients_exclude_servers_and_foreign_urls(self):
        html=''.join(f'<a href="{u}">Java 8</a>' for u in [
          'https://downloads.gtnewhorizons.com/ClientPacks/a.zip',
          'https://downloads.gtnewhorizons.com/Multi_mc_downloads/betas/b.zip',
          'https://downloads.gtnewhorizons.com/ServerPacks/a.zip',
          'https://other.example/ClientPacks/a.zip'])
        rows=parse_games(html)
        self.assertEqual(len(rows),2);self.assertFalse(rows[0].preview);self.assertTrue(rows[1].preview)

    def test_pack_rows_preserve_download_tag_and_exclude_shaders(self):
        row='<tr><td>icon</td><td>Pack</td><td>Author</td><td>Notes <a href="https://example.org/dependency">dependency</a></td><td><a href="https://github.com/a/b/releases/tag/special">下载</a><a href="https://github.com/a/b">源码</a></td></tr>'
        rows=parse_packs('<table>'+row+'</table><span id="光影"></span><table>'+row+'</table>')
        self.assertEqual(len(rows),1);self.assertTrue(rows[0].url.endswith('/special'))

    def test_specific_release_uses_tag_api_and_only_zip_assets(self):
        client=DownloadClient();self.addCleanup(client.session.close)
        r=self.response(b'');r.json.return_value={'assets':[{'name':'pack.zip','browser_download_url':'https://github.com/a/b/releases/download/x/pack.zip'},{'name':'mod.jar'}]}
        with patch.object(client,'_get',return_value=r) as get:
            files=client.assets(DownloadEntry('Pack','https://github.com/a/b/releases/tag/x','资源包'))
        self.assertTrue(get.call_args.args[0].endswith('/releases/tags/x'));self.assertEqual(len(files),1)

    def test_download_validates_and_preserves_existing_file(self):
        client=DownloadClient();self.addCleanup(client.session.close)
        data=self.archive();asset={'name':'pack.zip','url':'https://example.org/pack.zip'}
        with tempfile.TemporaryDirectory() as folder,patch.object(client,'_get',return_value=self.response(data)):
            path=client.download_zip(asset,folder,threading.Event(),lambda *_:None,True)
            self.assertEqual(Path(path).read_bytes(),data)
            with self.assertRaises(OnlineModError):client.download_zip(asset,folder,threading.Event(),lambda *_:None)

    def test_cancel_and_invalid_pack_leave_no_files(self):
        client=DownloadClient();self.addCleanup(client.session.close)
        for canceled in (False,True):
            cancel=threading.Event()
            if canceled:cancel.set()
            with tempfile.TemporaryDirectory() as folder,patch.object(client,'_get',return_value=self.response(self.archive(False))):
                with self.assertRaises(OnlineModError):client.download_zip({'name':'p.zip','url':'https://example.org/p.zip'},folder,cancel,lambda *_:None,True)
                self.assertEqual(list(Path(folder).iterdir()),[])

    def test_pack_import_and_metadata_failure_rollback(self):
        client=DownloadClient();self.addCleanup(client.session.close)
        entry=DownloadEntry('Pack','https://example.org','资源包')
        asset={'name':'p.zip','url':'https://example.org/p.zip'}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(client,'_get',return_value=self.response(self.archive())):
                client.download_pack(entry,asset,folder,threading.Event(),lambda *_:None)
            meta=json.loads((Path(folder)/'resources.json').read_text(encoding='utf8'))
            self.assertEqual(meta['resourcepacks'][0]['filename'],'p.zip')
        with tempfile.TemporaryDirectory() as folder,patch.object(client,'_get',return_value=self.response(self.archive())),patch('core.downloads._atomic_json',side_effect=OSError('denied')):
            with self.assertRaises(OSError):client.download_pack(entry,asset,folder,threading.Event(),lambda *_:None)
            self.assertFalse((Path(folder)/'resourcepacks'/'p.zip').exists())

    def test_path_traversal_rejected(self):
        client=DownloadClient();self.addCleanup(client.session.close)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OnlineModError):client.download_zip({'name':'../p.zip','url':'https://example.org/p.zip'},folder,threading.Event(),lambda *_:None)
