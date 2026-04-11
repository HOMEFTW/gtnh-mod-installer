# 资源编辑器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 GTNH 私货安装器添加资源元数据编辑器，允许用户通过 GUI 编辑 resources.json

**Architecture:** 创建独立的 ResourceEditorDialog 对话框类，左右分栏布局，左侧文件列表，右侧编辑区。通过三种方式（按钮、右键、双击）从主窗口打开。

**Tech Stack:** Python 3, Tkinter, JSON

---

## 文件结构

```
gui/
├── resource_editor.py  # 新增：ResourceEditorDialog 类
├── main_window.py      # 修改：添加编辑器入口
└── widgets.py          # 修改：添加回调参数
```

---

### Task 1: 创建 ResourceEditorDialog 基础框架

**Files:**
- Create: `gui/resource_editor.py`

- [ ] **Step 1: 创建 resource_editor.py 基础结构**

```python
"""
Resource Editor Dialog for GTNH Mod Installer GUI
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Dict, List, Callable
import os
import json

from utils.helpers import load_json, save_json, get_app_dir


class ResourceEditorDialog(tk.Toplevel):
    """Dialog for editing resource metadata"""

    RESOURCE_TYPES = ['mods', 'scripts', 'configs', 'fonts', 'resourcepacks']

    def __init__(self, parent, gtnh_version: str = "",
                 initial_type: str = "mods",
                 initial_id: str = None):
        """
        Args:
            parent: Parent window
            gtnh_version: Initial GTNH version to edit
            initial_type: Initial resource type to show
            initial_id: Initial resource ID to select
        """
        super().__init__(parent)
        self.title("资源编辑器")
        self.parent = parent

        # State
        self.current_version = gtnh_version
        self.current_type = initial_type
        self.resources_data: Dict[str, List[dict]] = {}
        self.selected_id: Optional[str] = initial_id

        # Build UI
        self._create_widgets()
        self._load_versions()
        self._center_window()

        # Load initial data
        if self.current_version:
            self._load_resources()

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

        # Description field
        ttk.Label(form_frame, text="说明:").grid(row=3, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(form_frame, width=40, height=6)
        self.desc_text.grid(row=3, column=1, sticky=tk.NSEW, pady=2, padx=(5, 0))

        form_frame.columnconfigure(1, weight=1)
        form_frame.rowconfigure(3, weight=1)

        # Server required checkbox
        self.server_required_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right_frame, text="服务端需要安装",
                        variable=self.server_required_var).pack(anchor=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="保存", command=self._save_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除", command=self._delete_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_close).pack(side=tk.RIGHT, padx=5)

    def _load_versions(self):
        """Load available GTNH versions"""
        app_dir = get_app_dir()
        content_dir = os.path.join(app_dir, "Addcontent")

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
        self._load_resources()

    def _load_resources(self):
        """Load resources for current version and type"""
        if not self.current_version:
            return

        # Load resources.json
        app_dir = get_app_dir()
        json_path = os.path.join(app_dir, "Addcontent", self.current_version, "resources.json")
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

        app_dir = get_app_dir()

        # Get actual files in directory
        type_dir = os.path.join(app_dir, "Addcontent", self.current_version, self.current_type)
        actual_files = set()
        if os.path.exists(type_dir):
            for f in os.listdir(type_dir):
                if os.path.isfile(os.path.join(type_dir, f)):
                    actual_files.add(f)

        # Get resources with metadata
        resources = self.resources_data.get(self.current_type, [])
        resources_by_filename = {r.get('filename'): r for r in resources}

        # Display: files with metadata first (marked with ☑)
        displayed_ids = []
        for res in resources:
            filename = res.get('filename', '')
            marker = '☑' if filename in actual_files else '☑⚠'  # file missing
            self.file_listbox.insert(tk.END, f"{marker} {res.get('id', '')} ({filename})")
            displayed_ids.append(res.get('id'))

        # Then files without metadata (marked with ☐)
        for filename in sorted(actual_files):
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
            self.id_var.set(resource.get('id', ''))
            self.filename_var.set(resource.get('filename', ''))
            self.name_var.set(resource.get('name', ''))
            self.desc_text.delete(1.0, tk.END)
            self.desc_text.insert(tk.END, resource.get('description', ''))
            self.server_required_var.set(resource.get('server_required', False))
        else:
            # New file without metadata - use filename as starting point
            self.id_var.set(self._generate_id_from_filename(resource_id))
            self.filename_var.set(resource_id)
            self.name_var.set('')
            self.desc_text.delete(1.0, tk.END)
            self.server_required_var.set(False)

    def _generate_id_from_filename(self, filename: str) -> str:
        """Generate a resource ID from filename"""
        # Remove extension
        name = os.path.splitext(filename)[0]
        # Replace spaces and special chars with dashes
        import re
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
        filename = self.filename_var.get().strip()

        if not resource_id:
            messagebox.showwarning("警告", "ID 不能为空", parent=self)
            return
        if not filename:
            messagebox.showwarning("警告", "文件名不能为空", parent=self)
            return

        # Get form data
        name = self.name_var.get().strip()
        description = self.desc_text.get(1.0, tk.END).strip()
        server_required = self.server_required_var.get()

        # Find and update resource
        resources = self.resources_data.get(self.current_type, [])
        found = False

        for i, r in enumerate(resources):
            if r.get('id') == resource_id or r.get('filename') == filename:
                resources[i] = {
                    'id': resource_id,
                    'filename': filename,
                    'name': name or filename,
                    'description': description,
                    'server_required': server_required
                }
                found = True
                break

        if not found:
            # Add new
            resources.append({
                'id': resource_id,
                'filename': filename,
                'name': name or filename,
                'description': description,
                'server_required': server_required
            })

        self.resources_data[self.current_type] = resources

        # Save to file
        self._save_to_file()

        # Refresh list
        self._refresh_file_list()

        messagebox.showinfo("成功", "资源已保存", parent=self)

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
        self.desc_text.delete(1.0, tk.END)
        self.server_required_var.set(False)

    def _save_to_file(self):
        """Save resources_data to resources.json"""
        if not self.current_version:
            return

        app_dir = get_app_dir()
        json_path = os.path.join(app_dir, "Addcontent", self.current_version, "resources.json")

        # Ensure directory exists
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        save_json(json_path, self.resources_data)

    def _on_close(self):
        """Close the dialog"""
        self.grab_release()
        self.destroy()


---

### Task 2: 修改 widgets.py 添加回调参数

**Files:**
- Modify: `gui/widgets.py:9-18` (ResourceListFrame.__init__)

- [ ] **Step 1: 修改 ResourceListFrame.__init__ 添加回调参数**

找到 `gui/widgets.py` 第 9-18 行，修改为：

```python
class ResourceListFrame(ttk.Frame):
    """Frame containing a scrollable list of resources with checkboxes"""

    def __init__(self, parent, on_select_callback: Optional[Callable] = None,
                 on_double_click: Optional[Callable] = None,
                 on_right_click: Optional[Callable] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select_callback = on_select_callback
        self.on_double_click = on_double_click
        self.on_right_click = on_right_click
        self.check_vars: Dict[str, tk.BooleanVar] = {}
        self.resource_items: Dict[str, dict] = {}

        self._create_widgets()
```

- [ ] **Step 2: 在 _create_widgets 末尾添加双击和右键绑定**

在 `gui/widgets.py` 的 `_create_widgets` 方法中，找到 `self.tree.bind('<Button-1>'...` 这一行（约第62行），在其后添加：

```python
        # Bind click event for selection toggle
        self.tree.bind('<Button-1>', self._on_tree_click)

        # Bind double-click and right-click events
        if self.on_double_click:
            self.tree.bind('<Double-Button-1>', self._on_double_click)
        if self.on_right_click:
            self.tree.bind('<Button-3>', self._on_right_click)
```

- [ ] **Step 3: 添加双击和右键事件处理方法**

在 `gui/widgets.py` 的 `_on_tree_click` 方法后（约第76行），添加：

```python
    def _on_double_click(self, event):
        """Handle double-click on tree item"""
        item_id = self.tree.identify_row(event.y)
        if item_id and self.on_double_click:
            self.on_double_click(item_id)

    def _on_right_click(self, event):
        """Handle right-click on tree item"""
        item_id = self.tree.identify_row(event.y)
        if self.on_right_click:
            self.on_right_click(event, item_id)
```

- [ ] **Step 4: 验证修改**

运行程序确认无语法错误：
```bash
cd D:/Code/gtnh-mod-installer && python main.py
```
程序应正常启动。

- [ ] **Step 5: 提交**

```bash
cd D:/Code/gtnh-mod-installer
git add gui/widgets.py
git commit -m "feat(widgets): add double-click and right-click callbacks to ResourceListFrame"
```


---

### Task 3: 修改 main_window.py 添加编辑器入口

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: 在文件顶部添加导入**

在 `gui/main_window.py` 第 10 行（`from gui.dialogs import...` 后）添加：

```python
from gui.resource_editor import ResourceEditorDialog
```

- [ ] **Step 2: 修改 ResourceListFrame 创建时传入回调**

在 `_create_widgets` 方法中，找到创建 `self.mod_list` 的位置（约第125-138行），修改为：

```python
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

        # Installed tab
        self.installed_list = ResourceListFrame(
            self.installed_frame,
            on_select_callback=self._update_selection_count,
            on_double_click=self._on_resource_double_click,
            on_right_click=self._show_context_menu
        )
        self.installed_list.pack(fill=tk.BOTH, expand=True)
```

- [ ] **Step 3: 在操作区添加"编辑资源"按钮**

在 `_create_widgets` 方法中，找到 `action_frame` 部分（约第158-171行），在"加载清单"按钮后添加：

```python
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
```

- [ ] **Step 4: 添加编辑器相关方法**

在 `main_window.py` 末尾（`_show_about` 方法后，`run` 方法前）添加：

```python
    def _on_resource_double_click(self, resource_id: str):
        """Handle double-click on a resource"""
        self._open_resource_editor(resource_id)

    def _show_context_menu(self, event, resource_id: str):
        """Show context menu on right-click"""
        # Get current resource type
        res_type = self._get_current_resource_type()

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

        ResourceEditorDialog(
            self.root,
            gtnh_version=self.current_version,
            initial_type=res_type.value,
            initial_id=resource_id
        )

        # Refresh resources after editor closes
        self._load_all_resources()
```

- [ ] **Step 5: 验证程序运行**

```bash
cd D:/Code/gtnh-mod-installer && python main.py
```
程序应正常启动，点击"编辑资源"按钮应打开编辑器对话框。

- [ ] **Step 6: 提交**

```bash
cd D:/Code/gtnh-mod-installer
git add gui/main_window.py gui/resource_editor.py
git commit -m "feat: add resource editor dialog with button/double-click/right-click entry points"
```


---

### Task 4: 集成测试

**Files:**
- None (testing only)

- [ ] **Step 1: 测试编辑器打开**

1. 运行程序：`python main.py`
2. 选择 .minecraft 路径
3. 点击"编辑资源"按钮
4. 验证编辑器对话框打开

- [ ] **Step 2: 测试资源编辑**

1. 在编辑器中选择版本和类型
2. 点击列表中的资源
3. 修改显示名称和说明
4. 点击保存
5. 关闭编辑器，重新打开
6. 验证修改已保存

- [ ] **Step 3: 测试添加新资源**

1. 点击"添加新资源"
2. 输入文件名
3. 填写信息并保存
4. 验证新资源出现在列表中

- [ ] **Step 4: 测试删除资源**

1. 选择一个资源
2. 点击"删除"
3. 确认删除
4. 验证资源从列表中移除

- [ ] **Step 5: 测试右键菜单**

1. 在资源列表中右键点击
2. 验证弹出菜单显示"编辑此资源"
3. 点击后编辑器打开并选中该资源

- [ ] **Step 6: 测试双击**

1. 双击资源列表中的项目
2. 验证编辑器打开并选中该资源

- [ ] **Step 7: 最终提交**

```bash
cd D:/Code/gtnh-mod-installer
git add -A
git commit -m "feat: complete resource editor implementation with all entry points"
```
