# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GTNH Mod Installer
"""

# UPX is disabled because compressed v1.1.1 builds crashed on startup.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle Addcontent folder for first-run extraction
        ('Addcontent', 'Addcontent'),
        # Bundle icon for window icon
        ('icon.png', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'tkinterdnd2',
        'py7zr',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Third-party packages not needed
        'httpx', 'httpcore', 'h11', 'anyio',
        'starlette', 'sse_starlette', 'uvicorn',
        'mcp', 'jsonschema', 'referencing', 'rpds',
        'pydantic', 'pydantic_core', 'annotated_types',
        'cryptography',
        'pytest', 'pip',
        # Unused stdlib modules
        'curses', 'tty', 'pty',
        'xmlrpc', 'lib2to3',
        'test', 'tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GTNH私货安装器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,  # Hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Exe icon
)
