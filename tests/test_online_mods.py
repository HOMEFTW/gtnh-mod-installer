import hashlib
import io
import json
import tempfile
import unittest
import zipfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from core.installer import Installer, ResourceType
from core.minecraft import MinecraftPath
from core.online_mods import OnlineMod, OnlineModClient, OnlineModError, normalize_repository, parse_wiki_index


INDEX_HTML = '''<div class="mw-parser-output"><div class="extra-mod">
<div class="extra-mod-aside-name"><div>Demo</div><div>示例模组</div></div>
<div class="extra-mod-body"><div class="extra-mod-tags"><span>客户端</span><span>服务端</span></div>
<div>仅适用于 2.8.X <a href="https://github.com/dependency/lib">前置</a></div>
<div class="extra-mod-links"><a href="https://github.com/owner/demo/releases">GTNH 特供版</a>
<a href="https://github.com/other/demo">原版</a>
<a href="https://github.com/owner/demo/">重复</a>
<a href="https://example.com/notgithub/mod">其他站点</a></div></div></div></div>'''


def response(payload=None, chunks=None, status=200):
    result = Mock()
    result.status_code = status
    result.json.return_value = payload
    result.iter_content.return_value = iter(chunks or [])
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


class OnlineModsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.session = Mock()
        self.client = OnlineModClient(self.session)
        jar = io.BytesIO()
        with zipfile.ZipFile(jar, "w") as archive:
            archive.writestr("mcmod.info", '[{"modid":"demo"}]')
        self.jar = jar.getvalue()
        self.asset = {"name": "demo-1.0.jar", "size": len(self.jar),
                      "browser_download_url": "https://github.com/owner/demo/releases/download/v1.0/demo-1.0.jar",
                      "digest": "sha256:" + hashlib.sha256(self.jar).hexdigest()}
        self.mod = OnlineMod("Demo", "owner/demo", "仅适用于 2.8.X", True)
        self.release = {"tag": "v1.0", "assets": [self.asset]}

    def download(self, chunks=None):
        self.session.get.return_value = response(chunks=[self.jar] if chunks is None else chunks)
        return self.client.download(self.mod, self.release, self.asset, self.base)

    def assert_no_download(self):
        self.assertEqual(list((self.base / "mods").iterdir()), [])
        self.assertFalse((self.base / "resources.json").exists())

    def test_wiki_keeps_variants_notes_and_sides_but_ignores_dependency_links(self):
        mods = parse_wiki_index(INDEX_HTML)
        self.assertEqual([mod.repository for mod in mods], ["owner/demo", "other/demo"])
        self.assertEqual(mods[0].name, "Demo / 示例模组")
        self.assertEqual(mods[0].link_label, "GTNH 特供版")
        self.assertIn("仅适用于 2.8.X", mods[0].description)
        self.assertTrue(mods[0].server_required)

    def test_changed_wiki_does_not_erase_cache(self):
        cache = self.base / "index.json"
        cache.write_text("previous cache", encoding="utf-8")
        self.session.get.return_value = response({"parse": {"text": {"*": "Access denied"}}})
        with self.assertRaises(OnlineModError):
            self.client.load_index(cache)
        self.assertEqual(cache.read_text(encoding="utf-8"), "previous cache")

    def test_successful_index_is_cached(self):
        cache = self.base / "index.json"
        self.session.get.return_value = response({"parse": {"text": {"*": INDEX_HTML}}})
        mods = self.client.load_index(cache)
        self.assertEqual(self.client.cached_index(cache), mods)

    def test_repository_validation(self):
        self.assertEqual(normalize_repository("https://github.com/owner/demo/releases/latest"), "owner/demo")
        for value in ("https://github.com.evil/owner/demo", "http://github.com/owner/demo",
                      "../demo", "owner/..", "owner/demo/more", "https://evil.com/owner/demo"):
            with self.subTest(value=value), self.assertRaises(OnlineModError):
                normalize_repository(value)

    def test_latest_release_filters_development_artifacts_and_keeps_choice(self):
        names = ["demo.jar", "demo-2.7.jar", "demo-sources.jar", "demo-dev.jar",
                 "demo-javadoc.jar", "demo-deobf.jar", "source.zip"]
        self.session.get.return_value = response({"tag_name": "v1", "assets": [{"name": n} for n in names]})
        result = self.client.latest_release("owner/demo")
        self.assertEqual([a["name"] for a in result["assets"]], names[:2])
        self.assertTrue(self.session.get.call_args.args[0].endswith("/releases/latest"))

    def test_prerelease_or_release_without_jar_is_not_downloaded(self):
        for payload in ({"prerelease": True}, {"assets": []}):
            self.session.get.return_value = response(payload)
            with self.assertRaises(OnlineModError):
                self.client.latest_release("owner/demo")

    def test_rate_limit_and_missing_release_are_actionable(self):
        for code, text in ((403, "额度"), (429, "额度"), (404, "Release")):
            with self.subTest(code=code):
                self.session.get.return_value = response(status=code)
                with self.assertRaisesRegex(OnlineModError, text):
                    self.client.latest_release("owner/demo")

    def test_download_preserves_metadata_and_is_loadable_by_installer(self):
        original = {"mods": [{"id": "old", "filename": "old.jar"}], "configs": [{"id": "config"}],
                    "custom": {"keep": True}}
        (self.base / "resources.json").write_text(json.dumps(original), encoding="utf-8")
        path = self.download()
        self.assertEqual(Path(path).read_bytes(), self.jar)
        data = json.loads((self.base / "resources.json").read_text(encoding="utf-8"))
        self.assertEqual(data["mods"][0], original["mods"][0])
        self.assertEqual(data["custom"], original["custom"])
        self.assertEqual(data["configs"], original["configs"])
        installer = Installer(MinecraftPath(str(self.base / "game")))
        installer._content_base = str(self.base)
        resources = installer.load_resources(ResourceType.MOD)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].version, "v1.0")
        self.assertTrue(resources[0].server_required)

    def test_existing_file_is_never_overwritten(self):
        (self.base / "mods").mkdir()
        path = self.base / "mods" / self.asset["name"]
        path.write_bytes(b"existing")
        with self.assertRaises(OnlineModError):
            self.download()
        self.assertEqual(path.read_bytes(), b"existing")
        self.session.get.assert_not_called()

    def test_changes_saved_during_download_are_preserved(self):
        metadata = self.base / 'resources.json'
        metadata.write_text('{"mods": [], "configs": []}', encoding='utf-8')
        def edit_during_download(done, total):
            metadata.write_text('{"mods": [], "configs": [{"id": "new-config"}]}', encoding='utf-8')
        self.session.get.return_value = response(chunks=[self.jar])
        self.client.download(self.mod, self.release, self.asset, self.base, progress=edit_during_download)
        self.assertEqual(json.loads(metadata.read_text(encoding='utf-8'))['configs'], [{'id': 'new-config'}])

    def test_two_concurrent_downloads_keep_both_entries(self):
        barrier = threading.Barrier(2)
        def download(index):
            session = Mock()
            session.get.return_value = response(chunks=[self.jar])
            asset = {**self.asset, 'name': f'mod-{index}.jar'}
            return OnlineModClient(session).download(
                self.mod, self.release, asset, self.base,
                progress=lambda done, total: barrier.wait(timeout=5))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(download, [1, 2]))
        self.assertTrue(all(Path(path).exists() for path in results))
        data = json.loads((self.base / 'resources.json').read_text(encoding='utf-8'))
        self.assertEqual({item['filename'] for item in data['mods']}, {'mod-1.jar', 'mod-2.jar'})

    def test_incomplete_and_oversized_downloads_leave_no_file_or_metadata(self):
        for chunks in ([self.jar[:-1]], [self.jar + b"extra"]):
            with self.subTest(length=len(chunks[0])), self.assertRaises(OnlineModError):
                self.download(chunks)
            self.assert_no_download()

    def test_wrong_hash_leaves_no_file_or_metadata(self):
        self.asset["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(OnlineModError, "SHA-256"):
            self.download()
        self.assert_no_download()

    def test_html_disguised_as_jar_is_rejected(self):
        self.asset.pop("digest")
        self.asset["size"] = 5
        with self.assertRaisesRegex(OnlineModError, "JAR"):
            self.download([b"<html"])
        self.assert_no_download()

    def test_interrupted_download_cleans_partial_file(self):
        def chunks():
            yield self.jar[:10]
            raise requests.ConnectionError("interrupted")
        with self.assertRaisesRegex(OnlineModError, "下载中断"):
            self.download(chunks())
        self.assert_no_download()

    def test_metadata_failure_rolls_back_new_jar(self):
        with patch("core.online_mods._atomic_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.download()
        self.assert_no_download()

    def test_corrupt_metadata_is_preserved(self):
        path = self.base / "resources.json"
        path.write_text("broken json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.download()
        self.assertEqual(path.read_text(encoding="utf-8"), "broken json")
        self.session.get.assert_not_called()

    def test_unsafe_asset_names_and_urls_are_rejected_before_network(self):
        for name in ("../escape.jar", "C:\\escape.jar", "NUL.jar", "bad:stream.jar"):
            self.asset["name"] = name
            with self.subTest(name=name), self.assertRaises(OnlineModError):
                self.download()
        self.asset["name"] = "demo.jar"
        self.asset["browser_download_url"] = "https://evil.com/owner/demo/releases/download/v1/demo.jar"
        with self.assertRaises(OnlineModError):
            self.download()
        self.session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
