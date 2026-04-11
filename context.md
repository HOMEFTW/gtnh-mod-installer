# GTNH 私货安装器 v1.0 - 项目上下文

## 项目概述
一个带GUI界面的应用程序，用于为GTNH（GregTech New Horizons）Minecraft整合包安装额外的模组、脚本、配置文件、字体和资源包。支持客户端和服务端分别管理。由工作室 Andgatech 开发。

## 技术栈
- **语言**: Python 3.14
- **GUI框架**: Tkinter + ttk
- **依赖**:
  - `requests`（网络下载）
  - `py7zr`（7z解压）
  - `tkinterdnd2`（拖放功能）
  - `Pillow`（PNG转ICO用于exe图标）
  - `pyinstaller`（打包exe）

## 项目结构
```
gtnh-mod-installer/
├── main.py                 # 程序入口
├── requirements.txt        # 依赖列表
├── build.spec              # PyInstaller打包配置
├── build.bat               # 一键打包脚本
├── icon.png                # 图标源文件（窗口+exe）
├── icon.ico                # exe图标（由Pillow从icon.png转换）
├── Addcontent/             # 资源目录（打包后首次运行自动解压到exe同级目录）
│   ├── 2.7.X/
│   │   ├── mods/
│   │   ├── scripts/
│   │   ├── configs/        # 支持文件夹和单个文件（仅一级）
│   │   ├── fonts/
│   │   ├── resourcepacks/
│   │   └── resources.json  # 资源元数据
│   └── 2.8.X/
│       └── ...（同上）
├── core/
│   ├── minecraft.py        # .minecraft 路径操作（含fonts/fontfiles路径）
│   ├── backup.py           # 备份/还原功能（客户端/服务端分离，支持空目录恢复）
│   ├── installer.py        # 安装/卸载逻辑（双installed.json，资源类型安装规则）
│   ├── version_check.py    # 版本兼容检查
│   └── downloader.py       # 网络下载
├── gui/
│   ├── main_window.py      # 主窗口（TkinterDnD.Tk、路径检测、安装方式选择）
│   ├── widgets.py          # 自定义组件（COLUMNS_FULL/COLUMNS_INSTALLED两种列布局）
│   ├── dialogs.py          # 对话框（备份管理、还原方式选择、关于）
│   └── resource_editor.py  # 资源编辑器（文件重命名、类型感知UI）
└── utils/
    ├── logger.py           # 日志记录
    └── helpers.py          # 工具函数（is_frozen、外置资源目录处理）
```

## v1.0 已实现功能

### 1. 路径设置
- 客户端路径选择
- 服务端路径选择（可选）
- 路径自动保存到 config.json
- **启动时路径检测**：加载配置时检查路径是否存在，不存在则弹窗提示并清空路径栏（空路径不弹窗）

### 2. 资源版本管理
- 从 `Addcontent/` 目录动态读取可用版本（如 2.7.X, 2.8.X）
- 下拉框选择版本，点击"刷新版本"扫描新版本

### 3. 资源标签页
- 模组 (mods)
- 脚本 (scripts)
- 配置 (configs)
- 字体 (fonts)
- 资源包 (resourcepacks)
- 已安装（显示名称和安装状态：客户端/服务端已安装）

### 4. 资源列表显示
- COLUMNS_FULL：选择、名称、版本、适配版本、大小、服务端需装、说明
- COLUMNS_INSTALLED：选择、名称、安装状态
- 从 `resources.json` 读取资源元数据
- 说明列根据窗口大小自动换行
- 客户端/服务端安装状态区分显示

### 5. 安装方式选择
- 点击"安装选中"后弹出选择对话框：双端安装 / 仅客户端 / 仅服务端
- 安装逻辑遵循 `install_side` 参数：
  - `"both"`：客户端+服务端（按资源类型规则决定服务端安装）
  - `"client"`：仅安装客户端
  - `"server"`：仅安装服务端（仍遵守 server_required 规则）

