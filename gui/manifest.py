"""Main-thread progress UI for manifest download/install workers."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
from gui.theme import dialog_heading


class ManifestProgressDialog(tk.Toplevel):
    def __init__(self, parent, operation):
        super().__init__(parent)
        self.title('从清单下载安装')
        self.geometry('600x260')
        self.resizable(False,False)
        self.transient(parent);self.grab_set()
        self.result=None;self.error=None;self.done=False
        self.cancel=threading.Event();self.events=queue.Queue()
        dialog_heading(self,'从清单下载安装','按固定链接下载并校验文件，再安装到所选目录。')
        body=ttk.Frame(self,padding=(20,0,20,20));body.pack(fill='both',expand=True)
        self.status=tk.StringVar(value='准备安装…')
        ttk.Label(body,textvariable=self.status,wraplength=550).pack(fill='x',pady=10)
        self.progress=ttk.Progressbar(body,mode='indeterminate');self.progress.pack(fill='x',pady=10);self.progress.start()
        self.button=ttk.Button(body,text='取消',command=self._close);self.button.pack(side='right')
        self.protocol('WM_DELETE_WINDOW',self._close)
        def worker():
            try:self.events.put(('done',operation(self.cancel,lambda text:self.events.put(('status',text)))))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
        self.after(100,self._poll)

    def _poll(self):
        try:
            while True:
                kind,result=self.events.get_nowait()
                if kind=='status':self.status.set(result)
                else:
                    self.done=True
                    if kind=='done':self.result=result
                    else:self.error=result
                    self.progress.stop();self.destroy();return
        except queue.Empty:pass
        self.after(100,self._poll)

    def _close(self):
        self.cancel.set();self.status.set('正在停止，请等待当前网络请求结束…');self.button.configure(state='disabled')
