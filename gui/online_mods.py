"""Non-blocking online mod browser; all Tk calls stay on the UI thread."""
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from gui.theme import dialog_heading
from core.online_mods import OnlineMod, OnlineModClient, WIKI_URL, normalize_repository


class OnlineModsDialog(tk.Toplevel):
    def __init__(self, parent, content_base, cache_path):
        super().__init__(parent)
        self.title(f"在线下载模组 — {Path(content_base).name}")
        self.geometry("1060x790")
        self.minsize(940, 720)
        self.transient(parent)
        self.grab_set()
        self.content_base = content_base
        self.cache_path = cache_path
        self.client = OnlineModClient()
        self.events = queue.Queue()
        self.busy = False
        self.changed = False
        self.release = None
        self.mod = None
        self.mods = self.client.cached_index(cache_path)
        self.protocol("WM_DELETE_WINDOW", self._close)

        dialog_heading(self, "在线下载模组", "从社区索引发现模组，将 GitHub 正式版下载到当前资源库。")
        frame = ttk.Frame(self, padding=(20, 0, 20, 18))
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="索引：GTNH 中文维基 · 可添加MOD（CC BY-NC-SA 3.0）", style="Muted.TLabel").pack(anchor=tk.W)
        ttk.Label(frame, text="最新正式 Release 不保证兼容当前整合包；请阅读 Wiki 说明和发布说明，确认依赖。\n"
                  "下载仅加入资源库；回到主窗口选择安装。升级已有模组时，请先卸载旧版，避免重复加载。",
                  wraplength=960, style="Muted.TLabel").pack(anchor=tk.W, pady=(6, 14))
        top = ttk.Frame(frame)
        top.pack(fill=tk.X)
        self.refresh_button = ttk.Button(top, text="刷新 Wiki 索引", command=self._refresh)
        self.refresh_button.pack(side=tk.LEFT)
        ttk.Button(top, text="打开 Wiki", command=lambda: webbrowser.open(WIKI_URL)).pack(side=tk.LEFT, padx=5)
        ttk.Label(top, text="搜索：").pack(side=tk.LEFT)
        self.search = tk.StringVar()
        ttk.Entry(top, textvariable=self.search).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search.trace_add("write", lambda *_: self._populate())

        lower = ttk.Frame(frame)
        lower.pack(side=tk.BOTTOM, fill=tk.X)
        table = ttk.Frame(frame)
        table.pack(fill=tk.BOTH, expand=True, pady=8)
        self.tree = ttk.Treeview(table, columns=("name", "repo", "variant", "side"),
                                 show="headings", selectmode="browse", height=9)
        for key, title, width in (("name", "模组", 260), ("repo", "GitHub 仓库", 280),
                                  ("variant", "Wiki 链接说明", 160), ("side", "服务端", 65)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width)
        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.notes = tk.Text(frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.notes.pack(side=tk.BOTTOM, fill=tk.X, before=table, pady=(8, 0))

        repo_row = ttk.Frame(lower)
        repo_row.pack(fill=tk.X, pady=8)
        ttk.Label(repo_row, text="仓库（可手动输入）：").pack(side=tk.LEFT)
        self.repository = tk.StringVar()
        self.repository.trace_add("write", self._repository_changed)
        self.repo_entry = ttk.Entry(repo_row, textvariable=self.repository)
        self.repo_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.query_button = ttk.Button(repo_row, text="查询最新正式版", style="Primary.TButton", command=self._query)
        self.query_button.pack(side=tk.LEFT)
        self.release_text = tk.StringVar(value="尚未查询 Release")
        ttk.Label(lower, textvariable=self.release_text).pack(anchor=tk.W)
        self.asset_combo = ttk.Combobox(lower, state="disabled")
        self.asset_combo.pack(fill=tk.X, pady=5)
        bottom = ttk.Frame(lower)
        bottom.pack(fill=tk.X)
        self.server_required = tk.BooleanVar(value=False)
        self.server_check = ttk.Checkbutton(bottom, text="需要安装到服务端（请核对模组说明）",
                                           variable=self.server_required)
        self.server_check.pack(side=tk.LEFT)
        self.download_button = ttk.Button(bottom, text="下载到资源库", style="Primary.TButton", command=self._download,
                                          state=tk.DISABLED)
        self.download_button.pack(side=tk.RIGHT)
        ttk.Button(bottom, text="打开发布页面", command=self._open_release).pack(side=tk.RIGHT, padx=5)
        self.progress = ttk.Progressbar(lower, maximum=100)
        self.progress.pack(fill=tk.X, pady=8)
        self.status = tk.StringVar(value=f"缓存索引：{len(self.mods)} 个仓库" if self.mods else "准备加载索引")
        ttk.Label(lower, textvariable=self.status, wraplength=900).pack(anchor=tk.W)
        self._populate()
        self.poll_job = self.after(100, self._poll)
        self._refresh()

    def _populate(self):
        if self.busy:
            return
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().casefold()
        for index, mod in enumerate(self.mods):
            if query in f"{mod.name} {mod.repository} {mod.description}".casefold():
                self.tree.insert("", tk.END, iid=str(index), values=(
                    mod.name, mod.repository, mod.link_label, "需要" if mod.server_required else "请核对"))

    def _select(self, _event=None):
        if self.busy or not self.tree.selection():
            return
        mod = self.mods[int(self.tree.selection()[0])]
        self.repository.set(mod.repository)
        self.mod = mod
        self.server_required.set(mod.server_required)
        self.notes.configure(state=tk.NORMAL)
        self.notes.delete("1.0", tk.END)
        self.notes.insert("1.0", mod.description)
        self.notes.configure(state=tk.DISABLED)

    def _repository_changed(self, *_):
        self.mod = None
        self.release = None
        self.notes.configure(state=tk.NORMAL)
        self.notes.delete("1.0", tk.END)
        self.notes.configure(state=tk.DISABLED)
        self.server_required.set(False)
        self.asset_combo.set("")
        self.asset_combo.configure(values=(), state="disabled")
        self.download_button.configure(state=tk.DISABLED)
        self.release_text.set("尚未查询 Release")

    def _start(self, kind, operation):
        if self.busy:
            return
        self.busy = True
        self.progress["value"] = 0
        for widget in (self.refresh_button, self.query_button, self.download_button,
                       self.repo_entry, self.server_check, self.asset_combo):
            widget.configure(state=tk.DISABLED)
        self.status.set({"index": "正在获取 Wiki 索引…", "release": "正在查询最新正式 Release…",
                         "download": "正在下载并校验 JAR…"}[kind])

        def worker():
            try:
                self.events.put((kind, operation()))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh(self):
        self._start("index", lambda: self.client.load_index(self.cache_path))

    def _query(self):
        try:
            repository = normalize_repository(self.repository.get())
        except Exception as exc:
            messagebox.showerror("仓库无效", str(exc), parent=self)
            return
        if not self.mod or self.mod.repository.lower() != repository.lower():
            self.mod = OnlineMod(repository.split("/")[1], repository)
        self.release = None
        self.asset_combo.set("")
        self.asset_combo.configure(values=())
        self.release_text.set("正在查询…")
        self._start("release", lambda: self.client.latest_release(repository))

    def _download(self):
        index = self.asset_combo.current()
        if not self.release or index < 0:
            messagebox.showwarning("请选择附件", "请先选择要下载的 JAR 文件。", parent=self)
            return
        mod, release = self.mod, self.release
        asset = release["assets"][index]
        server = self.server_required.get()
        self._start("download", lambda: self.client.download(
            mod, release, asset, self.content_base, server,
            lambda done, total: self.events.put(("progress", done * 100 / total))))

    def _poll(self):
        try:
            while True:
                kind, result = self.events.get_nowait()
                if kind == "progress":
                    self.progress["value"] = result
                    continue
                self.busy = False
                for widget in (self.refresh_button, self.query_button, self.repo_entry, self.server_check):
                    widget.configure(state=tk.NORMAL)
                if kind == "index":
                    self.mods = result
                    self._populate()
                    self.status.set(f"已刷新：{len(result)} 个 GitHub 仓库；选择模组后查询最新正式版。")
                elif kind == "release":
                    self.release = result
                    self.release_text.set(f"最新正式版：{result['tag']}，共 {len(result['assets'])} 个 JAR 附件")
                    self.asset_combo.configure(values=[asset["name"] for asset in result["assets"]])
                    if len(result["assets"]) == 1:
                        self.asset_combo.current(0)
                    self.status.set("请核对适用版本并选择附件。")
                elif kind == "download":
                    self.changed = True
                    self.progress["value"] = 100
                    self.status.set(f"已加入资源库：{result}")
                    messagebox.showinfo("下载完成", "已加入当前版本资源库。关闭此窗口后即可选择安装。\n"
                                        "如果已有旧版，请先卸载旧版再安装。", parent=self)
                elif kind == "error":
                    self.status.set(f"操作失败；保留已有索引，可重试或手动输入仓库。{result}")
                    messagebox.showerror("在线下载", result, parent=self)
                if self.release:
                    self.asset_combo.configure(state="readonly")
                    self.download_button.configure(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.poll_job = self.after(100, self._poll)

    def _open_release(self):
        try:
            repository = normalize_repository(self.repository.get())
        except Exception as exc:
            messagebox.showwarning("仓库无效", str(exc), parent=self)
            return
        webbrowser.open(f"https://github.com/{repository}/releases")

    def _close(self):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前网络操作完成后关闭窗口。", parent=self)
            return
        self.client.session.close()
        self.after_cancel(self.poll_job)
        self.destroy()
