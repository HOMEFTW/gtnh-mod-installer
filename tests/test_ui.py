"""Behavior checks for the modern navigation and filterable resource lists."""
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from gui.main_window import MainWindow
from gui.theme import apply_theme
from gui.widgets import ResourceListFrame
from gui.dialogs import BackupDialog
from gui.online_mods import OnlineModsDialog
from gui.downloads import DownloadsDialog


class DialogLayoutTests(unittest.TestCase):
    def test_actions_remain_visible_at_minimum_size(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        apply_theme(root)
        manager = Mock()
        manager.list_backups.return_value = []
        backup = BackupDialog(root, manager, has_server=True)
        backup.geometry('800x520')
        root.update()

        def buttons(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == 'TButton':
                    yield child
                yield from buttons(child)

        def assert_visible(dialog, controls):
            for control in controls:
                self.assertTrue(control.winfo_ismapped(), control.cget('text'))
                self.assertLessEqual(control.winfo_rooty() + control.winfo_height(),
                                     dialog.winfo_rooty() + dialog.winfo_height())

        assert_visible(backup, list(buttons(backup)))
        backup.destroy()
        with patch('gui.online_mods.OnlineModClient') as client, patch.object(OnlineModsDialog, '_refresh'):
            client.return_value.cached_index.return_value = []
            online = OnlineModsDialog(root, '2.8.X', 'unused.json')
        online.geometry('940x720')
        root.update()
        assert_visible(online, [online.query_button, online.download_button])
        self.assertGreater(online.tree.winfo_height(), 80)
        online._close()
        with patch.object(DownloadsDialog, '_refresh'):
            downloads = DownloadsDialog(root, game=True)
        downloads.geometry('940x680')
        root.update()
        controls = [downloads.download, downloads.install_client_button, downloads.stop]
        assert_visible(downloads, controls)
        for control in controls:
            self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                 downloads.winfo_rootx() + downloads.winfo_width())
        downloads._close()


class ResourceListUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        apply_theme(self.root)
        self.listing = ResourceListFrame(self.root)
        self.listing.pack(fill='both', expand=True)
        self.listing.set_resources([
            {'id': 'one', 'name': 'Alpha', 'description': '完整说明第一行\n第二行'},
            {'id': 'two', 'name': 'Beta'}])

    def test_filter_keeps_checked_items_and_select_all_targets_visible_results(self):
        self.listing.search_var.set('Alpha')
        self.listing.select_all()
        self.listing.search_var.set('Beta')
        self.assertEqual(self.listing.tree.get_children(), ('two',))
        self.assertEqual(self.listing.get_selected_ids(), ['one'])
        self.listing.search_var.set('')
        self.assertEqual(self.listing.tree.get_children(), ('one', 'two'))

    def test_reload_removes_detached_rows_without_duplicate_ids(self):
        self.listing.search_var.set('Alpha')
        self.listing.set_resources([{'id': 'two', 'name': 'New Alpha'}])
        self.assertEqual(self.listing.tree.get_children(), ('two',))
        self.assertEqual(self.listing.get_selected_ids(), [])

    def test_details_show_full_description_and_space_toggles_selection(self):
        self.listing.tree.selection_set('one')
        self.listing.tree.focus('one')
        self.listing._update_details()
        self.assertIn('完整说明第一行\n第二行', self.listing.details.get('1.0', 'end'))
        self.assertEqual(self.listing._toggle_focused(), 'break')
        self.assertEqual(self.listing.get_selected_ids(), ['one'])


class MainWindowUITests(unittest.TestCase):
    def test_navigation_actions_and_compact_layout(self):
        with patch.object(MainWindow, '_load_config'), patch.object(MainWindow, '_refresh_versions'):
            window = MainWindow()
        try:
            window.root.withdraw()
            self.assertFalse(window.generate_list_var.get())
            with patch.object(window, '_load_install_list') as load:
                event = Mock(data='{D:/Shared Packs/My Pack.hflist}')
                window._on_drop(event)
                load.assert_called_once_with('D:/Shared Packs/My Pack.hflist')
            for index, (_, title, kind) in enumerate(MainWindow.RESOURCE_TABS):
                window.nav_buttons[index].invoke()
                window.root.update()
                self.assertEqual(window.notebook.index(window.notebook.select()), index)
                self.assertEqual(window.page_title.cget('text'), title)
                self.assertEqual(str(window.install_button.cget('state')), 'disabled' if kind is None else 'normal')
            window.root.geometry('1000x800')
            window.root.deiconify()
            window.root.update()
            self.assertGreater(window.installed_list.tree.winfo_height(), 100)
            window._toggle_log()
            window.root.update_idletasks()
            self.assertTrue(window.log_frame.winfo_ismapped())
            self.assertGreater(window.installed_list.tree.winfo_height(), 50)
            window._toggle_log()
            self.assertFalse(window._logs_visible)
        finally:
            from utils.logger import logger
            logger.set_gui_callback(None)
            window.root.destroy()
