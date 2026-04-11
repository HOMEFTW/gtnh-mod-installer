"""
Custom widgets for GTNH Mod Installer GUI
"""
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Callable, Optional
import textwrap


class ResourceListFrame(ttk.Frame):
    """Frame containing a scrollable list of resources with checkboxes"""

    # Maximum characters per line for description wrapping
    DESC_WRAP_WIDTH = 35

    # Column presets
    COLUMNS_FULL = ('select', 'name', 'version', 'mc_version', 'size', 'server_required', 'description')
    COLUMNS_INSTALLED = ('select', 'name', 'description')

    def __init__(self, parent, on_select_callback: Optional[Callable] = None,
                 on_double_click: Optional[Callable] = None,
                 on_right_click: Optional[Callable] = None,
                 columns: tuple = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select_callback = on_select_callback
        self.on_double_click = on_double_click
        self.on_right_click = on_right_click
        self.check_vars: Dict[str, tk.BooleanVar] = {}
        self.resource_items: Dict[str, dict] = {}
        self.columns = columns or self.COLUMNS_FULL

        self._create_widgets()

    def _wrap_description(self, text: str, width: int = None) -> str:
        """Wrap description text to fit in column"""
        if not text:
            return ""
        width = width or self.DESC_WRAP_WIDTH
        # Use textwrap to wrap at word boundaries
        wrapped = textwrap.fill(text, width=width)
        return wrapped

    def _create_widgets(self):
        # Create treeview with scrollbar
        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        self.v_scroll = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = ttk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Treeview with increased row height for multi-line description
        style = ttk.Style()
        style.configure('ResourceTree.Treeview', rowheight=40)

        # Use self.columns instead of fixed columns
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=self.columns,
            show='headings',
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set,
            style='ResourceTree.Treeview'
        )

        # Configure columns based on preset
        if self.columns == self.COLUMNS_INSTALLED:
            # Installed tab: simpler layout
            self.tree.heading('select', text='选择')
            self.tree.heading('name', text='名称')
            self.tree.heading('description', text='安装状态')

            self.tree.column('select', width=50, anchor=tk.CENTER)
            self.tree.column('name', width=200)
            self.tree.column('description', width=400)
        else:
            # Full layout for resource tabs
            self.tree.heading('select', text='选择')
            self.tree.heading('name', text='名称')
            self.tree.heading('version', text='版本')
            self.tree.heading('mc_version', text='适配版本')
            self.tree.heading('size', text='大小')
            self.tree.heading('server_required', text='服务端需装')
            self.tree.heading('description', text='说明')

            self.tree.column('select', width=50, minwidth=50, anchor=tk.CENTER)
            self.tree.column('name', width=130, minwidth=100, anchor=tk.W)
            self.tree.column('version', width=70, minwidth=60, anchor=tk.CENTER)
            self.tree.column('mc_version', width=80, minwidth=60, anchor=tk.CENTER)
            self.tree.column('size', width=60, minwidth=50, anchor=tk.CENTER)
            self.tree.column('server_required', width=80, minwidth=80, anchor=tk.CENTER)
            self.tree.column('description', width=250, minwidth=200, anchor=tk.W)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll.config(command=self.tree.yview)
        self.h_scroll.config(command=self.tree.xview)

        # Bind click event for selection toggle
        self.tree.bind('<Button-1>', self._on_tree_click)

        # Bind double-click and right-click events
        if self.on_double_click:
            self.tree.bind('<Double-Button-1>', self._on_double_click)
        if self.on_right_click:
            self.tree.bind('<Button-3>', self._on_right_click)

    def _on_tree_click(self, event):
        """Handle click on tree item to toggle selection"""
        region = self.tree.identify('region', event.x, event.y)
        if region == 'cell':
            column = self.tree.identify_column(event.x)
            if column == '#1':  # Select column
                item_id = self.tree.identify_row(event.y)
                if item_id and item_id in self.check_vars:
                    var = self.check_vars[item_id]
                    var.set(not var.get())
                    self._update_tree_item(item_id)
                    if self.on_select_callback:
                        self.on_select_callback()

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

    def _update_tree_item(self, item_id: str):
        """Update the display of a tree item"""
        if item_id in self.check_vars and item_id in self.resource_items:
            checked = '☑' if self.check_vars[item_id].get() else '☐'
            item = self.resource_items[item_id]

            if self.columns == self.COLUMNS_INSTALLED:
                # Installed tab layout - only name and description
                desc = self._wrap_description(item.get('description', ''))
                self.tree.item(item_id, values=(
                    checked,
                    item.get('name', ''),
                    desc
                ))
            else:
                # Full layout
                server_req = '是' if item.get('server_required', False) else '否'
                desc = self._wrap_description(item.get('description', ''))
                self.tree.item(item_id, values=(
                    checked,
                    item.get('name', ''),
                    item.get('version', ''),
                    item.get('mc_version', ''),
                    item.get('size', ''),
                    server_req,
                    desc
                ))

    def set_resources(self, resources: List[dict]):
        """Set the list of resources to display"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.check_vars.clear()
        self.resource_items.clear()

        # Add new items
        for res in resources:
            res_id = res.get('id', '')

            var = tk.BooleanVar(value=False)
            self.check_vars[res_id] = var
            self.resource_items[res_id] = res

            if self.columns == self.COLUMNS_INSTALLED:
                # Installed tab layout
                desc = self._wrap_description(res.get('description', ''))
                self.tree.insert('', tk.END, iid=res_id, values=(
                    '☐',
                    res.get('name', ''),
                    desc
                ))
            else:
                # Full layout
                server_req = '是' if res.get('server_required', False) else '否'
                desc = self._wrap_description(res.get('description', ''))
                self.tree.insert('', tk.END, iid=res_id, values=(
                    '☐',
                    res.get('name', ''),
                    res.get('version', ''),
                    res.get('mc_version', ''),
                    res.get('size', ''),
                    server_req,
                    desc
                ))

    def select_all(self):
        """Select all resources"""
        for var in self.check_vars.values():
            var.set(True)
        for item_id in self.check_vars.keys():
            self._update_tree_item(item_id)
        if self.on_select_callback:
            self.on_select_callback()

    def deselect_all(self):
        """Deselect all resources"""
        for var in self.check_vars.values():
            var.set(False)
        for item_id in self.check_vars.keys():
            self._update_tree_item(item_id)
        if self.on_select_callback:
            self.on_select_callback()

    def get_selected_ids(self) -> List[str]:
        """Get list of selected resource IDs"""
        return [res_id for res_id, var in self.check_vars.items() if var.get()]

    def set_selected_ids(self, ids: List[str]):
        """Set which resources are selected"""
        for res_id, var in self.check_vars.items():
            var.set(res_id in ids)
            self._update_tree_item(res_id)


class LogFrame(ttk.Frame):
    """Frame for displaying log messages"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        # Label
        ttk.Label(self, text="日志:").pack(anchor=tk.W)

        # Text widget with scrollbar
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(text_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text = tk.Text(
            text_frame,
            height=6,
            state=tk.DISABLED,
            yscrollcommand=self.scrollbar.set,
            font=('Consolas', 9)
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        self.scrollbar.config(command=self.text.yview)

        # Configure tags for different log levels
        self.text.tag_configure('INFO', foreground='black')
        self.text.tag_configure('WARNING', foreground='orange')
        self.text.tag_configure('ERROR', foreground='red')
        self.text.tag_configure('SUCCESS', foreground='green')

    def append_log(self, message: str, level: str = 'INFO'):
        """Append a log message"""
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, message + '\n', level)
        self.text.see(tk.END)
        self.text.config(state=tk.DISABLED)

    def clear(self):
        """Clear all log messages"""
        self.text.config(state=tk.NORMAL)
        self.text.delete(1.0, tk.END)
        self.text.config(state=tk.DISABLED)


class StatusBar(ttk.Frame):
    """Status bar at the bottom of the window"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        self.status_var = tk.StringVar(value="就绪")
        self.label = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN)
        self.label.pack(fill=tk.X, padx=2, pady=2)

    def set_status(self, status: str):
        """Set the status text"""
        self.status_var.set(status)


class ProgressDialog:
    """Progress dialog for long operations"""

    def __init__(self, parent, title: str = "请稍候", message: str = ""):
        self.parent = parent
        self.title = title
        self.message = message
        self.dialog: Optional[tk.Toplevel] = None
        self.progress_var: Optional[tk.DoubleVar] = None
        self.label_var: Optional[tk.StringVar] = None

    def show(self):
        """Show the progress dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self.title)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.geometry("300x100")
        self.dialog.resizable(False, False)

        # Message label
        self.label_var = tk.StringVar(value=self.message)
        ttk.Label(self.dialog, textvariable=self.label_var).pack(pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            self.dialog,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, padx=20, pady=10)

        # Prevent closing with X button
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    def update(self, value: float, message: str = None):
        """Update progress value and optionally the message"""
        if self.progress_var:
            self.progress_var.set(value)
        if message and self.label_var:
            self.label_var.set(message)
        self.dialog.update()

    def close(self):
        """Close the dialog"""
        if self.dialog:
            self.dialog.grab_release()
            self.dialog.destroy()
            self.dialog = None
