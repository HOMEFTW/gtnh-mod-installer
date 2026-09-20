"""Shared light desktop theme, including classic Tk controls used by dialogs."""
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

BG = '#f3f5f9'
SURFACE = '#ffffff'
TEXT = '#19263d'
MUTED = '#63738b'
BLUE = '#2563eb'
BORDER = '#dde4ef'


def apply_theme(root):
    root.configure(background=BG)
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
        tkfont.nametofont(name, root=root).configure(family='Microsoft YaHei UI', size=10)
    root.option_add('*Background', BG)
    root.option_add('*Foreground', TEXT)
    for kind in ('Text', 'Listbox'):
        root.option_add(f'*{kind}.font', '{Microsoft YaHei UI} 10')
        root.option_add(f'*{kind}.background', SURFACE)
        root.option_add(f'*{kind}.foreground', TEXT)
        root.option_add(f'*{kind}.selectBackground', '#dbeafe')
        root.option_add(f'*{kind}.selectForeground', TEXT)
        root.option_add(f'*{kind}.relief', 'flat')
        root.option_add(f'*{kind}.borderWidth', 0)
        root.option_add(f'*{kind}.highlightThickness', 1)
        root.option_add(f'*{kind}.highlightBackground', BORDER)
        root.option_add(f'*{kind}.highlightColor', BLUE)
    root.option_add('*Text.padX', 10)
    root.option_add('*Text.padY', 8)
    root.option_add('*Text.insertBackground', TEXT)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Microsoft YaHei UI', 10), background=BG, foreground=TEXT)
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=SURFACE)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Card.TLabel', background=SURFACE)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('CardMuted.TLabel', background=SURFACE, foreground=MUTED)
    style.configure('Title.TLabel', font=('Microsoft YaHei UI', 21, 'bold'))
    style.configure('Heading.TLabel', font=('Microsoft YaHei UI', 13, 'bold'))
    style.configure('CardHeading.TLabel', background=SURFACE, font=('Microsoft YaHei UI', 11, 'bold'))
    style.configure('TLabelframe', background=BG, bordercolor=BORDER, relief='solid', borderwidth=1)
    style.configure('TLabelframe.Label', background=BG, foreground=MUTED)
    style.configure('TButton', padding=(12, 6), background=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, relief='flat', focusthickness=1, focuscolor=BLUE)
    style.map('TButton', background=[('disabled', '#eef1f6'), ('pressed', '#dbeafe'), ('active', '#edf3ff')],
              foreground=[('disabled', '#94a3b8')], bordercolor=[('focus', BLUE)])
    style.configure('Primary.TButton', background=BLUE, foreground='white', bordercolor=BLUE,
                    lightcolor=BLUE, darkcolor=BLUE, font=('Microsoft YaHei UI', 10, 'bold'))
    style.map('Primary.TButton', background=[('disabled', '#bccbe6'), ('pressed', '#1e40af'), ('active', '#1d4ed8')],
              foreground=[('disabled', '#f8fafc'), ('!disabled', 'white')])
    style.configure('Primary.TMenubutton', padding=(14, 8), background=BLUE, foreground='white',
                    arrowcolor='white', bordercolor=BLUE, lightcolor=BLUE, darkcolor=BLUE,
                    relief='flat', font=('Microsoft YaHei UI', 10, 'bold'))
    style.map('Primary.TMenubutton',
              background=[('pressed', '#1e40af'), ('active', '#1d4ed8')],
              foreground=[('!disabled', 'white')], arrowcolor=[('!disabled', 'white')])
    style.configure('Danger.TButton', foreground='#b42332')
    style.configure('Nav.TButton', anchor='w', padding=(18, 11), background=SURFACE, borderwidth=0)
    style.configure('Active.Nav.TButton', background='#eaf1ff', foreground=BLUE,
                    font=('Microsoft YaHei UI', 10, 'bold'))
    style.map('Active.Nav.TButton', background=[('active', '#dbeafe'), ('!active', '#eaf1ff')])
    style.configure('TEntry', fieldbackground=SURFACE, bordercolor=BORDER, padding=(9, 7), relief='flat')
    style.map('TEntry', bordercolor=[('focus', BLUE)], fieldbackground=[('readonly', '#f8fafc')])
    style.configure('TCombobox', fieldbackground=SURFACE, background=SURFACE, bordercolor=BORDER,
                    padding=(9, 7), arrowcolor=MUTED)
    style.map('TCombobox', fieldbackground=[('readonly', SURFACE)], foreground=[('readonly', TEXT)],
              bordercolor=[('focus', BLUE)])
    style.configure('TCheckbutton', padding=5)
    style.configure('Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    rowheight=42, borderwidth=0, relief='flat', bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
    style.configure('Treeview.Heading', background='#f6f8fc', foreground=MUTED,
                    padding=(10, 11), relief='flat', font=('Microsoft YaHei UI', 9, 'bold'))
    style.map('Treeview', background=[('selected', '#e7efff')], foreground=[('selected', TEXT)])
    style.configure('TScrollbar', troughcolor=BG, background='#cbd5e1', borderwidth=0, arrowsize=12)
    style.configure('TSeparator', background=BORDER)
    style.configure('Horizontal.TProgressbar', background=BLUE, troughcolor='#e4ebf5', borderwidth=0)
    style.configure('Content.TNotebook', background=SURFACE, borderwidth=0, tabmargins=0)
    style.layout('Content.TNotebook.Tab', [])
    style.layout('Content.TNotebook', [('Notebook.client', {'sticky': 'nswe'})])


def dialog_heading(parent, title, subtitle):
    frame = ttk.Frame(parent, padding=(20, 18, 20, 12))
    frame.pack(fill=tk.X)
    ttk.Label(frame, text=title, style='Heading.TLabel').pack(anchor=tk.W)
    ttk.Label(frame, text=subtitle, style='Muted.TLabel', wraplength=760).pack(anchor=tk.W, pady=(5, 0))
    return frame
