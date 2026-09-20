import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.backup import BackupManager
from core.installer import Installer, Resource, ResourceType
from core.minecraft import MinecraftPath
from gui.main_window import MainWindow
from gui.resource_editor import ResourceEditorDialog
from utils.helpers import staged_resource_update


class ReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.game = self.base / 'game'
        self.content = self.base / 'content'
        self.game.mkdir()
        self.content.mkdir()
        self.installer = Installer(MinecraftPath(str(self.game)))
        self.installer._content_base = str(self.content)

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def make_resource(self, kind=ResourceType.MOD, name='new.jar', rid='demo'):
        source = self.content / kind.value / name
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(b'new')
        return Resource(rid, 'Demo', name, str(source), kind, server_required=True)

    def test_zip_traversal_is_rejected_before_any_extraction(self):
        for member in ('../escaped.txt', '..\\escaped.txt', '/absolute.txt', 'C:/outside.txt'):
            with self.subTest(member=member):
                archive = self.base / 'translation.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('safe.txt', 'safe')
                    z.writestr(member, 'unsafe')
                window = SimpleNamespace(mc_path=MinecraftPath(str(self.game)), root=Mock(),
                                         status_bar=Mock(), _load_all_resources=Mock())
                with patch('gui.main_window.filedialog.askopenfilename', return_value=str(archive)), \
                     patch('gui.main_window.messagebox') as messages:
                    MainWindow._install_localization(window)
                messages.showerror.assert_called_once()
                self.assertFalse((self.base / 'escaped.txt').exists())
                self.assertFalse((self.game / 'safe.txt').exists())

    def test_server_switch_keeps_destination_records(self):
        for server in ('a', 'b'):
            self.write_json(self.base / server / 'gtnh_installer_data/installed.json',
                            {'mods': [{'id': server, 'filename': server + '.jar'}]})
        self.installer.set_server_path(str(self.base / 'a'))
        self.installer.get_installed_resources(ResourceType.MOD, 'server')
        self.installer.set_server_path(str(self.base / 'b'))
        self.installer.install_resource(self.make_resource(), install_side='server')
        self.assertEqual(self.installer.get_installed_resources(ResourceType.MOD, 'server'), ['b', 'demo'])

    def test_uninstall_uses_each_sides_recorded_filename(self):
        resource = self.make_resource()
        self.write_json(self.content / 'resources.json', {'mods': [{'id': resource.id, 'filename': resource.filename}]})
        server = self.base / 'server'
        for directory, name in ((self.game, 'old-client.jar'), (server, 'old-server.jar')):
            (directory / 'mods').mkdir(parents=True)
            (directory / 'mods' / name).write_bytes(b'old')
            self.write_json(directory / 'gtnh_installer_data/installed.json',
                            {'mods': [{'id': 'demo', 'filename': name}]})
        self.installer.set_server_path(str(server))
        ok, message = self.installer.uninstall_resource('demo', ResourceType.MOD)
        self.assertTrue(ok, message)
        self.assertFalse((self.game / 'mods/old-client.jar').exists())
        self.assertFalse((server / 'mods/old-server.jar').exists())

    def test_failed_uninstall_retains_record_for_retry(self):
        resource = self.make_resource()
        self.installer.install_resource(resource, install_side='client')
        with patch('core.installer.os.remove', side_effect=PermissionError('locked')):
            ok, message = self.installer.uninstall_resource('demo', ResourceType.MOD)
        self.assertFalse(ok)
        self.assertIn('demo', self.installer.get_installed_resources(ResourceType.MOD))
        self.assertTrue((self.game / 'mods/new.jar').exists())

    def test_old_metadata_supports_new_resource_types(self):
        self.write_json(self.game / 'gtnh_installer_data/installed.json', {'mods': []})
        resource = self.make_resource(ResourceType.SHADERPACK, 'shader.zip')
        self.installer.install_resource(resource, install_side='client')
        self.installer.refresh_installed_cache()
        self.assertEqual(self.installer.get_installed_resources(ResourceType.SHADERPACK), ['demo'])

    def test_server_failure_is_returned_as_partial_failure(self):
        server = self.base / 'server'
        server.mkdir()
        self.installer.set_server_path(str(server))
        with patch.object(self.installer, '_copy_resource', side_effect=[(True, 'ok'), (False, 'denied')]):
            ok, message = self.installer.install_resource(self.make_resource(), install_side='both')
        self.assertFalse(ok)
        self.assertIn('服务端', message)
        self.assertEqual(self.installer.get_installed_resources(ResourceType.MOD), ['demo'])

    def test_update_copy_failure_preserves_originals(self):
        mods = self.content / '2.8.X/mods'
        mods.mkdir(parents=True)
        old = mods / 'old.jar'
        old.write_bytes(b'old')
        new = self.base / 'new.jar'
        new.write_bytes(b'new')
        editor = SimpleNamespace(id_var=Mock(get=lambda: 'demo'), filename_var=Mock(get=lambda: 'old.jar'),
                                 current_version='2.8.X', current_type='mods', client_path=None, server_path=None)
        with patch('gui.resource_editor.init_external_content', return_value=str(self.content)), \
             patch('gui.resource_editor.filedialog.askopenfilename', return_value=str(new)), \
             patch('gui.resource_editor.shutil.copy2', side_effect=OSError('disk full')), \
             patch('gui.resource_editor.messagebox'):
            ResourceEditorDialog._update_resource_file(editor)
        self.assertEqual(old.read_bytes(), b'old')

    def test_backup_restores_all_managed_resource_directories(self):
        folders = ('mods', 'config', 'scripts', 'fonts', 'fontfiles', 'resourcepacks', 'shaderpacks', 'serverutilities')
        for name in folders:
            (self.game / name).mkdir()
            (self.game / name / 'file').write_bytes(b'old')
        manager = BackupManager(str(self.game))
        self.assertTrue(manager.create_backup('snapshot', 'client')[0])
        for name in folders:
            (self.game / name / 'file').write_bytes(b'new')
        self.assertTrue(manager.restore_backup('snapshot', 'client')[0])
        for name in folders:
            self.assertEqual((self.game / name / 'file').read_bytes(), b'old', name)

    def test_restore_removes_directories_absent_at_snapshot(self):
        (self.game / 'mods').mkdir()
        manager = BackupManager(str(self.game))
        manager.create_backup('snapshot', 'client')
        (self.game / 'config').mkdir()
        (self.game / 'config/new.cfg').write_bytes(b'new')
        self.assertTrue(manager.restore_backup('snapshot', 'client')[0])
        self.assertFalse((self.game / 'config').exists())

    def test_legacy_backup_preserves_uncovered_resources_and_records(self):
        manager = BackupManager(str(self.game))
        backup = Path(manager.backup_base) / 'legacy/client'
        (backup / 'mods').mkdir(parents=True)
        (self.game / 'fonts').mkdir()
        (self.game / 'fonts/font.ttf').write_bytes(b'current')
        self.write_json(self.game / 'gtnh_installer_data/installed.json', {'mods': [], 'fonts': ['font']})
        self.assertTrue(manager.restore_backup('legacy', 'client')[0])
        self.assertEqual((self.game / 'fonts/font.ttf').read_bytes(), b'current')
        self.assertEqual(json.loads((self.game / 'gtnh_installer_data/installed.json').read_text())['fonts'], ['font'])

    def test_update_rolls_back_all_files_when_metadata_commit_fails(self):
        source = self.content / 'new.jar'
        old = self.content / 'old.jar'
        installed = self.game / 'old.jar'
        destination = self.content / 'replacement.jar'
        source.write_bytes(b'new')
        old.write_bytes(b'old-library')
        installed.write_bytes(b'old-game')
        with self.assertRaises(OSError):
            with staged_resource_update(source, destination, [old, installed]):
                self.assertEqual(destination.read_bytes(), b'new')
                raise OSError('metadata write failed')
        self.assertFalse(destination.exists())
        self.assertEqual(old.read_bytes(), b'old-library')
        self.assertEqual(installed.read_bytes(), b'old-game')
        self.assertFalse(list(self.base.rglob('*.rollback')))
        self.assertFalse(list(self.base.rglob('*.part')))

    def test_update_can_select_its_own_original_file(self):
        old = self.content / 'same.jar'
        old.write_bytes(b'original')
        with staged_resource_update(old, old, [old]):
            self.assertEqual(old.read_bytes(), b'original')
        self.assertEqual(old.read_bytes(), b'original')

    def test_stale_editor_cannot_overwrite_concurrent_metadata_changes(self):
        path = self.content / '2.8.X/resources.json'
        initial = ResourceEditorDialog._normalize_resources_data({'mods': []})
        self.write_json(path, {**initial, 'mods': [{'id': 'downloaded', 'filename': 'new.jar'}]})
        editor = ResourceEditorDialog.__new__(ResourceEditorDialog)
        editor.current_version = '2.8.X'
        editor._metadata_baseline = initial
        editor.resources_data = {**initial, 'configs': [{'id': 'my-edit'}]}
        with patch('gui.resource_editor.init_external_content', return_value=str(self.content)), \
             patch('gui.resource_editor.messagebox'):
            self.assertFalse(editor._save_to_file())
        self.assertEqual(json.loads(path.read_text())['mods'][0]['id'], 'downloaded')
