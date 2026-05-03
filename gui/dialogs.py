"""
Dialog windows for GTNH Mod Installer GUI
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional


class FolderSelectDialog:
    """Helper for selecting folders"""

    @staticmethod
    def select_minecraft_folder(parent, initial_dir: str = None) -> Optional[str]:
        """Open folder selection dialog for .minecraft folder"""
        folder = filedialog.askdirectory(
            parent=parent,
            title="选择 .minecraft 文件夹",
            initialdir=initial_dir
        )
        return folder if folder else None


class BackupDialog(tk.Toplevel):
    """Dialog for managing backups"""

    def __init__(self, parent, backup_manager, has_server=False, on_restore_callback=None):
        super().__init__(parent)
        self.title("备份管理")
        self.parent = parent
        self.backup_manager = backup_manager
        self.has_server = has_server
        self.on_restore_callback = on_restore_callback
        self._backups = []

        self._create_widgets()
        self._center_window()
        self.after(0, self._schedule_load_backups)

    def _create_widgets(self):
        self.geometry("600x400")

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Backup list
        ttk.Label(main_frame, text="可用备份:").pack(anchor=tk.W)
        self.status_var = tk.StringVar(value="准备加载备份...")
        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.scrollbar = ttk.Scrollbar(list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ('name', 'date', 'type', 'size')
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            yscrollcommand=self.scrollbar.set
        )
        self.tree.heading('name', text='名称')
        self.tree.heading('date', text='创建时间')
        self.tree.heading('type', text='类型')
        self.tree.heading('size', text='大小')

        self.tree.column('name', width=180)
        self.tree.column('date', width=130)
        self.tree.column('type', width=100)
        self.tree.column('size', width=80)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.tree.yview)

        # Action buttons
        action_frame = ttk.LabelFrame(main_frame, text="操作", padding=5)
        action_frame.pack(fill=tk.X, pady=5)

        # First row: Create backup buttons
        create_row = ttk.Frame(action_frame)
        create_row.pack(fill=tk.X, pady=2)

        ttk.Label(create_row, text="创建:").pack(side=tk.LEFT, padx=5)
        ttk.Button(create_row, text="创建客户端备份", command=lambda: self._create_backup("client")).pack(side=tk.LEFT, padx=5)
        if self.has_server:
            ttk.Button(create_row, text="创建服务端备份", command=lambda: self._create_backup("server")).pack(side=tk.LEFT, padx=5)
            ttk.Button(create_row, text="创建完整备份", command=lambda: self._create_backup("all")).pack(side=tk.LEFT, padx=5)

        # Second row: Restore and delete buttons
        restore_row = ttk.Frame(action_frame)
        restore_row.pack(fill=tk.X, pady=2)

        ttk.Label(restore_row, text="还原:").pack(side=tk.LEFT, padx=5)
        ttk.Button(restore_row, text="还原选中备份", command=self._restore_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(restore_row, text="删除选中备份", command=self._delete_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(restore_row, text="关闭", command=self._close).pack(side=tk.RIGHT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._close)

    def _center_window(self):
        self.transient(self.parent)
        self.grab_set()
        self.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 600) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 400) // 2
        self.geometry(f"600x400+{x}+{y}")

    def _load_backups(self):
        """Load and display backups"""
        self._backups = self._sorted_backups(self.backup_manager.list_backups())
        self._render_backups()

    def _schedule_load_backups(self):
        """Defer backup loading until after the dialog is visible."""
        self.status_var.set("正在加载备份...")
        self.after(10, self._load_backups)

    @staticmethod
    def _backup_row_values(backup: dict):
        """Format backup data for treeview display."""
        has_client = backup.get('has_client', False)
        has_server = backup.get('has_server', False)
        if has_client and has_server:
            backup_type = "客户端+服务端"
        elif has_client:
            backup_type = "客户端"
        elif has_server:
            backup_type = "服务端"
        else:
            backup_type = "未知"

        return (
            backup['id'],
            backup.get('created', '')[:19].replace('T', ' '),
            backup_type,
            backup.get('size_str', '')
        )

    @staticmethod
    def _sorted_backups(backups):
        """Sort backups newest first by created timestamp."""
        return sorted(backups, key=lambda x: x.get("created", ""), reverse=True)

    def _render_backups(self):
        """Render the current backup list into the treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for backup in self._backups:
            self.tree.insert('', tk.END, iid=backup['id'], values=self._backup_row_values(backup))

        count = len(self._backups)
        self.status_var.set(f"已加载 {count} 个备份" if count else "没有可用备份")

    def _upsert_backup(self, backup: dict):
        """Insert or replace a backup in the current list, keeping sort order."""
        self._backups = [item for item in self._backups if item["id"] != backup["id"]]
        self._backups.append(backup)
        self._backups = self._sorted_backups(self._backups)
        self._render_backups()

    def _remove_backup(self, backup_id: str):
        """Remove a backup from the current list and refresh the treeview."""
        self._backups = [item for item in self._backups if item["id"] != backup_id]
        self._render_backups()

    def _create_backup(self, backup_type: str):
        """Create a new backup"""
        name = tk.simpledialog.askstring("创建备份", "备份名称 (留空自动生成):", parent=self)
        if name is not None:  # None means cancelled
            success, message = self.backup_manager.create_backup(name if name.strip() else None, backup_type)
            if success:
                messagebox.showinfo("成功", f"备份创建成功: {message}", parent=self)
                new_backup = next(
                    (item for item in self.backup_manager.list_backups() if item["id"] == message),
                    None
                )
                if new_backup:
                    self._upsert_backup(new_backup)
                else:
                    self._schedule_load_backups()
            else:
                messagebox.showerror("错误", message, parent=self)

    def _restore_backup(self):
        """Restore selected backup with user-chosen restore type"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个备份", parent=self)
            return

        backup_id = selection[0]

        # Ask restore side
        restore_type = self._ask_restore_side()
        if not restore_type:
            return

        type_text = {"all": "双端", "client": "仅客户端", "server": "仅服务端"}.get(restore_type, "双端")

        if messagebox.askyesno("确认", f"确定要还原备份 '{backup_id}' 吗？\n还原方式: {type_text}\n当前配置将被覆盖！", parent=self):
            success, message = self.backup_manager.restore_backup(backup_id, restore_type)
            if success:
                messagebox.showinfo("成功", message, parent=self)
                # Call restore callback to refresh installed list
                if self.on_restore_callback:
                    self.on_restore_callback()
            else:
                messagebox.showerror("错误", message, parent=self)

    def _ask_restore_side(self) -> Optional[str]:
        """Ask user which side to restore. Returns 'all', 'client', 'server', or None (cancelled)"""
        dialog = tk.Toplevel(self)
        dialog.title("选择还原方式")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = [None]

        frame = ttk.Frame(dialog, padding=15)
        frame.pack()

        ttk.Label(frame, text="请选择还原方式:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        def on_choice(side):
            result[0] = side
            dialog.grab_release()
            dialog.destroy()

        ttk.Button(btn_frame, text="双端还原", command=lambda: on_choice("all")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="仅客户端", command=lambda: on_choice("client")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="仅服务端", command=lambda: on_choice("server")).pack(side=tk.LEFT, padx=5)

        dialog.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), dialog.grab_release(), dialog.destroy()))
        dialog.wait_window(dialog)
        return result[0]

    def _delete_backup(self):
        """Delete selected backup"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个备份", parent=self)
            return

        backup_id = selection[0]
        if messagebox.askyesno("确认", f"确定要删除备份 '{backup_id}' 吗？", parent=self):
            success, message = self.backup_manager.delete_backup(backup_id)
            if success:
                messagebox.showinfo("成功", message, parent=self)
                self._remove_backup(backup_id)
            else:
                messagebox.showerror("错误", message, parent=self)

    def _close(self):
        self.grab_release()
        self.destroy()


class AboutDialog(tk.Toplevel):
    """About dialog"""

    VERSION_TEXT = "版本 1.1.1"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("关于")
        self.parent = parent

        self._create_widgets()
        self._center_window()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="GTNH 私货安装器", font=('Arial', 14, 'bold')).pack()
        ttk.Label(main_frame, text=self.VERSION_TEXT).pack(pady=5)
        ttk.Label(main_frame, text="为 GTNH 整合包安装额外模组、脚本和配置文件").pack(pady=10)
        ttk.Label(main_frame, text="工作室 Andgatech").pack(pady=2)
        ttk.Label(main_frame, text="© 2026").pack()

        ttk.Button(main_frame, text="确定", command=self.destroy).pack(pady=10)

        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _center_window(self):
        self.transient(self.parent)
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        self.geometry(f"+{x}+{y}")
