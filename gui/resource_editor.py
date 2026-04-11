"""
Resource Editor Dialog for GTNH Mod Installer GUI
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Optional, Dict, List
import os
import re
import shutil

from utils.helpers import load_json, save_json, get_app_dir, init_external_content
from utils.logger import logger


class ResourceEditorDialog(tk.Toplevel):
    """Dialog for editing resource metadata"""

    RESOURCE_TYPES = ['mods', 'scripts', 'configs', 'fonts', 'resourcepacks']

    def __init__(self, parent, gtnh_version: str = "",
                 initial_type: str = "mods",
                 initial_id: str = None,
                 client_path: str = None,
                 server_path: str = None):
        """
        Args:
            parent: Parent window
            gtnh_version: Initial GTNH version to edit
            initial_type: Initial resource type to show
            initial_id: Initial resource ID to select
            client_path: Client .minecraft path for uninstalling old files
            server_path: Server .minecraft path for uninstalling old files
        """
        super().__init__(parent)
        self.title("资源编辑器")
        self.parent = parent

        # State
        self.current_version = gtnh_version
        self.current_type = initial_type
        self.resources_data: Dict[str, List[dict]] = {}
        self.selected_id: Optional[str] = initial_id
        self._displayed_ids: List[str] = []
        self._original_filename: Optional[str] = None  # Track original filename for rename
        self.client_path = client_path
        self.server_path = server_path

        # Build UI
        self._create_widgets()
        self._update_server_install_label()  # Set initial label text
        self._load_versions()
        self._center_window()

        # Load initial data
        if self.current_version:
            self._load_resources()

        # Wait for window to close before returning
        self.wait_window(self)

    def _center_window(self):
        """Center the dialog on parent"""
        self.transient(self.parent)
        self.grab_set()
        self.update_idletasks()

        width = 700
        height = 500
        x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        """Create all widgets"""
        # Top frame for version selection
        top_frame = ttk.Frame(self, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="版本:").pack(side=tk.LEFT)
        self.version_var = tk.StringVar()
        self.version_combo = ttk.Combobox(top_frame, textvariable=self.version_var,
                                           width=12, state='readonly')
        self.version_combo.pack(side=tk.LEFT, padx=5)
        self.version_combo.bind('<<ComboboxSelected>>', self._on_version_changed)

        # Main content frame (left-right split)
        content_frame = ttk.Frame(self, padding=5)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel: file list
        self._create_left_panel(content_frame)

        # Right panel: edit form
        self._create_right_panel(content_frame)

        # Configure column weights
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

    def _create_left_panel(self, parent):
        """Create left panel with file list"""
        left_frame = ttk.LabelFrame(parent, text="资源列表", padding=5)
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 5))

        # Type selection
        ttk.Label(left_frame, text="类型:").pack(anchor=tk.W)
        self.type_var = tk.StringVar(value=self.current_type)
        self.type_combo = ttk.Combobox(left_frame, textvariable=self.type_var,
                                        values=self.RESOURCE_TYPES, width=15, state='readonly')
        self.type_combo.pack(fill=tk.X, pady=(0, 5))
        self.type_combo.bind('<<ComboboxSelected>>', self._on_type_changed)

        # File list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(list_frame, height=15)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                   command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        # Add button
        ttk.Button(left_frame, text="添加新资源", command=self._add_new_resource).pack(fill=tk.X, pady=(5, 0))

    def _create_right_panel(self, parent):
        """Create right panel with edit form"""
        right_frame = ttk.LabelFrame(parent, text="编辑区", padding=10)
        right_frame.grid(row=0, column=1, sticky=tk.NSEW)

        # Form fields
        form_frame = ttk.Frame(right_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # ID field
        ttk.Label(form_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.id_var = tk.StringVar()
        self.id_entry = ttk.Entry(form_frame, textvariable=self.id_var, width=40)
        self.id_entry.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # Filename field
        ttk.Label(form_frame, text="文件名:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.filename_var = tk.StringVar()
        self.filename_entry = ttk.Entry(form_frame, textvariable=self.filename_var, width=40)
        self.filename_entry.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # Name field
        ttk.Label(form_frame, text="显示名称:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(form_frame, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=2, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # Version field
        ttk.Label(form_frame, text="版本:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.res_version_var = tk.StringVar()
        self.res_version_entry = ttk.Entry(form_frame, textvariable=self.res_version_var, width=40)
        self.res_version_entry.grid(row=3, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # MC Version field
        ttk.Label(form_frame, text="适配版本:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.mc_version_var = tk.StringVar()
        self.mc_version_entry = ttk.Entry(form_frame, textvariable=self.mc_version_var, width=40)
        self.mc_version_entry.grid(row=4, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # Description field
        ttk.Label(form_frame, text="说明:").grid(row=5, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(form_frame, width=40, height=6)
        self.desc_text.grid(row=5, column=1, sticky=tk.NSEW, pady=2, padx=(5, 0))

        form_frame.columnconfigure(1, weight=1)
        form_frame.rowconfigure(5, weight=1)

        # Server required checkbox (for mods only)
        self.server_required_var = tk.BooleanVar(value=False)
        self.server_required_check = ttk.Checkbutton(right_frame, text="服务端需装",
                                                       variable=self.server_required_var)
        # Will be shown/hidden based on resource type

        # Server install info label
        self.server_install_label = ttk.Label(right_frame, text="")
        self.server_install_label.pack(anchor=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="保存", command=self._save_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="更新文件", command=self._update_resource_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除", command=self._delete_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_close).pack(side=tk.RIGHT, padx=5)

    def _load_versions(self):
        """Load available GTNH versions"""
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

        if self.current_version and self.current_version in versions:
            self.version_var.set(self.current_version)
        elif versions:
            self.version_combo.current(0)
            self.current_version = versions[0]

    def _on_version_changed(self, _event):
        """Handle version selection change"""
        self.current_version = self.version_var.get()
        self._load_resources()

    def _on_type_changed(self, _event):
        """Handle resource type change"""
        self.current_type = self.type_var.get()
        self._update_server_install_label()
        self._load_resources()

    def _update_server_install_label(self):
        """Update server install info label based on current type"""
        # Mods: show checkbox for server_required
        # Scripts, configs: always install on both
        # Fonts, resourcepacks: client only
        if self.current_type == 'mods':
            self.server_install_label.config(text="📁 模组根据\"服务端需装\"选项决定是否安装到服务端")
            # Show checkbox for mods (pack before label)
            self.server_required_check.pack(before=self.server_install_label, anchor=tk.W, pady=5)
        elif self.current_type in ['scripts', 'configs']:
            self.server_install_label.config(text="📁 此类型资源会安装到客户端和服务端")
            # Hide checkbox for scripts/configs (always server)
            self.server_required_check.pack_forget()
        else:
            self.server_install_label.config(text="📁 此类型资源仅安装到客户端")
            # Hide checkbox for fonts/resourcepacks (client only)
            self.server_required_check.pack_forget()

    def _load_resources(self):
        """Load resources for current version and type"""
        if not self.current_version:
            return

        # Load resources.json
        content_dir = init_external_content()
        json_path = os.path.join(content_dir, self.current_version, "resources.json")
        self.resources_data = load_json(json_path) or {
            "mods": [], "scripts": [], "configs": [], "fonts": [], "resourcepacks": []
        }

        # Ensure all keys exist
        for key in self.RESOURCE_TYPES:
            if key not in self.resources_data:
                self.resources_data[key] = []

        self._refresh_file_list()

    def _refresh_file_list(self):
        """Refresh the file listbox"""
        self.file_listbox.delete(0, tk.END)

        if not self.current_version:
            return

        content_dir = init_external_content()

        # Get actual items (files and directories) in type directory
        type_dir = os.path.join(content_dir, self.current_version, self.current_type)
        actual_items = set()
        if os.path.exists(type_dir):
            for f in os.listdir(type_dir):
                item_path = os.path.join(type_dir, f)
                if os.path.isfile(item_path) or os.path.isdir(item_path):
                    actual_items.add(f)

        # Get resources with metadata
        resources = self.resources_data.get(self.current_type, [])
        resources_by_filename = {r.get('filename'): r for r in resources}

        # Display: items with metadata first (marked with ☑)
        displayed_ids = []
        for res in resources:
            filename = res.get('filename', '')
            marker = '☑' if filename in actual_items else '☑⚠'  # item missing
            self.file_listbox.insert(tk.END, f"{marker} {res.get('id', '')} ({filename})")
            displayed_ids.append(res.get('id'))

        # Then items without metadata (marked with ☐)
        for filename in sorted(actual_items):
            if filename not in resources_by_filename:
                self.file_listbox.insert(tk.END, f"☐ {filename}")
                displayed_ids.append(filename)

        self._displayed_ids = displayed_ids

        # Select initial item if provided
        if self.selected_id and self.selected_id in displayed_ids:
            idx = displayed_ids.index(self.selected_id)
            self.file_listbox.selection_set(idx)
            self._load_resource_to_form(self.selected_id)
            self.selected_id = None

    def _on_file_select(self, _event):
        """Handle file selection in listbox"""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < len(self._displayed_ids):
            resource_id = self._displayed_ids[idx]
            self._load_resource_to_form(resource_id)

    def _load_resource_to_form(self, resource_id: str):
        """Load resource data into form"""
        # Find resource by ID or filename
        resources = self.resources_data.get(self.current_type, [])
        resource = None
        for r in resources:
            if r.get('id') == resource_id or r.get('filename') == resource_id:
                resource = r
                break

        if resource:
            self._original_filename = resource.get('filename', '')
            self.id_var.set(resource.get('id', ''))
            self.filename_var.set(resource.get('filename', ''))
            self.name_var.set(resource.get('name', ''))
            self.res_version_var.set(resource.get('version', ''))
            self.mc_version_var.set(resource.get('mc_version', ''))
            self.desc_text.delete(1.0, tk.END)
            self.desc_text.insert(tk.END, resource.get('description', ''))
            # Only load server_required for mods
            if self.current_type == 'mods':
                self.server_required_var.set(resource.get('server_required', False))
            else:
                self.server_required_var.set(False)
        else:
            # New file without metadata - use filename as starting point
            self._original_filename = resource_id  # resource_id is the filename for new files
            self.id_var.set(self._generate_id_from_filename(resource_id))
            self.filename_var.set(resource_id)
            self.name_var.set('')
            self.res_version_var.set('')
            self.mc_version_var.set('')
            self.desc_text.delete(1.0, tk.END)
            self.server_required_var.set(False)

    def _generate_id_from_filename(self, filename: str) -> str:
        """Generate a resource ID from filename"""
        # Remove extension
        name = os.path.splitext(filename)[0]
        # Replace spaces and special chars with dashes
        name = re.sub(r'[^a-zA-Z0-9_-]', '-', name)
        return name.strip('-')

    def _add_new_resource(self):
        """Add a new resource entry"""
        filename = simpledialog.askstring("添加新资源", "输入文件名:", parent=self)
        if not filename or not filename.strip():
            return

        filename = filename.strip()

        # Check if already exists
        resources = self.resources_data.get(self.current_type, [])
        for r in resources:
            if r.get('filename') == filename or r.get('id') == filename:
                messagebox.showwarning("警告", f"资源 '{filename}' 已存在", parent=self)
                return

        # Generate ID and add to list
        new_id = self._generate_id_from_filename(filename)
        self.resources_data.setdefault(self.current_type, []).append({
            'id': new_id,
            'filename': filename,
            'name': filename,
            'version': '',
            'mc_version': '',
            'description': '',
            'server_required': False
        })

        self._refresh_file_list()

        # Select the new item
        for i, rid in enumerate(self._displayed_ids):
            if rid == new_id:
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(i)
                self._load_resource_to_form(new_id)
                break

    def _save_resource(self):
        """Save current form data to resources"""
        resource_id = self.id_var.get().strip()
        new_filename = self.filename_var.get().strip()

        if not resource_id:
            messagebox.showwarning("警告", "ID 不能为空", parent=self)
            return
        if not new_filename:
            messagebox.showwarning("警告", "文件名不能为空", parent=self)
            return

        # Get form data
        name = self.name_var.get().strip()
        version = self.res_version_var.get().strip()
        mc_version = self.mc_version_var.get().strip()
        description = self.desc_text.get(1.0, tk.END).strip()
        server_required = self.server_required_var.get()

        # Use tracked original filename for rename and lookup
        original_filename = self._original_filename
        resources = self.resources_data.get(self.current_type, [])

        # Rename file on disk if filename changed
        if original_filename and original_filename != new_filename:
            content_dir = init_external_content()
            type_dir = os.path.join(content_dir, self.current_version, self.current_type)
            old_path = os.path.join(type_dir, original_filename)
            new_path = os.path.join(type_dir, new_filename)

            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    os.rename(old_path, new_path)
                    logger.info(f"已重命名文件: {original_filename} -> {new_filename}")
                except Exception as e:
                    logger.error(f"重命名文件失败: {str(e)}")
                    messagebox.showwarning("警告", f"文件重命名失败: {str(e)}", parent=self)

        # Find and update resource - use original_filename for lookup
        found = False

        # Build resource data - only include server_required for mods
        resource_data = {
            'id': resource_id,
            'filename': new_filename,
            'name': name or new_filename,
            'version': version,
            'mc_version': mc_version,
            'description': description
        }
        if self.current_type == 'mods':
            resource_data['server_required'] = server_required

        for i, r in enumerate(resources):
            if r.get('filename') == original_filename or r.get('id') == resource_id:
                resources[i] = resource_data
                found = True
                break

        if not found:
            # Add new
            resources.append(resource_data)

        # Update tracked original filename
        self._original_filename = new_filename

        self.resources_data[self.current_type] = resources

        # Save to file
        self._save_to_file()

        # Refresh list
        self._refresh_file_list()

        messagebox.showinfo("成功", "资源已保存", parent=self)

    def _update_resource_file(self):
        """Update resource file with a new file, preserving id, name and description"""
        resource_id = self.id_var.get().strip()
        old_filename = self.filename_var.get().strip()

        if not resource_id:
            messagebox.showwarning("警告", "请先选择一个资源", parent=self)
            return

        # Open file dialog to select new file
        file_path = filedialog.askopenfilename(
            parent=self,
            title="选择新文件",
            filetypes=[("所有文件", "*.*"), ("JAR文件", "*.jar"), ("ZIP文件", "*.zip"), ("脚本文件", "*.zs")]
        )

        if not file_path:
            return

        new_filename = os.path.basename(file_path)

        # Get current type directory
        content_dir = init_external_content()
        type_dir = os.path.join(content_dir, self.current_version, self.current_type)

        # Track deleted files for user notification
        deleted_files = []

        # Delete old file from Addcontent if exists
        if old_filename:
            old_file_path = os.path.join(type_dir, old_filename)
            if os.path.exists(old_file_path):
                try:
                    if os.path.isdir(old_file_path):
                        shutil.rmtree(old_file_path)
                    else:
                        os.remove(old_file_path)
                    logger.info(f"已删除旧资源文件: {old_filename}")
                except Exception as e:
                    logger.error(f"删除旧资源文件失败: {str(e)}")

            # Delete old file from client .minecraft
            if self.client_path:
                client_type_dir = os.path.join(self.client_path, self.current_type)
                if client_type_dir and os.path.exists(client_type_dir):
                    old_client_file = os.path.join(client_type_dir, old_filename)
                    if os.path.exists(old_client_file):
                        try:
                            if os.path.isdir(old_client_file):
                                shutil.rmtree(old_client_file)
                            else:
                                os.remove(old_client_file)
                            deleted_files.append(f"[客户端] {old_filename}")
                            logger.info(f"已从客户端卸载: {old_filename}")
                        except Exception as e:
                            logger.error(f"从客户端卸载失败: {str(e)}")

            # Delete old file from server .minecraft
            if self.server_path:
                server_type_dir = os.path.join(self.server_path, self.current_type)
                if server_type_dir and os.path.exists(server_type_dir):
                    old_server_file = os.path.join(server_type_dir, old_filename)
                    if os.path.exists(old_server_file):
                        try:
                            if os.path.isdir(old_server_file):
                                shutil.rmtree(old_server_file)
                            else:
                                os.remove(old_server_file)
                            deleted_files.append(f"[服务端] {old_filename}")
                            logger.info(f"已从服务端卸载: {old_filename}")
                        except Exception as e:
                            logger.error(f"从服务端卸载失败: {str(e)}")

        # Copy new file
        new_dest_path = os.path.join(type_dir, new_filename)
        try:
            import shutil
            shutil.copy2(file_path, new_dest_path)
            logger.info(f"已复制新文件: {new_filename}")
        except Exception as e:
            messagebox.showerror("错误", f"复制文件失败: {str(e)}", parent=self)
            return

        # Parse version from filename
        new_version = self._parse_version_from_filename(new_filename)
        new_mc_version = self._parse_mc_version_from_filename(new_filename)

        # Keep id, name, description, server_required; update filename and version
        saved_id = self.id_var.get().strip()
        saved_name = self.name_var.get().strip()
        saved_description = self.desc_text.get(1.0, tk.END).strip()
        saved_server_required = self.server_required_var.get()

        # Update filename in form
        self.filename_var.set(new_filename)
        self.res_version_var.set(new_version)
        self.mc_version_var.set(new_mc_version)

        # Update resources data
        resources = self.resources_data.get(self.current_type, [])
        found = False

        for i, r in enumerate(resources):
            if r.get('id') == saved_id:
                resources[i] = {
                    'id': saved_id,
                    'filename': new_filename,
                    'name': saved_name or new_filename,
                    'version': new_version,
                    'mc_version': new_mc_version,
                    'description': saved_description,
                    'server_required': saved_server_required
                }
                found = True
                break

        if not found:
            # Add new entry
            resources.append({
                'id': saved_id,
                'filename': new_filename,
                'name': saved_name or new_filename,
                'version': new_version,
                'mc_version': new_mc_version,
                'description': saved_description,
                'server_required': saved_server_required
            })

        self.resources_data[self.current_type] = resources

        # Save to file
        self._save_to_file()

        # Refresh list
        self._refresh_file_list()

        # Build result message
        msg = f"资源文件已更新\n\n新文件: {new_filename}\n版本: {new_version or '(未检测到)'}\n适配版本: {new_mc_version or '(未检测到)'}"
        if deleted_files:
            msg += f"\n\n已卸载旧文件:\n" + "\n".join(deleted_files)

        messagebox.showinfo("成功", msg, parent=self)

    def _parse_version_from_filename(self, filename: str) -> str:
        """Parse version number from filename"""
        import re
        # Common patterns: -v1.2.3.jar, -1.2.3.jar, _1.2.3.jar, v1.2.3, etc.
        patterns = [
            r'-v?(\d+\.\d+\.\d+)',  # -v1.2.3 or -1.2.3
            r'[_-]v?(\d+\.\d+)',     # _v1.2 or -1.2
            r'(\d+\.\d+\.\d+)\.jar$',  # 1.2.3.jar at end
        ]
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _parse_mc_version_from_filename(self, filename: str) -> str:
        """Parse MC version from filename (GTNH specific)"""
        import re
        # Look for patterns like 2.7.0, 2.7.1, etc.
        # But not the mod version itself
        # This is tricky, so we'll look for common GTNH version patterns
        patterns = [
            r'-(\d+\.\d+\.\d+)\.jar$',  # -2.7.0.jar at end (might be confused with mod version)
        ]
        # For now, return empty and let user fill it
        return ""

    def _delete_resource(self):
        """Delete current resource from metadata"""
        resource_id = self.id_var.get().strip()
        if not resource_id:
            return

        if not messagebox.askyesno("确认", f"确定要删除 '{resource_id}' 的元数据吗？\n（实际文件不会被删除）", parent=self):
            return

        resources = self.resources_data.get(self.current_type, [])
        self.resources_data[self.current_type] = [
            r for r in resources if r.get('id') != resource_id
        ]

        self._save_to_file()
        self._refresh_file_list()
        self._clear_form()

        messagebox.showinfo("成功", "元数据已删除", parent=self)

    def _clear_form(self):
        """Clear all form fields"""
        self.id_var.set('')
        self.filename_var.set('')
        self.name_var.set('')
        self.res_version_var.set('')
        self.mc_version_var.set('')
        self.desc_text.delete(1.0, tk.END)

    def _save_to_file(self):
        """Save resources_data to resources.json"""
        if not self.current_version:
            return

        content_dir = init_external_content()
        json_path = os.path.join(content_dir, self.current_version, "resources.json")

        # Ensure directory exists
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        save_json(json_path, self.resources_data)

    def _on_close(self):
        """Close the dialog"""
        self.grab_release()
        self.destroy()