### 6. 资源类型安装规则（核心逻辑）
安装资源时根据资源类型决定是否安装到服务端：
- **模组 (mods)**：始终根据元数据中 `server_required` 字段判断（最高优先级，无论选双端还是仅服务端）
- **脚本 (scripts)**：始终双端安装
- **配置 (configs)**：始终双端安装，递归合并复制
- **字体 (fonts)**：仅客户端安装，复制到 `fonts/` 和 `fontfiles/` 两个目录（自动创建）
- **资源包 (resourcepacks)**：仅客户端安装

### 7. 配置文件 (configs) 特殊处理
- Addcontent 中 configs 目录读取**一级子项**（文件或文件夹），不读取更深层级
- 安装时将 configs 内容**递归合并复制**到客户端/服务端的 config 目录
- 同名文件覆盖，新文件添加，不删除客户端原有文件
- 已安装的配置文件列表跟踪在 installed.json 的 `config_files` 字段中
- 卸载时根据跟踪的文件列表精确删除

### 8. 字体 (fonts) 特殊处理
- 安装时同时复制到客户端的 `fonts/` 和 `fontfiles/` 目录
- 若目录不存在则自动创建
- 卸载时从两个目录中都删除

### 9. installed.json 双文件机制
- **客户端** `installed.json` 存储在 `client_path/gtnh_installer_data/`，记录客户端安装状态
- **服务端** `installed.json` 存储在 `server_path/gtnh_installer_data/`，记录服务端安装状态
- 两个文件完全独立，各自跟踪
- Installer 类使用 `_load_client_installed()` / `_load_server_installed()` 分别读取
- `_save_client_installed()` / `_save_server_installed()` 分别保存
- 若某端不存在 installed.json，该端显示为未安装

### 10. 安装/卸载
- 勾选资源后点击"安装选中"，选择安装方式
- 文件复制到客户端/服务端对应目录（按安装方式和类型规则）
- 同名文件自动覆盖
- 安装状态分别记录到各自路径的 installed.json
- 安装/卸载/还原操作后自动刷新已安装界面

### 11. 备份/还原
- 分别备份客户端和服务端（mods、config、scripts、gtnh_installer_data）
- 每端携带各自的 installed.json
- 支持创建客户端备份、服务端备份、完整备份
- 还原时弹出选择对话框：双端还原 / 仅客户端 / 仅服务端
- 还原时自动检测备份内容，智能还原
- 还原时若备份不含 gtnh_installer_data，会删除当前的该文件夹
- 空目录保留：恢复备份时确保备份中的空目录也被正确恢复
- 还原后自动刷新所有资源列表

### 12. 安装清单 (.hflist)
- 安装完成后根据菜单勾选项决定是否生成清单文件（默认开启）
- 文件菜单 → "安装后生成清单" 勾选项控制
- 取消勾选后安装完毕不再弹出保存清单对话框
- 其他用户可加载清单执行相同安装操作
- 支持方式：菜单加载、按钮加载、Ctrl+V 粘贴路径、拖放文件（tkinterdnd2）

### 13. 资源编辑器
- 双击资源打开编辑器
- 右键菜单快速编辑
- 可编辑字段：ID、文件名、显示名称、版本、适配版本、说明、服务端必需
- 文件名修改同步文件本体：修改文件名时会重命名 Addcontent 中的实际文件
- 新资源首次保存：使用 `_original_filename` 跟踪原始文件名，避免同时修改多项时产生重复元数据
- 服务端必需复选框仅在模组类型时显示
- 类型感知标签（如"服务端必需"vs"模组始终双端安装"等提示）
- 支持更新资源文件（自动卸载旧文件）
- 自动从文件名解析版本号
- 支持文件和文件夹的删除操作

### 14. 工具功能
- **备份管理**：创建、还原、删除备份
- **初始化**：删除 CraftPresence、darkerer、defaultserverlist、HardcoreDarkness 模组
- **汉化安装**：支持 7z/zip 压缩包解压安装
- **安装常见问题**：打开维基页面
- **中文维基私货页面**：打开维基页面

### 15. 打包支持
- 使用 PyInstaller 打包为单个 exe（build.spec）
- Addcontent 和 icon.png 打包进 exe 内部
- 首次运行时 `init_external_content()` 自动解压 Addcontent 到 exe 同级目录
- 后续可直接在 Addcontent 文件夹中添加/修改资源
- icon.png 同时用于窗口图标和 exe 图标（Pillow 转 ICO）
- 控制台窗口隐藏（console=False）
- 关于对话框显示"工作室 Andgatech"

