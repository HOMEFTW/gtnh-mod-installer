"""Download browser for official clients and Wiki resource packs."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from core.downloads import DownloadClient, GAME_URL, PACK_URL
from gui.theme import dialog_heading


class DownloadsDialog(tk.Toplevel):
    def __init__(self, parent, game=True, content_base=None):
        super().__init__(parent)
        self.game = game
        self.content_base = content_base
        self.changed = False
        self.installed_client = None
        self.client = DownloadClient()
        self.entries = []
        self.files = []
        self.asset_entry = None
        self.busy = False
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.title('下载 GTNH 客户端' if game else '下载资源包')
        self.geometry('1060x740')
        self.minsize(940,680)
        self.transient(parent)
        self.grab_set()
        self.protocol('WM_DELETE_WINDOW',self._close)
        dialog_heading(self,self.title(), '选择官方客户端：可仅下载 ZIP，或安装到空目录并记录清单来源。' if game else
                       '索引：GTNH 中文维基 · 资源包与光影（CC BY-NC-SA 3.0）')
        frame = ttk.Frame(self,padding=(20,0,20,20)); frame.pack(fill='both',expand=True)
        top = ttk.Frame(frame); top.pack(fill='x')
        self.refresh = ttk.Button(top,text='刷新索引',command=self._refresh); self.refresh.pack(side='left')
        ttk.Button(top,text='打开索引网页',command=lambda:webbrowser.open(GAME_URL if game else PACK_URL)).pack(side='left',padx=6)
        self.search = tk.StringVar()
        ttk.Entry(top,textvariable=self.search).pack(side='right',fill='x',expand=True)
        ttk.Label(top,text='搜索：').pack(side='right')
        self.search.trace_add('write',lambda *_:self._populate())
        self.preview = tk.BooleanVar(value=False)
        if game:
            ttk.Checkbutton(frame,text='包含测试版（Beta / RC）',variable=self.preview,command=self._populate).pack(anchor='w',pady=8)
        # Reserve actions before allocating remaining space to the list.
        footer = ttk.Frame(frame); footer.pack(side='bottom',fill='x')
        self.notes = tk.Text(footer,height=4,wrap='word',state='disabled'); self.notes.pack(fill='x',pady=8)
        self.assets = ttk.Combobox(footer,state='disabled'); self.assets.pack(fill='x',pady=5)
        actions = ttk.Frame(footer); actions.pack(fill='x')
        self.open_button = ttk.Button(actions,text='打开选中发布页',command=self._open); self.open_button.pack(side='left')
        self.query = ttk.Button(actions,text='查询 ZIP 附件',command=self._query); self.query.pack(side='left',padx=5)
        self.download = ttk.Button(actions,text='仅下载 ZIP…' if game else '下载到资源库',style='TButton' if game else 'Primary.TButton',command=self._download,state='disabled'); self.download.pack(side='right')
        self.install_client_button = None
        if game:
            self.install_client_button = ttk.Button(actions, text='下载并安装客户端', style='Primary.TButton', command=self._install_client, state='disabled')
            self.install_client_button.pack(side='right', padx=5)
        self.stop = ttk.Button(actions,text='取消下载',command=self.cancel.set,state='disabled'); self.stop.pack(side='right',padx=5)
        self.progress = ttk.Progressbar(footer); self.progress.pack(fill='x',pady=8)
        self.status = tk.StringVar(value='准备加载索引')
        ttk.Label(footer,textvariable=self.status,wraplength=900).pack(anchor='w')
        table = ttk.Frame(frame); table.pack(fill='both',expand=True,pady=8)
        self.tree = ttk.Treeview(table,columns=('name','kind'),show='headings',selectmode='browse',height=7)
        self.tree.heading('name',text='文件 / 资源包'); self.tree.heading('kind',text='类型')
        self.tree.column('name',width=700); self.tree.column('kind',width=160)
        scroll = ttk.Scrollbar(table,command=self.tree.yview); scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set); self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self._select)
        self.job = self.after(100,self._poll)
        self._refresh()

    def _selected(self):
        selection = self.tree.selection()
        return self.entries[int(selection[0])] if selection else None

    def _populate(self):
        if self.busy: return
        self.tree.delete(*self.tree.get_children())
        self.files = []; self.assets.set(''); self.assets.configure(values=(),state='disabled')
        self.download.configure(state='disabled')
        if self.install_client_button: self.install_client_button.configure(state='disabled')
        for i,entry in enumerate(self.entries):
            if self.game and entry.preview and not self.preview.get(): continue
            if self.search.get().casefold() not in (entry.name+' '+entry.description+' '+entry.kind).casefold(): continue
            self.tree.insert('', 'end',iid=str(i),values=(entry.name,entry.kind))

    def _select(self,_event=None):
        if self.busy: return
        self.files = []; self.assets.set(''); self.assets.configure(values=(),state='disabled')
        self.download.configure(state='disabled')
        if self.install_client_button: self.install_client_button.configure(state='disabled')
        entry = self._selected()
        self.notes.configure(state='normal'); self.notes.delete('1.0','end')
        if entry:
            self.notes.insert('1.0',entry.description+'\n'+entry.url+'\n'+(
                '请核对 Java 版本和启动器格式。使用“下载并安装客户端”可记录来源，之后生成完整清单。' if self.game else
                '请核对兼容版本、依赖和加载顺序；非 GitHub 平台请打开发布页下载。'))
        self.notes.configure(state='disabled')
        if entry and self.game: self._query()

    def _start(self,kind,operation):
        if self.busy: return
        self.busy=True; self.cancel.clear(); self.progress['value']=0
        for widget in (self.refresh,self.query,self.download,self.assets): widget.configure(state='disabled')
        if self.install_client_button: self.install_client_button.configure(state='disabled')
        self.stop.configure(state='normal' if kind in ('download','client') else 'disabled')
        self.status.set({'index':'正在加载索引…','assets':'正在查询附件…','download':'正在下载…','client':'正在安装客户端…'}[kind])
        def worker():
            try: self.events.put((kind,operation()))
            except Exception as exc: self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def _refresh(self): self._start('index',lambda:self.client.load_entries(self.game))

    def _query(self):
        entry=self._selected()
        if not entry or self.busy:return
        self.files=[]; self.assets.set(''); self.asset_entry=entry
        self._start('assets',lambda:self.client.assets(entry))

    def _download(self):
        index=self.assets.current(); entry=self._selected()
        if self.busy or not entry or index<0 or entry is not self.asset_entry:return
        asset=self.files[index]
        destination=filedialog.askdirectory(parent=self,title='选择客户端下载目录') if self.game else None
        if self.game and not destination:return
        def progress(done,total):self.events.put(('progress',(done,total)))
        self._start('download',lambda:self.client.download_zip(asset,destination,self.cancel,progress) if self.game else
                    self.client.download_pack(entry,asset,self.content_base,self.cancel,progress))

    def _install_client(self):
        from core.manifest import ManifestInstaller
        entry = self._selected()
        index = self.assets.current()
        if self.busy or not entry or index < 0 or entry is not self.asset_entry:
            return
        target = filedialog.askdirectory(parent=self, title='选择空目录安装客户端（保留启动器实例结构）')
        if not target:
            return
        asset = self.files[index]
        self._start('client', lambda: ManifestInstaller(self.client).install_client(
            asset, target, self.cancel, lambda text: self.events.put(('status', text))))

    def _open(self):
        entry=self._selected()
        if entry:webbrowser.open(entry.url)

    def _poll(self):
        try:
            while True:
                kind,result=self.events.get_nowait()
                if kind=='status':
                    self.status.set(result); continue
                if kind=='progress':
                    done,total=result
                    self.progress['value']=done*100/total if total else 0
                    self.status.set(f'已下载 {done/1048576:.1f} MB'+(f' / {total/1048576:.1f} MB' if total else ''))
                    continue
                self.busy=False; self.stop.configure(state='disabled')
                self.refresh.configure(state='normal'); self.query.configure(state='normal')
                if kind=='index':
                    self.entries=result; self._populate(); self.status.set(f'已加载 {len(result)} 个下载条目')
                elif kind=='assets':
                    if self._selected() is not self.asset_entry:
                        self.files=[]; self.assets.set(''); self.status.set('选择已变更，请重新查询附件。'); continue
                    self.files=result; self.assets.configure(values=[x['name'] for x in result])
                    if len(result)==1:self.assets.current(0)
                    self.status.set('请选择附件后下载。' if result else '没有可直接下载的 ZIP，请打开选中发布页。')
                elif kind=='client':
                    self.installed_client=result; self.progress['value']=100
                    self.status.set('客户端安装完成：'+result)
                    messagebox.showinfo('安装完成', '客户端已安装并记录下载来源。关闭窗口后自动选择该客户端。\n首次启动仍需在对应启动器中添加实例并配置 Java。', parent=self)
                elif kind=='download':
                    self.changed=not self.game; self.progress['value']=100
                    self.status.set('下载完成：'+result)
                    messagebox.showinfo('下载完成',result+('\n请在对应启动器中导入 ZIP。' if self.game else '\n关闭窗口后可在资源包列表中选择安装。'),parent=self)
                else:self.status.set('操作失败：'+result)
                # Selection may have changed while the worker was running: invalidate stale assets.
                if kind=='assets' or kind=='download' or kind=='error':
                    self.tree.selection_remove(*self.tree.selection()) if kind=='error' else None
                if self.files and self._selected() is self.asset_entry:
                    self.assets.configure(state='readonly'); self.download.configure(state='normal')
                    if self.install_client_button: self.install_client_button.configure(state='normal')
        except queue.Empty:pass
        self.job=self.after(100,self._poll)

    def _close(self):
        if self.busy:
            self.cancel.set(); self.status.set('正在停止，请等待当前网络请求结束后关闭。'); return
        self.after_cancel(self.job); self.client.session.close(); self.destroy()
