import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.backup import BackupManager
from core.installer import Installer, ResourceType
from core.minecraft import MinecraftPath
from gui.dialogs import AboutDialog, BackupDialog
from gui.main_window import MainWindow
from gui.resource_editor import ResourceEditorDialog
from utils.helpers import ensure_content_version_directories

TEST_TMP_ROOT = Path(tempfile.gettempdir()) / "gtnh_mod_installer_tests"


class FakeStringVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeStatusBar:
    def __init__(self):
        self.status = ""

    def set_status(self, status):
        self.status = status


class InstallerRegressionTests(unittest.TestCase):
    def setUp(self):
        temp_root = TEST_TMP_ROOT
        temp_root.mkdir(exist_ok=True)
        self.temp_dir = os.path.join(temp_root, self.id().replace(".", "_"))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.makedirs(self.temp_dir)
        self.client_dir = os.path.join(self.temp_dir, "client")
        self.server_dir = os.path.join(self.temp_dir, "server")
        self.content_dir = os.path.join(self.temp_dir, "Addcontent", "2.7.X")
        os.makedirs(self.client_dir)
        os.makedirs(self.server_dir)
        os.makedirs(self.content_dir)

        mc_path = MinecraftPath(self.client_dir)
        valid, message = mc_path.validate()
        self.assertTrue(valid, message)

        self.installer = Installer(mc_path, gtnh_version="2.7.X")
        self.installer.set_server_path(self.server_dir)
        self.installer._content_base = self.content_dir

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_resource(self, type_key, filename, metadata):
        type_dir = os.path.join(self.content_dir, type_key)
        os.makedirs(type_dir, exist_ok=True)
        source_path = os.path.join(type_dir, filename)
        with open(source_path, "w", encoding="utf-8") as fh:
            fh.write("demo")

        resources_path = os.path.join(self.content_dir, "resources.json")
        data = {"mods": [], "scripts": [], "configs": [], "fonts": [], "resourcepacks": []}
        if os.path.exists(resources_path):
            with open(resources_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        data[type_key].append(metadata)
        with open(resources_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def test_server_only_font_install_reports_failure_when_nothing_can_be_installed(self):
        self._write_resource(
            "fonts",
            "demo.ttf",
            {"id": "font-demo", "name": "Demo Font", "filename": "demo.ttf"},
        )

        resource = self.installer.get_resource_by_id("font-demo", ResourceType.FONT)
        success, message = self.installer.install_resource(resource, install_side="server")

        self.assertFalse(success)
        self.assertIn("无法安装", message)
        self.assertFalse(os.path.exists(os.path.join(self.client_dir, "fonts", "demo.ttf")))
        self.assertFalse(os.path.exists(os.path.join(self.server_dir, "fonts", "demo.ttf")))

    def test_installed_resources_include_entries_missing_from_current_content(self):
        installed_path = os.path.join(self.client_dir, "gtnh_installer_data", "installed.json")
        os.makedirs(os.path.dirname(installed_path), exist_ok=True)
        with open(installed_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "mods": ["missing-mod"],
                    "scripts": [],
                    "configs": [],
                    "fonts": [],
                    "resourcepacks": [],
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

        installed = self.installer.get_all_installed_resources()

        self.assertEqual(len(installed), 1)
        item = installed[0]
        self.assertEqual(item["id"], "missing-mod")
        self.assertEqual(item["resource_type"], ResourceType.MOD)
        self.assertEqual(item["filename"], "missing-mod")
        self.assertTrue(item["missing"])

    def test_uninstall_missing_resource_uses_tracked_filename(self):
        mods_dir = os.path.join(self.client_dir, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        mod_path = os.path.join(mods_dir, "missing-mod.jar")
        with open(mod_path, "w", encoding="utf-8") as fh:
            fh.write("demo")

        installed_path = os.path.join(self.client_dir, "gtnh_installer_data", "installed.json")
        os.makedirs(os.path.dirname(installed_path), exist_ok=True)
        with open(installed_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "mods": [
                        {
                            "id": "missing-mod",
                            "filename": "missing-mod.jar",
                        }
                    ],
                    "scripts": [],
                    "configs": [],
                    "fonts": [],
                    "resourcepacks": [],
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

        success, message = self.installer.uninstall_resource("missing-mod", ResourceType.MOD)

        self.assertTrue(success)
        self.assertIn("成功卸载", message)
        self.assertFalse(os.path.exists(mod_path))


class BackupRegressionTests(unittest.TestCase):
    def setUp(self):
        temp_root = TEST_TMP_ROOT
        temp_root.mkdir(exist_ok=True)
        self.temp_dir = os.path.join(temp_root, self.id().replace(".", "_"))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.makedirs(self.temp_dir)
        self.client_dir = os.path.join(self.temp_dir, "client")
        os.makedirs(self.client_dir)
        self.backup_manager = BackupManager(self.client_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_backup_without_content_returns_clean_error(self):
        success, message = self.backup_manager.create_backup(name="empty-backup", backup_type="client")

        self.assertFalse(success)
        self.assertEqual(message, "没有可备份的内容")
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.client_dir,
                    self.backup_manager.BACKUP_DIR_NAME,
                    "empty-backup",
                )
            )
        )

    def test_create_backup_persists_summary_metadata(self):
        mods_dir = os.path.join(self.client_dir, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        with open(os.path.join(mods_dir, "demo.jar"), "w", encoding="utf-8") as fh:
            fh.write("demo")

        success, backup_id = self.backup_manager.create_backup(name="with-meta", backup_type="client")

        self.assertTrue(success)
        meta = self.backup_manager._load_backup_meta()
        backup_info = next(item for item in meta["backups"] if item["id"] == backup_id)
        self.assertIn("size", backup_info)
        self.assertIn("size_str", backup_info)
        self.assertTrue(backup_info["has_client"])
        self.assertFalse(backup_info["has_server"])
        self.assertGreater(backup_info["size"], 0)

    def test_list_backups_backfills_missing_summary_fields(self):
        backup_path = os.path.join(self.client_dir, self.backup_manager.BACKUP_DIR_NAME, "legacy-backup")
        client_backup_path = os.path.join(backup_path, "client", "mods")
        os.makedirs(client_backup_path, exist_ok=True)
        with open(os.path.join(client_backup_path, "demo.jar"), "w", encoding="utf-8") as fh:
            fh.write("demo")

        self.backup_manager._save_backup_meta(
            {
                "backups": [
                    {
                        "id": "legacy-backup",
                        "created": "2026-04-16T12:00:00",
                        "directories": {"client": ["mods"], "server": []},
                        "auto": False,
                        "type": "client",
                    }
                ]
            }
        )

        backups = self.backup_manager.list_backups()

        self.assertEqual(len(backups), 1)
        self.assertIn("size", backups[0])
        self.assertIn("size_str", backups[0])
        self.assertTrue(backups[0]["has_client"])
        self.assertFalse(backups[0]["has_server"])

        saved_meta = self.backup_manager._load_backup_meta()
        saved_backup = saved_meta["backups"][0]
        self.assertIn("size", saved_backup)
        self.assertIn("size_str", saved_backup)
        self.assertTrue(saved_backup["has_client"])
        self.assertFalse(saved_backup["has_server"])


class MainWindowPathRegressionTests(unittest.TestCase):
    def setUp(self):
        temp_root = TEST_TMP_ROOT
        temp_root.mkdir(exist_ok=True)
        self.temp_dir = os.path.join(temp_root, self.id().replace(".", "_"))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.makedirs(self.temp_dir)
        self.client_dir = os.path.join(self.temp_dir, "client")
        self.server_dir = os.path.join(self.temp_dir, "server")
        os.makedirs(self.client_dir)
        os.makedirs(self.server_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_client_path_preserves_existing_server_path_for_backups(self):
        window = MainWindow.__new__(MainWindow)
        window.client_path_var = FakeStringVar()
        window.server_path_var = FakeStringVar(self.server_dir)
        window.status_bar = FakeStatusBar()
        window._refresh_versions = lambda: None

        MainWindow._set_client_path(window, self.client_dir)

        self.assertIsNotNone(window.installer.server_mc_path)
        self.assertEqual(window.installer.server_mc_path.mc_path, self.server_dir)
        self.assertEqual(window.backup_manager.server_path, self.server_dir)


class ContentDirectoryRegressionTests(unittest.TestCase):
    def setUp(self):
        temp_root = TEST_TMP_ROOT
        temp_root.mkdir(exist_ok=True)
        self.temp_dir = os.path.join(temp_root, self.id().replace(".", "_"))
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.makedirs(self.temp_dir)
        self.content_dir = os.path.join(self.temp_dir, "Addcontent")
        os.makedirs(self.content_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_content_version_directories_creates_required_subfolders_for_existing_versions(self):
        version_dir = os.path.join(self.content_dir, "2.9.X")
        os.makedirs(version_dir)
        os.makedirs(os.path.join(version_dir, "mods"))

        ensure_content_version_directories(self.content_dir)

        for folder_name in ("scripts", "resourcepacks", "mods", "fonts", "configs"):
            self.assertTrue(
                os.path.isdir(os.path.join(version_dir, folder_name)),
                f"missing expected folder: {folder_name}",
            )

    def test_ensure_content_version_directories_is_idempotent(self):
        version_dir = os.path.join(self.content_dir, "2.9.X")
        os.makedirs(version_dir)

        ensure_content_version_directories(self.content_dir)
        ensure_content_version_directories(self.content_dir)

        folder_names = sorted(
            item for item in os.listdir(version_dir)
            if os.path.isdir(os.path.join(version_dir, item))
        )
        self.assertEqual(folder_names, ["configs", "fonts", "mods", "resourcepacks", "scripts"])


class DialogFormattingRegressionTests(unittest.TestCase):
    def test_application_display_version_is_current_release(self):
        self.assertEqual(MainWindow.TITLE, "GTNH 私货安装器 v1.1.1")
        self.assertEqual(AboutDialog.VERSION_TEXT, "版本 1.1.1")

    def test_backup_row_values_formats_backup_type_and_timestamp(self):
        values = BackupDialog._backup_row_values(
            {
                "id": "backup_1",
                "created": "2026-04-16T12:34:56.000000",
                "has_client": True,
                "has_server": True,
                "size_str": "12.0 MB",
            }
        )

        self.assertEqual(values, ("backup_1", "2026-04-16 12:34:56", "客户端+服务端", "12.0 MB"))

    def test_sorted_backups_orders_newest_first(self):
        backups = BackupDialog._sorted_backups(
            [
                {"id": "old", "created": "2026-04-15T12:00:00"},
                {"id": "new", "created": "2026-04-16T12:00:00"},
                {"id": "mid", "created": "2026-04-15T18:00:00"},
            ]
        )

        self.assertEqual([item["id"] for item in backups], ["new", "mid", "old"])

    def test_build_file_list_entries_keeps_metadata_first_and_marks_missing_files(self):
        rows, displayed_ids = ResourceEditorDialog._build_file_list_entries(
            [
                {"id": "mod-a", "filename": "a.jar"},
                {"id": "mod-b", "filename": "b.jar"},
            ],
            {"a.jar", "c.jar"},
        )

        self.assertEqual(rows, ["☑ mod-a (a.jar)", "☑⚠ mod-b (b.jar)", "☐ c.jar"])
        self.assertEqual(displayed_ids, ["mod-a", "mod-b", "c.jar"])

    def test_list_versions_from_content_dir_returns_sorted_directories_only(self):
        temp_root = TEST_TMP_ROOT / "version_scan"
        shutil.rmtree(temp_root, ignore_errors=True)
        os.makedirs(temp_root)
        try:
            os.makedirs(temp_root / "2.7.X")
            os.makedirs(temp_root / "2.9.X")
            with open(temp_root / "README.txt", "w", encoding="utf-8") as fh:
                fh.write("ignore")

            versions = ResourceEditorDialog._list_versions_from_content_dir(str(temp_root))

            self.assertEqual(versions, ["2.9.X", "2.7.X"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_normalize_resources_data_fills_missing_resource_type_keys(self):
        normalized = ResourceEditorDialog._normalize_resources_data(
            {
                "mods": [{"id": "a"}],
                "fonts": [{"id": "font"}],
            }
        )

        self.assertEqual(normalized["mods"], [{"id": "a"}])
        self.assertEqual(normalized["fonts"], [{"id": "font"}])
        self.assertEqual(normalized["scripts"], [])
        self.assertEqual(normalized["configs"], [])
        self.assertEqual(normalized["resourcepacks"], [])


if __name__ == "__main__":
    unittest.main()