## resources.json 格式
```json
{
  "mods": [
    {
      "id": "mod-id",
      "name": "显示名称",
      "filename": "文件名.jar",
      "version": "1.0.0",
      "mc_version": "2.7.4",
      "description": "说明文字",
      "server_required": true
    }
  ],
  "scripts": [],
  "configs": [],
  "fonts": [],
  "resourcepacks": []
}
```

## installed.json 格式（客户端和服务端各自独立）
位于 `gtnh_installer_data/installed.json`：
```json
{
  "mods": ["mod-id-1", "mod-id-2"],
  "scripts": [],
  "configs": [],
  "config_files": {
    "config-id": ["path/to/file1.cfg", "path/to/file2.cfg"]
  },
  "fonts": [],
  "resourcepacks": []
}
```

## .hflist 清单格式
```json
{
  "version": "1.0",
  "created": "2026-04-07T12:00:00",
  "gtnh_version": "2.7.X",
  "resources": {
    "mods": ["mod_id_1", "mod_id_2"],
    "scripts": ["script_id_1"],
    "configs": [],
    "fonts": [],
    "resourcepacks": []
  }
}
```

## 关键设计决策
- **双 installed.json**：客户端和服务端各自维护独立的 installed.json，备份还原时随各自文件夹走，彻底解决服务端还原后状态不同步问题
- **server_required 最高优先级**：模组的 server_required 字段无论用户选双端还是仅服务端都生效
- **字体/资源包服务端拦截**：仅选服务端安装且全部为字体/资源包时弹窗阻止
- **配置递归合并而非覆盖**：configs 安装采用合并复制（不删除客户端原有配置），卸载时根据跟踪的文件列表精确删除
- **字体双目录安装**：GTNH 客户端使用 fonts/ 和 fontfiles/ 两个目录存放字体
- **_original_filename 模式**：资源编辑器跟踪原始文件名用于重命名，避免新资源首次保存时产生重复元数据
- **资源类型感知安装**：不同资源类型有不同安装规则
- **空目录恢复**：备份恢复后额外遍历确保空目录被创建
- **启动路径检测**：应用启动时检查保存的路径是否存在，不存在则提示并清空

## 运行方式
```bash
cd D:/Code/gtnh-mod-installer
pip install -r requirements.txt
python main.py
```

## 打包方式
```bash
# 安装 PyInstaller 和 Pillow
pip install pyinstaller Pillow

# 确保 icon.ico 存在（从 icon.png 生成）
python -c "from PIL import Image; img=Image.open('icon.png'); img.save('icon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

# 执行打包
pyinstaller build.spec --noconfirm

# 输出文件
dist/GTNH私货安装器.exe
```

## v1.0 完成状态
- [x] 资源编辑器对话框
- [x] 客户端/服务端安装状态区分
- [x] 备份系统客户端/服务端分离
- [x] 汉化安装（7z/zip）
- [x] 初始化按钮（删除指定模组）
- [x] 拖放文件支持（tkinterdnd2）
- [x] PyInstaller 打包支持
- [x] Addcontent 外置（首次运行自动解压）
- [x] 资源类型安装规则（mods按元数据，scripts/configs双端，fonts/resourcepacks仅客户端）
- [x] 配置文件递归合并安装+文件跟踪卸载
- [x] 配置文件一级目录读取
- [x] 字体双目录安装（fonts/ + fontfiles/）
- [x] 资源编辑器文件名同步修改文件本体
- [x] 新资源首次保存重命名bug修复
- [x] 空目录备份恢复
- [x] 窗口图标+exe图标统一使用icon.png
- [x] 关于对话框显示"工作室 Andgatech"
- [x] 安装/卸载/还原后自动刷新已安装状态
- [x] 安装方式选择（双端/仅客户端/仅服务端）
- [x] 还原方式选择（双端/仅客户端/仅服务端）
- [x] 双 installed.json（客户端和服务端各自独立）
- [x] server_required 始终为最高优先级
- [x] 启动时路径存在性检测
- [x] 字体/资源包仅服务端安装拦截提示
- [x] 清单生成开关（文件菜单勾选项）
