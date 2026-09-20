"""
Main window for GTNH Mod Installer GUI
"""
import tkinter as tk
import queue
from tkinter import ttk, messagebox, filedialog
from typing import Optional, List, Tuple
import os
import sys
import webbrowser

from app_version import APP_VERSION
from gui.theme import apply_theme
from gui.widgets import ResourceListFrame, LogFrame, StatusBar, ProgressDialog
from gui.dialogs import FolderSelectDialog, BackupDialog, AboutDialog
from gui.resource_editor import ResourceEditorDialog
from gui.online_mods import OnlineModsDialog
from gui.downloads import DownloadsDialog
from core.minecraft import MinecraftPath
from core.installer import Installer, ResourceType
from core.backup import BackupManager
from utils.logger import logger
from utils.helpers import (
    ensure_content_version_directories,
    get_app_dir,
    init_external_content,
    is_frozen,
    load_json,
    save_json,
    safe_child_path,
)

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


class MainWindow:
    """Main application window"""

    TITLE = f"GTNH 私货安装器 v{APP_VERSION}"
    RESOURCE_TABS = [
        ("mod", "模组", ResourceType.MOD),
        ("script", "脚本", ResourceType.SCRIPT),
        ("config", "配置", ResourceType.CONFIG),
        ("font", "字体", ResourceType.FONT),
        ("resourcepack", "资源包", ResourceType.RESOURCEPACK),
        ("shaderpack", "光影包", ResourceType.SHADERPACK),
        ("serverutilities", "ServerUtilities", ResourceType.SERVERUTILITIES),
        ("installed", "已安装", None),
    ]
    CLIENT_ONLY_TYPES = {ResourceType.FONT, ResourceType.RESOURCEPACK, ResourceType.SHADERPACK}

    def __init__(self):
        # Use TkinterDnD.Tk() if available, otherwise fallback to tk.Tk()
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        self.root.title(self.TITLE)
        self.root.geometry("1180x900")
        self.root.minsize(1000, 800)
        apply_theme(self.root)

        # Set window icon
        self._set_window_icon()

        # Core components
        self.mc_path: Optional[MinecraftPath] = None
        self.installer: Optional[Installer] = None
        self.backup_manager: Optional[BackupManager] = None
        self.current_version: str = ""

        # Generate list flag
        self.generate_list_var = tk.BooleanVar(value=False)
        self._manifest_busy = False

        # Build UI
        self._create_menu()
        self._create_widgets()
        self._setup_logger()
        self._setup_drag_drop()

        # Load saved config
        self._load_config()

    def _set_window_icon(self):
        """Set window icon from icon.png"""
        try:
            # Try to find icon.png in different locations
            if is_frozen():
                # When frozen, icon is bundled
                icon_path = os.path.join(sys._MEIPASS, 'icon.png')
            else:
                # When running from source
                icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icon.png')

            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
                # Keep reference to prevent garbage collection
                self.root._icon = icon
        except Exception as e:
            logger.warning(f"无法加载窗口图标: {e}")

    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择客户端文件夹", command=self._select_client_folder)
        file_menu.add_command(label="选择服务端文件夹", command=self._select_server_folder)
        file_menu.add_separator()
        file_menu.add_command(label="加载安装清单...", command=self._load_install_list_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="备份管理", command=self._show_backup_dialog)
        tools_menu.add_cascade(label="下载中心", menu=self._create_download_menu(tools_menu))
        tools_menu.add_command(label="初始化模组", command=self._initialize_mods)
        tools_menu.add_command(label="汉化安装...", command=self._install_localization)
        tools_menu.add_separator()
        tools_menu.add_command(label="中文维基私货页面", command=self._open_wiki)
        tools_menu.add_command(label="安装常见问题", command=self._open_install_faq)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        """Resource navigation, workspace settings and a focused installation area."""
        shell = ttk.Frame(self.root)
        shell.pack(fill=tk.BOTH, expand=True)
        sidebar = ttk.Frame(shell, style='Card.TFrame', width=190, padding=(14, 22))
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="GTNH", style='CardHeading.TLabel',
                  font=('Microsoft YaHei UI', 22, 'bold')).pack(anchor=tk.W, padx=12)
        ttk.Label(sidebar, text="私货安装器", style='CardMuted.TLabel').pack(anchor=tk.W, padx=12, pady=(0, 26))
        ttk.Label(sidebar, text="资源库", style='CardMuted.TLabel').pack(anchor=tk.W, padx=12, pady=(0, 8))
        self.nav_buttons = []
        for index, (_attr, label, _type) in enumerate(self.RESOURCE_TABS):
            button = ttk.Button(sidebar, text=label, style='Nav.TButton',
                                command=lambda i=index: self.notebook.select(i))
            button.pack(fill=tk.X, pady=2)
            self.nav_buttons.append(button)
        ttk.Label(sidebar, text=f"v{APP_VERSION}  ·  GT New Horizons", style='CardMuted.TLabel',
                  font=('Microsoft YaHei UI', 8)).pack(side=tk.BOTTOM, anchor=tk.W, padx=8)
        ttk.Button(sidebar, text="备份与还原", command=self._show_backup_dialog).pack(side=tk.BOTTOM, fill=tk.X, pady=16)

        workspace = ttk.Frame(shell, padding=(22, 20))
        workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        heading = ttk.Frame(workspace)
        heading.pack(fill=tk.X, pady=(0, 16))
        ttk.Menubutton(heading, text="下载中心", style='Primary.TMenubutton',
                       menu=self._create_download_menu(heading)).pack(side=tk.RIGHT)
        self.page_title = ttk.Label(heading, text="模组", style='Title.TLabel')
        self.page_title.pack(anchor=tk.W)
        ttk.Label(heading, text="管理额外资源，为你的 GTNH 配置合适的内容。", style='Muted.TLabel').pack(anchor=tk.W, pady=(3, 0))

        settings = ttk.Frame(workspace, style='Card.TFrame', padding=16)
        settings.pack(fill=tk.X, pady=(0, 16))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="安装位置", style='CardHeading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(settings, textvariable=self.version_var, width=12, state='readonly')
        self.version_combo.grid(row=0, column=2, padx=8, pady=(0, 10))
        self.version_combo.bind('<<ComboboxSelected>>', self._on_version_changed)
        ttk.Label(settings, text="资源版本", style='CardMuted.TLabel').grid(row=0, column=1, sticky=tk.E, pady=(0, 10))
        ttk.Button(settings, text="刷新", command=self._refresh_versions).grid(row=0, column=3, pady=(0, 10))
        self.client_path_var = tk.StringVar()
        self.server_path_var = tk.StringVar()
        for row, label, var, command, attr in (
            (1, "客户端", self.client_path_var, self._select_client_folder, 'client_path_entry'),
            (2, "服务端", self.server_path_var, self._select_server_folder, 'server_path_entry')):
            ttk.Label(settings, text=label, style='CardMuted.TLabel').grid(row=row, column=0, sticky=tk.W, padx=(0, 16), pady=4)
            entry = ttk.Entry(settings, textvariable=var, state='readonly')
            entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=(0, 8), pady=4)
            setattr(self, attr, entry)
            ttk.Button(settings, text="选择文件夹", command=command).grid(row=row, column=3, pady=4)

        # Pack the footer first so primary actions remain visible when shrinking the window.
        footer = ttk.Frame(workspace)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
        self.log_frame = LogFrame(footer)
        self.status_bar = StatusBar(footer)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        ttk.Button(self.status_bar, text="展开日志", command=self._toggle_log).pack(side=tk.RIGHT)
        self.log_toggle = self.status_bar.winfo_children()[-1]
        self._logs_visible = False
        actions = ttk.Frame(footer)
        actions.pack(fill=tk.X)
        self.selection_label = ttk.Label(actions, text="已选择: 0 项", style='Muted.TLabel')
        self.selection_label.pack(side=tk.LEFT)
        self.install_button = ttk.Button(actions, text="安装选中资源", style='Primary.TButton', command=self._install_selected)
        self.install_button.pack(side=tk.RIGHT)
        self.uninstall_button = ttk.Button(actions, text="卸载选中资源", style='Danger.TButton', command=self._uninstall_selected)
        self.uninstall_button.pack(side=tk.RIGHT, padx=8)
        ttk.Button(actions, text="加载清单", command=self._load_install_list_dialog).pack(side=tk.RIGHT)
        ttk.Button(actions, text="编辑资源", command=self._open_resource_editor).pack(side=tk.RIGHT, padx=8)

        toolbar = ttk.Frame(workspace)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="全选", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="取消全选", command=self._deselect_all).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(toolbar, text="安装后生成清单", variable=self.generate_list_var).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(toolbar, text="生成清单", command=self._save_install_list).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="备份当前", command=self._create_backup).pack(side=tk.RIGHT)
        self.notebook = ttk.Notebook(workspace, style='Content.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)
        for attr, label, res_type in self.RESOURCE_TABS:
            frame = ttk.Frame(self.notebook, style='Card.TFrame', padding=12)
            setattr(self, f'{attr}_frame', frame)
            self.notebook.add(frame, text=label)
            options = {'on_select_callback': self._update_selection_count}
            if res_type is None:
                options['columns'] = ResourceListFrame.COLUMNS_INSTALLED
            else:
                options.update(on_double_click=self._on_resource_double_click, on_right_click=self._show_context_menu)
            listing = ResourceListFrame(frame, **options)
            listing.pack(fill=tk.BOTH, expand=True)
            setattr(self, f'{attr}_list', listing)
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        self._refresh_versions()
        self._on_tab_changed(None)

    def _toggle_log(self):
        self._logs_visible = not self._logs_visible
        if self._logs_visible:
            self.log_frame.pack(fill=tk.X, before=self.status_bar, pady=(10, 0))
        else:
            self.log_frame.pack_forget()
        self.log_toggle.configure(text="收起日志" if self._logs_visible else "展开日志")

    def _setup_logger(self):
        """Setup logger with GUI callback"""
        # Install/download workers may log; widgets must only be touched on the Tk thread.
        self._log_events = queue.Queue()
        logger.set_gui_callback(self._log_events.put)
        def drain_logs():
            try:
                while True:
                    self.log_frame.append_log(self._log_events.get_nowait())
            except queue.Empty:
                pass
            self._log_job = self.root.after(100, drain_logs)
        self._log_job = self.root.after(100, drain_logs)
        def stop_logs(event):
            if event.widget is self.root:
                self.root.after_cancel(self._log_job)
        self.root.bind('<Destroy>', stop_logs, add='+')

    def _load_config(self):
        """Load saved config"""
        config_path = os.path.join(get_app_dir(), 'config.json')
        config = load_json(config_path)
        if config:
            missing_paths = []
            config_changed = False
            if 'client_path' in config and config['client_path']:
                if os.path.exists(config['client_path']):
                    self.client_path_var.set(config['client_path'])
                    self._set_client_path(config['client_path'])
                else:
                    self.client_path_var.set('')
                    config_changed = True
                    missing_paths.append(f"客户端路径: {config['client_path']}")
            if 'server_path' in config and config['server_path']:
                if os.path.exists(config['server_path']):
                    self.server_path_var.set(config['server_path'])
                    if self.installer:
                        self.installer.set_server_path(config['server_path'])
                    if self.backup_manager:
                        self.backup_manager.set_server_path(config['server_path'])
                else:
                    self.server_path_var.set('')
                    config_changed = True
                    missing_paths.append(f"服务端路径: {config['server_path']}")
            if missing_paths:
                messagebox.showwarning("路径不存在", "以下路径不存在，已清除:\n\n" + "\n".join(missing_paths))
            if 'last_version' in config:
                self.version_var.set(config['last_version'])
                self._on_version_changed(None)
            if config_changed:
                self._save_config()

    def _save_config(self):
        """Save current config"""
        config_path = os.path.join(get_app_dir(), 'config.json')
        config = load_json(config_path) or {}
        config['client_path'] = self.client_path_var.get()
        config['server_path'] = self.server_path_var.get()
        config['last_version'] = self.version_var.get()
        save_json(config_path, config)

    def _refresh_versions(self):
        """Refresh available versions from Addcontent directory"""
        # Initialize external content folder if needed
        content_dir = init_external_content()
        ensure_content_version_directories(content_dir)

        versions = []
        if os.path.exists(content_dir):
            for item in os.listdir(content_dir):
                item_path = os.path.join(content_dir, item)
                if os.path.isdir(item_path):
                    versions.append(item)
            versions = sorted(versions, reverse=True)

        self.version_combo['values'] = versions

        # If installer exists, also update it
        if self.installer and versions:
            if not self.version_var.get() or self.version_var.get() not in versions:
                self.version_combo.current(0)
                self._on_version_changed(None)
            else:
                # Reload resources with current version
                self._on_version_changed(None)

    def _on_version_changed(self, _event):
        """Handle version selection change"""
        version = self.version_var.get()
        if version and self.installer:
            self.current_version = version
            ensure_content_version_directories(init_external_content())
            self.installer.set_gtnh_version(version)
            self._load_all_resources()
            self._save_config()
            self.status_bar.set_status(f"已选择版本: {version}")
            logger.info(f"资源版本已设置: {version}")

    def _select_client_folder(self):
        """Open folder selection dialog for client"""
        folder = FolderSelectDialog.select_minecraft_folder(self.root)
        if folder:
            self._set_client_path(folder)
            self._save_config()

    def _select_server_folder(self):
        """Open folder selection dialog for server"""
        folder = FolderSelectDialog.select_minecraft_folder(self.root)
        if folder:
            self.server_path_var.set(folder)
            self._apply_server_path_from_entry()
            self._save_config()
            logger.info(f"服务端路径已设置: {folder}")

    def _apply_server_path_from_entry(self) -> bool:
        """Apply the currently entered server path to initialized components."""
        server_path = self.server_path_var.get().strip()
        if not server_path or not os.path.exists(server_path):
            return False

        if self.installer:
            self.installer.set_server_path(server_path)
        if self.backup_manager:
            self.backup_manager.set_server_path(server_path)
        return True

    def _set_client_path(self, path: str):
        """Set the client .minecraft path and initialize components"""
        self.client_path_var.set(path)
        self.mc_path = MinecraftPath(path)

        # Validate path
        valid, message = self.mc_path.validate()
        if not valid:
            messagebox.showerror("错误", f"无效的 .minecraft 目录: {message}")
            self.status_bar.set_status(f"错误: {message}")
            return

        # Initialize components
        self.installer = Installer(self.mc_path)
        self.backup_manager = BackupManager(path)
        self._apply_server_path_from_entry()

        # Refresh versions and load resources
        self._refresh_versions()

        self.status_bar.set_status(f"已加载: {path}")
        logger.info(f".minecraft 路径已设置: {path}")

    def _load_all_resources(self):
        """Load resources for all tabs"""
        if not self.installer or not self.current_version:
            return

        # Load mods
        mods = self.installer.load_resources(ResourceType.MOD)
        mod_data = self._prepare_resource_data(mods, ResourceType.MOD)
        self.mod_list.set_resources(mod_data)

        # Load scripts
        scripts = self.installer.load_resources(ResourceType.SCRIPT)
        script_data = self._prepare_resource_data(scripts, ResourceType.SCRIPT)
        self.script_list.set_resources(script_data)

        # Load configs
        configs = self.installer.load_resources(ResourceType.CONFIG)
        config_data = self._prepare_resource_data(configs, ResourceType.CONFIG)
        self.config_list.set_resources(config_data)

        # Load fonts
        fonts = self.installer.load_resources(ResourceType.FONT)
        font_data = self._prepare_resource_data(fonts, ResourceType.FONT)
        self.font_list.set_resources(font_data)

        # Load resourcepacks
        resourcepacks = self.installer.load_resources(ResourceType.RESOURCEPACK)
        resourcepack_data = self._prepare_resource_data(resourcepacks, ResourceType.RESOURCEPACK)
        self.resourcepack_list.set_resources(resourcepack_data)

        # Load shaderpacks
        shaderpacks = self.installer.load_resources(ResourceType.SHADERPACK)
        shaderpack_data = self._prepare_resource_data(shaderpacks, ResourceType.SHADERPACK)
        self.shaderpack_list.set_resources(shaderpack_data)

        # Load serverutilities
        serverutilities = self.installer.load_resources(ResourceType.SERVERUTILITIES)
        serverutilities_data = self._prepare_resource_data(serverutilities, ResourceType.SERVERUTILITIES)
        self.serverutilities_list.set_resources(serverutilities_data)

        # Load installed
        self._load_installed_resources()

    def _prepare_resource_data(self, resources, resource_type: ResourceType) -> List[dict]:
        """Prepare resource data for display"""
        data = []
        has_server = self.installer.server_mc_path is not None if self.installer else False

        for res in resources:
            install_status = self.installer.get_install_status(res.id, resource_type)
            client_installed = install_status["client"]
            server_installed = install_status["server"]
            is_installed = client_installed or server_installed

            size_str = self.installer._format_size(res.size) if res.size else ""

            # Build installation status text
            if has_server:
                if client_installed and server_installed:
                    status = '客户端+服务端'
                elif client_installed:
                    status = '仅客户端'
                elif server_installed:
                    status = '仅服务端'
                else:
                    status = '未安装'
            else:
                status = '已安装' if client_installed else '未安装'

            # Determine server_required display
            # MODs: use field from metadata
            # SCRIPTs, CONFIGs, SERVERUTILITIES: always show as required
            # FONTs, RESOURCEPACKs, SHADERPACKs: always show as not required
            if resource_type == ResourceType.MOD:
                server_required = res.server_required
            elif resource_type in [ResourceType.SCRIPT, ResourceType.CONFIG, ResourceType.SERVERUTILITIES]:
                server_required = True
            else:
                server_required = False

            data.append({
                'id': res.id,
                'name': res.name,
                'version': res.version or "",
                'mc_version': res.mc_version or "",
                'size': size_str,
                'server_required': server_required,
                'description': res.description or status,
                'installed': is_installed,
                'client_installed': client_installed,
                'server_installed': server_installed,
                'resource': res
            })
        return data

    def _load_installed_resources(self):
        """Load installed resources for the installed tab"""
        if not self.installer:
            return

        # Clear cache to force reload from installed.json
        self.installer.refresh_installed_cache()

        installed_data = []
        has_server = self.installer.server_mc_path is not None

        for item in self.installer.get_all_installed_resources():
            client_installed = item["client_installed"]
            server_installed = item["server_installed"]

            if has_server:
                if client_installed and server_installed:
                    status_desc = "客户端/服务端已安装"
                elif client_installed:
                    status_desc = "客户端已安装"
                elif server_installed:
                    status_desc = "服务端已安装"
                else:
                    status_desc = "未安装"
            else:
                status_desc = "已安装" if client_installed else "未安装"

            if item.get("missing"):
                status_desc += " (当前版本资源清单中不存在)"

            installed_data.append({
                'id': item['id'],
                'name': item['name'],
                'description': status_desc,
                'installed': True,
                'resource': item.get('resource'),
                'type': item['resource_type'].value
            })

        self.installed_list.set_resources(installed_data)

    def _on_tab_changed(self, _event):
        """Keep sidebar, title and context actions in sync."""
        index = self.notebook.index(self.notebook.select())
        self.page_title.configure(text=self.RESOURCE_TABS[index][1])
        for i, button in enumerate(self.nav_buttons):
            button.configure(style='Active.Nav.TButton' if i == index else 'Nav.TButton')
        installed = self.RESOURCE_TABS[index][2] is None
        self.uninstall_button.configure(state=tk.NORMAL if installed else tk.DISABLED)
        self.install_button.configure(state=tk.DISABLED if installed else tk.NORMAL)
        self._update_selection_count()

    def _get_current_list(self) -> ResourceListFrame:
        """Get the currently visible resource list"""
        tab_idx = self.notebook.index(self.notebook.select())
        lists = [
            getattr(self, f"{attr}_list")
            for attr, _label, _res_type in self.RESOURCE_TABS
        ]
        return lists[tab_idx] if tab_idx < len(lists) else self.mod_list

    def _get_current_resource_type(self) -> ResourceType:
        """Get resource type for current tab"""
        tab_idx = self.notebook.index(self.notebook.select())
        types = [
            res_type or ResourceType.MOD
            for _attr, _label, res_type in self.RESOURCE_TABS
        ]
        return types[tab_idx] if tab_idx < len(types) else ResourceType.MOD

    def _select_all(self):
        """Select all items in current list"""
        self._get_current_list().select_all()

    def _deselect_all(self):
        """Deselect all items in current list"""
        self._get_current_list().deselect_all()

    def _update_selection_count(self):
        """Update the selection count label"""
        if self.notebook.index(self.notebook.select()) == len(self.RESOURCE_TABS) - 1:
            selected = len(self.installed_list.get_selected_ids())
        else:
            selected = sum(len(getattr(self, f'{attr}_list').get_selected_ids())
                           for attr, _, kind in self.RESOURCE_TABS if kind is not None)
        self.selection_label.config(text=f"已选择: {selected} 项")

    def _create_backup(self):
        """Create a backup"""
        if not self.backup_manager:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

        self._apply_server_path_from_entry()

        # Determine backup type
        has_server = self.installer.server_mc_path is not None if self.installer else False

        if has_server:
            # Ask user what to backup
            dialog = tk.Toplevel(self.root)
            dialog.title("选择备份类型")
            dialog.transient(self.root)
            dialog.grab_set()

            result = ["all"]

            ttk.Label(dialog, text="请选择要备份的内容:").pack(padx=20, pady=10)

            ttk.Button(dialog, text="仅客户端", command=lambda: [result.__setitem__(0, "client"), dialog.destroy()]).pack(pady=5)
            ttk.Button(dialog, text="仅服务端", command=lambda: [result.__setitem__(0, "server"), dialog.destroy()]).pack(pady=5)
            ttk.Button(dialog, text="全部", command=lambda: [result.__setitem__(0, "all"), dialog.destroy()]).pack(pady=5)
            ttk.Button(dialog, text="取消", command=lambda: [result.__setitem__(0, None), dialog.destroy()]).pack(pady=5)

            dialog.wait_window()

            backup_type = result[0]
            if backup_type is None:
                return
        else:
            backup_type = "client"

        self.status_bar.set_status("正在创建备份...")
        self.root.update()

        success, message = self.backup_manager.create_backup(backup_type=backup_type)

        if success:
            messagebox.showinfo("成功", f"备份创建成功: {message}")
            logger.success(f"备份创建成功: {message}")
        else:
            messagebox.showerror("错误", message)
            logger.error(message)

        self.status_bar.set_status("就绪")

    def _show_backup_dialog(self):
        """Show backup management dialog"""
        if not self.backup_manager:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

        self._apply_server_path_from_entry()
        has_server = self.installer.server_mc_path is not None if self.installer else False
        BackupDialog(self.root, self.backup_manager, has_server, on_restore_callback=self._load_all_resources)

    def _install_selected(self):
        """Install selected resources"""
        if not self.installer:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

        # Collect selections from all tabs
        all_selected = []
        for attr, _label, res_type in self.RESOURCE_TABS:
            if res_type is None:
                continue
            res_list = getattr(self, f"{attr}_list")
            for res_id in res_list.get_selected_ids():
                all_selected.append((res_id, res_type))

        if not all_selected:
            messagebox.showwarning("警告", "请先选择要安装的资源")
            return

        # Ask install side
        install_side = self._ask_install_side()
        if not install_side:
            return

        # Check if all selected are server-incompatible types (fonts/resourcepacks/shaderpacks)
        if install_side == "server":
            server_incompatible = all(
                res_type in self.CLIENT_ONLY_TYPES
                for _, res_type in all_selected
            )
            if server_incompatible:
                messagebox.showwarning("提示", "字体、资源包和光影包无法安装在服务端")
                return

        # Confirm
        side_text = {"both": "双端", "client": "仅客户端", "server": "仅服务端"}.get(install_side, "双端")
        if not messagebox.askyesno("确认", f"确定要安装 {len(all_selected)} 个资源吗？\n安装方式: {side_text}"):
            return

        # Show progress dialog
        progress = ProgressDialog(self.root, "安装中", "正在安装资源...")
        progress.show()

        def update_progress(current, total, name):
            progress.update((current / total) * 100, f"正在安装: {name}")
            self.root.update()

        success_count, errors = self.installer.install_multiple(all_selected, update_progress, install_side=install_side)

        progress.close()

        if errors:
            messagebox.showwarning("完成", f"安装完成，成功: {success_count}，失败: {len(errors)}")
        else:
            messagebox.showinfo("成功", f"成功安装 {success_count} 个资源")

        # Generate installation list file
        if self.generate_list_var.get():
            self._save_install_list()

        # Refresh lists
        self._load_all_resources()
        self._deselect_all()

    def _ask_install_side(self) -> Optional[str]:
        """Ask user which side to install. Returns 'both', 'client', 'server', or None (cancelled)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择安装方式")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = [None]

        frame = ttk.Frame(dialog, padding=15)
        frame.pack()

        ttk.Label(frame, text="请选择安装方式:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        def on_choice(side):
            result[0] = side
            dialog.grab_release()
            dialog.destroy()

        ttk.Button(btn_frame, text="双端安装", command=lambda: on_choice("both")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="仅客户端", command=lambda: on_choice("client")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="仅服务端", command=lambda: on_choice("server")).pack(side=tk.LEFT, padx=5)

        dialog.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), dialog.grab_release(), dialog.destroy()))
        dialog.wait_window(dialog)
        return result[0]

    def _save_install_list(self):
        """Export what was actually installed, rather than the last checkbox selection."""
        from datetime import datetime
        from core.manifest import export_manifest
        from utils.helpers import atomic_json
        if not self.installer:
            messagebox.showwarning("生成清单", "请先选择已安装整合包的客户端目录。", parent=self.root)
            return
        try:
            data = export_manifest(self.installer)
            entries = [entry for items in data['resources'].values() for entry in items]
            if not entries and not data.get('client'):
                raise ValueError("当前客户端没有本工具记录的安装内容。")
            path = filedialog.asksaveasfilename(parent=self.root, title="保存整合包安装清单",
                defaultextension='.hflist', initialfile=f"GTNH_{datetime.now():%Y%m%d_%H%M%S}.hflist",
                filetypes=[("安装清单", "*.hflist")])
            if not path:
                return
            atomic_json(path, data)
            local = sum(not entry.get('download') for entry in entries)
            note = f"已保存 {len(entries)} 项已安装资源。"
            if data.get('client'):
                note += "\n已包含客户端固定下载链接，拖入清单可安装到空目录。"
            else:
                note += "\n未记录客户端来源，接收方需先准备对应版本的客户端。"
            if local:
                note += f"\n其中 {local} 项没有可用下载来源，接收方须具备相同的本地资源。"
            messagebox.showinfo("清单已生成", note, parent=self.root)
        except Exception as exc:
            messagebox.showerror("生成清单失败", str(exc), parent=self.root)

    def _load_install_list(self, file_path: str):
        from core.manifest import read_manifest, ManifestInstaller
        from gui.manifest import ManifestProgressDialog
        if self._manifest_busy:
            return
        self._manifest_busy = True
        service = None
        try:
            data = read_manifest(file_path)
            if data.get('client'):
                target = filedialog.askdirectory(parent=self.root, title="选择空目录安装清单中的完整客户端")
                server = None
            else:
                if not self.installer:
                    target = filedialog.askdirectory(parent=self.root, title="选择现有客户端 .minecraft 目录")
                else:
                    target = self.installer.mc_path.mc_path
                server = self.server_path_var.get().strip() or None
            if not target:
                return
            version = data['gtnh_version']
            library = os.path.join(init_external_content(), version)
            service = ManifestInstaller()
            dialog = ManifestProgressDialog(self.root, lambda cancel, report: service.install(
                data, target, library, cancel, report, server))
            self.root.wait_window(dialog)
            if dialog.error:
                messagebox.showerror("清单安装未完成", dialog.error + "\n完整客户端失败时不会发布暂存目录；已有客户端可能保留此前成功安装的资源。", parent=self.root)
            if dialog.result:
                self._adopt_downloaded_client(dialog.result, version)
                messagebox.showinfo("安装完成", "清单中的客户端与资源已安装。完整实例请通过对应启动器添加，并在游戏内启用资源包。", parent=self.root)
            elif self.installer:
                self.installer.refresh_installed_cache()
                self._load_all_resources()
        except Exception as exc:
            messagebox.showerror("清单安装失败", str(exc), parent=self.root)
        finally:
            if service:
                service.client.session.close()
            self._manifest_busy = False

    def _adopt_downloaded_client(self, path, version):
        os.makedirs(os.path.join(init_external_content(), version), exist_ok=True)
        self.version_var.set(version)
        self._set_client_path(path)
        self.version_var.set(version)
        self._on_version_changed(None)
        self._save_config()

    def _on_drop(self, event):
        """Handle file drop event"""
        # Get dropped files
        files = event.data
        if isinstance(files, str):
            # Parse dropped files (may be space or newline separated)
            # On Windows, paths may be enclosed in curly braces if they contain spaces
            files = self.root.tk.splitlist(files)

        for file_path in files:
            file_path = file_path.strip()
            if file_path.lower().endswith('.hflist'):
                self._load_install_list(file_path)
                break

    def _uninstall_selected(self):
        """Uninstall selected resources"""
        if not self.installer:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

        selected = self.installed_list.get_selected_ids()
        if not selected:
            messagebox.showwarning("警告", "请先选择要卸载的资源")
            return

        if not messagebox.askyesno("确认", f"确定要卸载 {len(selected)} 个资源吗？"):
            return

        success_count = 0
        errors = []
        for res_id in selected:
            item = self.installed_list.resource_items[res_id]
            success, message = self.installer.uninstall_resource(res_id, ResourceType(item['type']))
            if success:
                success_count += 1
            else:
                errors.append(message)

        if errors:
            messagebox.showwarning("卸载未全部完成", f"成功: {success_count}，失败: {len(errors)}\n" + "\n".join(errors))
        else:
            messagebox.showinfo("完成", f"成功卸载 {success_count} 个资源")

        # Refresh lists
        self._load_all_resources()
        self._deselect_all()

    def _initialize_mods(self):
        """Delete specific mod files from client and server mods folders"""
        # Mods to remove (case-insensitive matching)
        mods_to_remove = ['CraftPresence', 'darkerer', 'defaultserverlist', 'HardcoreDarkness']

        if not self.mc_path:
            messagebox.showwarning("警告", "请先选择客户端 .minecraft 文件夹")
            return

        removed_count = 0
        removed_files = []

        # Process client mods
        client_mods_dir = self.mc_path.get_mods_path()
        if client_mods_dir and os.path.exists(client_mods_dir):
            for f in os.listdir(client_mods_dir):
                if f.endswith('.jar'):
                    f_lower = f.lower()
                    for mod_name in mods_to_remove:
                        if mod_name.lower() in f_lower:
                            file_path = os.path.join(client_mods_dir, f)
                            try:
                                os.remove(file_path)
                                removed_count += 1
                                removed_files.append(f"[客户端] {f}")
                                logger.info(f"已删除: {f}")
                            except Exception as e:
                                logger.error(f"删除失败 {f}: {str(e)}")
                            break

        # Process server mods if path is set
        if self.installer and self.installer.server_mc_path:
            server_mods_dir = self.installer.server_mc_path.get_mods_path()
            if server_mods_dir and os.path.exists(server_mods_dir):
                for f in os.listdir(server_mods_dir):
                    if f.endswith('.jar'):
                        f_lower = f.lower()
                        for mod_name in mods_to_remove:
                            if mod_name.lower() in f_lower:
                                file_path = os.path.join(server_mods_dir, f)
                                try:
                                    os.remove(file_path)
                                    removed_count += 1
                                    removed_files.append(f"[服务端] {f}")
                                    logger.info(f"已删除: {f}")
                                except Exception as e:
                                    logger.error(f"删除失败 {f}: {str(e)}")
                                break

        if removed_count > 0:
            msg = f"已删除 {removed_count} 个模组文件:\n\n" + "\n".join(removed_files)
            messagebox.showinfo("初始化完成", msg)
        else:
            messagebox.showinfo("初始化完成", "未找到需要删除的模组文件")

        # Refresh lists
        self._load_all_resources()

    def _install_localization(self):
        """Install localization pack from 7z or zip archive"""
        if not self.mc_path:
            messagebox.showwarning("警告", "请先选择客户端 .minecraft 文件夹")
            return

        # Open file dialog to select archive
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="选择汉化压缩包",
            filetypes=[("压缩包文件", "*.7z *.zip"), ("7z文件", "*.7z"), ("ZIP文件", "*.zip"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        self.status_bar.set_status("正在安装汉化...")
        self.root.update()

        try:
            import zipfile
            import subprocess

            client_path = self.mc_path.mc_path
            extracted_count = 0

            if file_path.lower().endswith('.zip'):
                # Handle ZIP files
                with zipfile.ZipFile(file_path, 'r') as zf:
                    # Validate the entire archive before writing its first file.
                    for member in zf.namelist():
                        safe_child_path(client_path, member)
                    for member in zf.namelist():
                        # Skip directories
                        if member.endswith('/'):
                            continue
                        # Extract file
                        target_path = safe_child_path(client_path, member)
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zf.open(member) as source, open(target_path, 'wb') as target:
                            target.write(source.read())
                        extracted_count += 1
                        logger.info(f"已解压: {member}")

            elif file_path.lower().endswith('.7z'):
                # Handle 7z files using py7zr or 7z command
                try:
                    import py7zr
                    with py7zr.SevenZipFile(file_path, mode='r') as archive:
                        archive.extractall(path=client_path)
                        extracted_count = len(archive.getnames())
                        logger.info(f"已解压 7z 文件到: {client_path}")
                except ImportError:
                    # Fallback to 7z command line
                    try:
                        result = subprocess.run(
                            ['7z', 'x', file_path, f'-o{client_path}', '-y'],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if result.returncode == 0:
                            logger.info(f"已解压 7z 文件到: {client_path}")
                            extracted_count = result.stdout.count('\n')  # Rough count
                        else:
                            raise Exception(f"7z 解压失败: {result.stderr}")
                    except FileNotFoundError:
                        messagebox.showerror("错误", "解压 7z 文件需要安装 7-Zip 或 py7zr 库\n\n请运行: pip install py7zr")
                        return

            self.status_bar.set_status("就绪")
            messagebox.showinfo("成功", f"汉化安装完成！\n已解压 {extracted_count} 个文件")
            logger.success(f"汉化安装完成，解压了 {extracted_count} 个文件")

            # Refresh lists
            self._load_all_resources()

        except Exception as e:
            self.status_bar.set_status("就绪")
            logger.error(f"汉化安装失败: {str(e)}")
            messagebox.showerror("错误", f"汉化安装失败:\n{str(e)}")

    def _load_install_list_dialog(self):
        """Open file dialog to load installation list"""
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="加载安装清单",
            filetypes=[("安装清单文件", "*.hflist"), ("所有文件", "*.*")]
        )
        if file_path:
            self._load_install_list(file_path)

    def _setup_drag_drop(self):
        """Setup drag and drop support for .hflist files"""
        # Bind keyboard shortcut for paste (fallback method)
        self.root.bind('<Control-v>', self._on_paste_hflist)

        # Setup drag and drop if tkinterdnd2 is available
        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)

    def _on_paste_hflist(self, _event):
        """Handle Ctrl+V paste for .hflist file path"""
        try:
            clipboard = self.root.clipboard_get()
            if clipboard.lower().endswith('.hflist') and os.path.exists(clipboard):
                self._load_install_list(clipboard)
        except tk.TclError:
            pass

    def _create_download_menu(self, parent):
        menu = tk.Menu(parent, tearoff=0)
        menu.add_command(label="模组下载", command=self._show_online_mods)
        menu.add_command(label="客户端下载", command=lambda: self._show_downloads(True))
        menu.add_command(label="资源包下载", command=lambda: self._show_downloads(False))
        return menu

    def _show_downloads(self, game):
        version = self.version_var.get()
        content_dir = init_external_content()
        if not game and (not version or version not in os.listdir(content_dir)):
            messagebox.showwarning("请选择版本", "请先选择资源包保存的 GTNH 资源版本。")
            return
        dialog = DownloadsDialog(self.root, game, os.path.join(content_dir, version))
        self.root.wait_window(dialog)
        if dialog.installed_client:
            import re
            from core.manifest import CLIENT_RECEIPT
            receipt = load_json(os.path.join(dialog.installed_client, CLIENT_RECEIPT)) or {}
            match = re.search(r'_(\d+)\.(\d+)\.', receipt.get('name', ''))
            installed_version = f"{match[1]}.{match[2]}.X" if match else version
            self._adopt_downloaded_client(dialog.installed_client, installed_version)
            if self.generate_list_var.get():
                self._save_install_list()

        if dialog.changed:
            ResourceEditorDialog._invalidate_resources_cache(version)
            if self.installer:
                self._load_all_resources()

    def _show_online_mods(self):
        version = self.version_var.get()
        content_dir = init_external_content()
        if not version or version not in os.listdir(content_dir):
            messagebox.showwarning("请选择版本", "请先选择要保存下载资源的 GTNH 资源版本。")
            return
        dialog = OnlineModsDialog(
            self.root, os.path.join(content_dir, version),
            os.path.join(get_app_dir(), "wiki-mod-index.json"))
        self.root.wait_window(dialog)
        if dialog.changed:
            ResourceEditorDialog._invalidate_resources_cache(version)
            if self.installer:
                self._load_all_resources()

    def _open_wiki(self):
        """Open GTNH Chinese wiki page in browser"""
        webbrowser.open("https://gtnh.huijiwiki.com/wiki/%E5%8F%AF%E6%B7%BB%E5%8A%A0MOD")

    def _open_install_faq(self):
        """Open GTNH installation FAQ page in browser"""
        webbrowser.open("https://gtnh.huijiwiki.com/wiki/%E5%AE%89%E8%A3%85%E5%8F%8A%E6%9B%B4%E6%96%B0%E6%B8%B8%E6%88%8F#%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98")

    def _show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)

    def _on_resource_double_click(self, resource_id: str):
        """Handle double-click on a resource"""
        self._open_resource_editor(resource_id)

    def _show_context_menu(self, event, resource_id: str):
        """Show context menu on right-click"""
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="编辑此资源", command=lambda: self._open_resource_editor(resource_id))

        # Display menu at cursor position
        menu.post(event.x_root, event.y_root)

    def _open_resource_editor(self, resource_id: str = None):
        """Open the resource editor dialog"""
        if not self.current_version:
            messagebox.showwarning("警告", "请先选择资源版本")
            return

        res_type = self._get_current_resource_type()

        # Get client and server paths for uninstalling old files during update
        client_path = self.mc_path.mc_path if self.mc_path else None
        server_path = self.installer.server_mc_path.mc_path if (self.installer and self.installer.server_mc_path) else None

        ResourceEditorDialog(
            self.root,
            gtnh_version=self.current_version,
            initial_type=res_type.value,
            initial_id=resource_id,
            client_path=client_path,
            server_path=server_path
        )

        # Refresh resources after editor closes
        self._load_all_resources()

    def run(self):
        """Start the application"""
        self.root.mainloop()
