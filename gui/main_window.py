"""
Main window for GTNH Mod Installer GUI
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, List, Tuple
import os
import sys
import webbrowser

from gui.widgets import ResourceListFrame, LogFrame, StatusBar, ProgressDialog
from gui.dialogs import FolderSelectDialog, BackupDialog, AboutDialog
from gui.resource_editor import ResourceEditorDialog
from core.minecraft import MinecraftPath
from core.installer import Installer, ResourceType
from core.backup import BackupManager
from utils.logger import logger
from utils.helpers import load_json, save_json, get_app_dir, init_external_content, is_frozen

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


class MainWindow:
    """Main application window"""

    TITLE = "GTNH 私货安装器 v1.0"

    def __init__(self):
        # Use TkinterDnD.Tk() if available, otherwise fallback to tk.Tk()
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        self.root.title(self.TITLE)
        self.root.geometry("900x900")
        self.root.minsize(700, 500)

        # Set window icon
        self._set_window_icon()

        # Core components
        self.mc_path: Optional[MinecraftPath] = None
        self.installer: Optional[Installer] = None
        self.backup_manager: Optional[BackupManager] = None
        self.current_version: str = ""

        # Generate list flag
        self.generate_list_var = tk.BooleanVar(value=True)

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
        file_menu.add_checkbutton(label="安装后生成清单", variable=self.generate_list_var)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="备份管理", command=self._show_backup_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="中文维基私货页面", command=self._open_wiki)
        tools_menu.add_command(label="安装常见问题", command=self._open_install_faq)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        """Create main widgets"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Path selection
        path_frame = ttk.LabelFrame(main_frame, text="路径设置", padding=5)
        path_frame.pack(fill=tk.X, pady=5)

        # Client path
        ttk.Label(path_frame, text="客户端路径:").grid(row=0, column=0, sticky=tk.W)
        self.client_path_var = tk.StringVar()
        self.client_path_entry = ttk.Entry(path_frame, textvariable=self.client_path_var, width=45)
        self.client_path_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
        ttk.Button(path_frame, text="选择...", command=self._select_client_folder).grid(row=0, column=2)

        # Server path
        ttk.Label(path_frame, text="服务端路径:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.server_path_var = tk.StringVar()
        self.server_path_entry = ttk.Entry(path_frame, textvariable=self.server_path_var, width=45)
        self.server_path_entry.grid(row=1, column=1, padx=5, sticky=tk.EW, pady=(5, 0))
        ttk.Button(path_frame, text="选择...", command=self._select_server_folder).grid(row=1, column=2, pady=(5, 0))

        # Version selection
        ttk.Label(path_frame, text="资源版本:").grid(row=0, column=3, padx=(20, 0), sticky=tk.W)
        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(path_frame, textvariable=self.version_var, width=12, state='readonly')
        self.version_combo.grid(row=0, column=4, padx=5)
        self.version_combo.bind('<<ComboboxSelected>>', self._on_version_changed)
        ttk.Button(path_frame, text="刷新版本", command=self._refresh_versions).grid(row=0, column=5, padx=5)

        path_frame.columnconfigure(1, weight=1)

        # Tab notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create tabs
        self.mod_frame = ttk.Frame(self.notebook)
        self.script_frame = ttk.Frame(self.notebook)
        self.config_frame = ttk.Frame(self.notebook)
        self.font_frame = ttk.Frame(self.notebook)
        self.resourcepack_frame = ttk.Frame(self.notebook)
        self.installed_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.mod_frame, text="模组")
        self.notebook.add(self.script_frame, text="脚本")
        self.notebook.add(self.config_frame, text="配置")
        self.notebook.add(self.font_frame, text="字体")
        self.notebook.add(self.resourcepack_frame, text="资源包")
        self.notebook.add(self.installed_frame, text="已安装")

        # Resource list frames for each tab
        self.mod_list = ResourceListFrame(
            self.mod_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.mod_list.pack(fill=tk.BOTH, expand=True)

        self.script_list = ResourceListFrame(
            self.script_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.script_list.pack(fill=tk.BOTH, expand=True)

        self.config_list = ResourceListFrame(
            self.config_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.config_list.pack(fill=tk.BOTH, expand=True)

        self.font_list = ResourceListFrame(
            self.font_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.font_list.pack(fill=tk.BOTH, expand=True)

        self.resourcepack_list = ResourceListFrame(
            self.resourcepack_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.resourcepack_list.pack(fill=tk.BOTH, expand=True)

        # Installed tab - no double-click/right-click callbacks
        self.installed_list = ResourceListFrame(
            self.installed_frame,
            on_select_callback=self._update_selection_count,
            columns=ResourceListFrame.COLUMNS_INSTALLED
        )
        self.installed_list.pack(fill=tk.BOTH, expand=True)

        # Bind tab change
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        # Selection buttons
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Button(select_frame, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="取消全选", command=self._deselect_all).pack(side=tk.LEFT, padx=5)

        self.selection_label = ttk.Label(select_frame, text="已选择: 0 项")
        self.selection_label.pack(side=tk.RIGHT, padx=10)

        # Action buttons
        action_frame = ttk.LabelFrame(main_frame, text="操作", padding=5)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="备份当前", command=self._create_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="还原备份", command=self._show_backup_dialog).pack(side=tk.LEFT, padx=5)

        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(action_frame, text="安装选中", command=self._install_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="卸载选中", command=self._uninstall_selected).pack(side=tk.LEFT, padx=5)

        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(action_frame, text="加载清单", command=self._load_install_list_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="编辑资源", command=self._open_resource_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="初始化", command=self._initialize_mods).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="汉化安装", command=self._install_localization).pack(side=tk.LEFT, padx=5)

        # Drop zone for .hflist files
        drop_frame = ttk.LabelFrame(main_frame, text="安装清单 (可将 .hflist 文件拖入此区域)", padding=10)
        drop_frame.pack(fill=tk.X, pady=5)

        self.drop_label = ttk.Label(drop_frame, text="将 .hflist 清单文件拖放到此处，或点击上方【加载清单】按钮",
                                    anchor=tk.CENTER, font=('Arial', 10))
        self.drop_label.pack(fill=tk.X, pady=10)

        # Bind click on drop zone
        drop_frame.bind('<Button-1>', lambda _: self._load_install_list_dialog())
        self.drop_label.bind('<Button-1>', lambda _: self._load_install_list_dialog())

        # Status bar
        self.status_bar = StatusBar(main_frame)
        self.status_bar.pack(fill=tk.X, pady=5)

        # Log frame
        self.log_frame = LogFrame(main_frame)
        self.log_frame.pack(fill=tk.X, pady=5)

        # Initialize version list
        self._refresh_versions()

    def _setup_logger(self):
        """Setup logger with GUI callback"""
        def log_callback(message: str):
            self.log_frame.append_log(message)

        logger.set_gui_callback(log_callback)

    def _load_config(self):
        """Load saved config"""
        config_path = os.path.join(get_app_dir(), 'config.json')
        config = load_json(config_path)
        if config:
            missing_paths = []
            if 'client_path' in config and config['client_path']:
                if os.path.exists(config['client_path']):
                    self.client_path_var.set(config['client_path'])
                    self._set_client_path(config['client_path'])
                else:
                    self.client_path_var.set('')
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
                    missing_paths.append(f"服务端路径: {config['server_path']}")
            if missing_paths:
                messagebox.showwarning("路径不存在", "以下路径不存在，已清除:\n\n" + "\n".join(missing_paths))
            if 'last_version' in config:
                self.version_var.set(config['last_version'])
                self._on_version_changed(None)

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
            if self.installer:
                self.installer.set_server_path(folder)
            if self.backup_manager:
                self.backup_manager.set_server_path(folder)
            self._save_config()
            logger.info(f"服务端路径已设置: {folder}")

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
            # SCRIPTs, CONFIGs: always show as required
            # FONTs, RESOURCEPACKs: always show as not required
            if resource_type == ResourceType.MOD:
                server_required = res.server_required
            elif resource_type in [ResourceType.SCRIPT, ResourceType.CONFIG]:
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

        for res_type in [ResourceType.MOD, ResourceType.SCRIPT, ResourceType.CONFIG,
                         ResourceType.FONT, ResourceType.RESOURCEPACK]:
            resources = self.installer.load_resources(res_type)

            for res in resources:
                install_status = self.installer.get_install_status(res.id, res_type)
                client_installed = install_status["client"]
                server_installed = install_status["server"]

                if client_installed or server_installed:
                    # Build description based on installation status
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

                    installed_data.append({
                        'id': res.id,
                        'name': res.name,
                        'description': status_desc,
                        'installed': True,
                        'resource': res,
                        'type': res_type.value
                    })

        self.installed_list.set_resources(installed_data)

    def _on_tab_changed(self, _event):
        """Handle tab change event"""
        self._update_selection_count()

    def _get_current_list(self) -> ResourceListFrame:
        """Get the currently visible resource list"""
        tab_idx = self.notebook.index(self.notebook.select())
        lists = [self.mod_list, self.script_list, self.config_list,
                 self.font_list, self.resourcepack_list, self.installed_list]
        return lists[tab_idx] if tab_idx < len(lists) else self.mod_list

    def _get_current_resource_type(self) -> ResourceType:
        """Get resource type for current tab"""
        tab_idx = self.notebook.index(self.notebook.select())
        types = [ResourceType.MOD, ResourceType.SCRIPT, ResourceType.CONFIG,
                 ResourceType.FONT, ResourceType.RESOURCEPACK, ResourceType.MOD]
        return types[tab_idx] if tab_idx < len(types) else ResourceType.MOD

    def _select_all(self):
        """Select all items in current list"""
        self._get_current_list().select_all()

    def _deselect_all(self):
        """Deselect all items in current list"""
        self._get_current_list().deselect_all()

    def _update_selection_count(self):
        """Update the selection count label"""
        selected = len(self._get_current_list().get_selected_ids())
        self.selection_label.config(text=f"已选择: {selected} 项")

    def _create_backup(self):
        """Create a backup"""
        if not self.backup_manager:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

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

        has_server = self.installer.server_mc_path is not None if self.installer else False
        BackupDialog(self.root, self.backup_manager, has_server, on_restore_callback=self._load_all_resources)

    def _install_selected(self):
        """Install selected resources"""
        if not self.installer:
            messagebox.showwarning("警告", "请先选择 .minecraft 文件夹")
            return

        # Collect selections from all tabs
        all_selected = []
        for res_list, res_type in [
            (self.mod_list, ResourceType.MOD),
            (self.script_list, ResourceType.SCRIPT),
            (self.config_list, ResourceType.CONFIG),
            (self.font_list, ResourceType.FONT),
            (self.resourcepack_list, ResourceType.RESOURCEPACK)
        ]:
            for res_id in res_list.get_selected_ids():
                all_selected.append((res_id, res_type))

        if not all_selected:
            messagebox.showwarning("警告", "请先选择要安装的资源")
            return

        # Ask install side
        install_side = self._ask_install_side()
        if not install_side:
            return

        # Check if all selected are server-incompatible types (fonts/resourcepacks)
        if install_side == "server":
            server_incompatible = all(
                res_type in [ResourceType.FONT, ResourceType.RESOURCEPACK]
                for _, res_type in all_selected
            )
            if server_incompatible:
                messagebox.showwarning("提示", "字体和资源包无法安装在服务端")
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
            self._save_install_list(all_selected)

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

    def _save_install_list(self, selected_items: List[Tuple[str, ResourceType]]):
        """Save installation list to .hflist file"""
        from datetime import datetime

        # Group by type
        list_data = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "gtnh_version": self.version_var.get(),
            "resources": {
                "mods": [],
                "scripts": [],
                "configs": [],
                "fonts": [],
                "resourcepacks": []
            }
        }

        for res_id, res_type in selected_items:
            type_key = res_type.value
            if type_key in list_data["resources"]:
                list_data["resources"][type_key].append(res_id)

        # Ask user for save location
        from tkinter import filedialog
        default_name = f"install_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.hflist"
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="保存安装清单",
            defaultextension=".hflist",
            initialfile=default_name,
            filetypes=[("安装清单文件", "*.hflist"), ("所有文件", "*.*")]
        )

        if file_path:
            save_json(file_path, list_data)
            logger.success(f"安装清单已保存: {file_path}")

    def _load_install_list(self, file_path: str):
        """Load installation list from .hflist file and apply"""
        if not self.installer:
            messagebox.showwarning("警告", "请先选择客户端 .minecraft 文件夹")
            return

        list_data = load_json(file_path)
        if not list_data:
            messagebox.showerror("错误", "无法读取安装清单文件")
            return

        # Check version compatibility
        list_version = list_data.get("gtnh_version", "")
        current_version = self.version_var.get()

        if list_version and list_version != current_version:
            if not messagebox.askyesno("版本不匹配",
                f"清单版本: {list_version}\n当前版本: {current_version}\n\n是否继续安装？"):
                return

        # Collect resources to install
        all_selected = []
        resources = list_data.get("resources", {})

        for type_key, res_ids in resources.items():
            try:
                res_type = ResourceType(type_key)
                for res_id in res_ids:
                    all_selected.append((res_id, res_type))
            except ValueError:
                continue

        if not all_selected:
            messagebox.showwarning("警告", "清单中没有可安装的资源")
            return

        # Show progress dialog
        progress = ProgressDialog(self.root, "安装中", "正在从清单安装资源...")
        progress.show()

        def update_progress(current, total, name):
            progress.update((current / total) * 100, f"正在安装: {name}")
            self.root.update()

        success_count, errors = self.installer.install_multiple(all_selected, update_progress)

        progress.close()

        if errors:
            messagebox.showwarning("完成", f"安装完成，成功: {success_count}，失败: {len(errors)}")
        else:
            messagebox.showinfo("成功", f"成功安装 {success_count} 个资源")

        # Refresh lists
        self._load_all_resources()

    def _on_drop(self, event):
        """Handle file drop event"""
        # Get dropped files
        files = event.data
        if isinstance(files, str):
            # Parse dropped files (may be space or newline separated)
            # On Windows, paths may be enclosed in curly braces if they contain spaces
            files = files.replace('{', '').replace('}', '').split()

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

        # Try to uninstall as each type
        success_count = 0
        for res_id in selected:
            for res_type in [ResourceType.MOD, ResourceType.SCRIPT, ResourceType.CONFIG,
                             ResourceType.FONT, ResourceType.RESOURCEPACK]:
                success, _ = self.installer.uninstall_resource(res_id, res_type)
                if success:
                    success_count += 1
                    break

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
                    for member in zf.namelist():
                        # Skip directories
                        if member.endswith('/'):
                            continue
                        # Extract file
                        source = zf.open(member)
                        target_path = os.path.join(client_path, member)
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as target:
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
        self.root.bind('<FocusIn>', self._on_focus_in)

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

    def _on_focus_in(self, _event):
        """Check clipboard for .hflist file path when window gets focus"""
        try:
            clipboard = self.root.clipboard_get()
            if clipboard.lower().endswith('.hflist') and os.path.exists(clipboard):
                self._load_install_list(clipboard)
                self.root.clipboard_clear()
        except:
            pass

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
