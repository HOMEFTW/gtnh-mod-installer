<div align="center">
  <img src="icon.png" width="88" alt="GTNH 私货安装器图标">

# GTNH 私货安装器 2.0

**下载客户端，管理附加资源，用一份清单分享你的整合包。**

[![Release](https://img.shields.io/github/v/release/HOMEFTW/gtnh-mod-installer)](https://github.com/HOMEFTW/gtnh-mod-installer/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/HOMEFTW/gtnh-mod-installer/total)](https://github.com/HOMEFTW/gtnh-mod-installer/releases)
![Platform](https://img.shields.io/badge/平台-Windows%20x64-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)

[**下载 Windows EXE**](https://github.com/HOMEFTW/gtnh-mod-installer/releases/latest) · [使用方法](#快速开始) · [分享整合包](#用清单分享整合包) · [反馈问题](https://github.com/HOMEFTW/gtnh-mod-installer/issues)

</div>

---

GTNH 私货安装器是面向 **GregTech New Horizons** 的中文桌面资源管理工具。你可以下载官方客户端，从 Wiki 索引发现额外模组和资源包，分别管理客户端与服务端安装，并将有下载来源的安装内容导出为可复现的 `.hflist` 清单。

它负责下载与资源安装。启动游戏仍需使用对应启动器、配置 Java，并在游戏内启用资源包。

## 2.0 有什么新功能

| 功能 | 可以做什么 |
| --- | --- |
| 统一下载中心 | 一个入口访问模组、GTNH 客户端、资源包下载 |
| 全新浅色界面 | 侧栏分类、资源搜索、完整说明、折叠日志 |
| 客户端下载安装 | 选择官方版本与 Java 变体，下载 ZIP 或安装到空目录 |
| GitHub 模组下载 | 从 Wiki 发现仓库，查询正式 Release 并选择 JAR |
| 资源包索引 | 保留 Wiki 说明，查询 GitHub ZIP 附件或打开其他平台发布页 |
| 安装清单 2.0 | 保存固定下载链接和 SHA-256，拖入窗口自动下载、校验、安装 |
| 安装与备份修复 | 更准确的双端记录、失败回滚、完整资源备份与元数据并发保护 |

## 下载与运行

1. 前往 [最新 Release](https://github.com/HOMEFTW/gtnh-mod-installer/releases/latest)，下载 **`GTNH-Mod-Installer-2.0.exe`**。
2. 放到可写的独立文件夹中运行，**无需另装 Python**。
3. 首次运行会在程序旁初始化 `Addcontent` 资源库。请保留该目录与程序配置，以便后续管理资源。

升级旧版时，先退出程序，再替换 EXE。保留已有的 `Addcontent`、配置及备份；不要把新版空资源库覆盖到自己的资源库上。2.0 可以继续读取旧版安装记录和 `.hflist 1.0` 清单。

> 发布的 EXE 面向 Windows x64。本项目与 Minecraft / GTNH 官方发行项目相互独立。

## 快速开始

### 已有 GTNH 客户端

1. 在主页面选择客户端实际使用的 `.minecraft` 目录；需要双端管理时再选择服务端目录。
2. 选择对应的 **资源版本**，例如 `2.8.X`。这是本地资源库分类，不代表程序会自动判断每个模组的兼容性。
3. 打开右上角 **下载中心**，下载需要的模组或资源包。
4. 返回主窗口，在相应分类勾选资源，点击 **安装选中资源**，选择安装到客户端、服务端或双端。
5. 通过“已安装”查看记录和卸载资源；建议变更前先使用 **备份当前**。

搜索会保留已经勾选的条目，“全选”只选择当前搜索结果。选中行可查看完整说明，空格键可勾选资源。初始化模组、汉化安装位于“工具”菜单。

### 从零安装客户端

1. 打开 **下载中心 → 客户端下载**。
2. 搜索版本并核对 Java 要求、MultiMC / Prism 或客户端 ZIP 格式。默认隐藏测试版，可手动显示 Beta / RC。
3. 选择 **下载并安装客户端**，指定一个空目录。
4. 下载、校验和解压完成后，程序自动选择该客户端，并记录其固定下载来源。
5. 在对应启动器中添加该实例，配置 Java 后启动游戏。

“仅下载 ZIP”用于自行导入启动器；它不会自动建立导入后客户端与下载链接之间的关联。需要分享完整清单时，请使用“下载并安装客户端”。

## 下载中心

### 模组下载

索引来自 [GTNH 中文维基·可添加 MOD](https://gtnh.huijiwiki.com/wiki/%E5%8F%AF%E6%B7%BB%E5%8A%A0MOD)。支持按名称搜索，也支持手动输入 `作者/仓库` 或 GitHub 仓库链接。

查询使用 GitHub 最新正式 Release，不包含预发布和草稿；自动排除源码、开发和文档 JAR，多个附件需要自行选择。下载后先加入当前版本资源库，再由主窗口安装。升级已有模组时，请先卸载旧版，避免重复加载。

Wiki 索引成功获取后会缓存；刷新失败时仍保留已有模组索引。GitHub 限流、仓库没有正式 Release 或缺少合适附件时，界面会显示原因。

### 资源包下载

索引来自 [GTNH 中文维基·资源包与光影](https://gtnh.huijiwiki.com/wiki/%E8%B5%84%E6%BA%90%E5%8C%85%E4%B8%8E%E5%85%89%E5%BD%B1) 的资源包章节。

- GitHub 发布页支持查询 ZIP 附件；Wiki 指定了 Release 标签时保留该标签，不擅自切换到最新版本。
- CurseForge 等其他平台通过“打开选中发布页”下载。
- 直接导入的 ZIP 必须在根目录包含 `pack.mcmeta`，下载后加入当前资源库。
- 安装后仍需在游戏中启用资源包，并根据作者说明调整加载顺序。

光影包支持本地管理和安装，当前不从 Wiki 的光影章节自动导入。

### 下载行为

| 项目 | 行为 |
| --- | --- |
| 同名文件 | 不覆盖现有资源库文件 |
| 完整性 | 校验大小、归档格式及发布方提供的 SHA-256（若有） |
| 清单来源 | 为已记录的下载保存实际文件 SHA-256 |
| 下载上限 | 模组 512 MiB，资源包 1 GiB，客户端 8 GiB |
| 取消 | 客户端和资源包支持取消，网络请求可能需要等待超时后结束 |
| 尚不支持 | 断点续传、自动安装 Java、自动解决模组依赖和兼容性 |

## 用清单分享整合包

### 创建者

1. 使用 **下载并安装客户端** 建立基础客户端。
2. 从下载中心获取模组和资源包，并在主页面安装。
3. 点击 **生成清单**，保存 `.hflist` 文件并分享给接收方。

主页面的 **安装后生成清单** 默认关闭；勾选后，普通资源安装或客户端下载并安装结束时会提示保存。独立“生成清单”按钮随时可用，导出的是本工具记录的实际已安装内容，而不是当前勾选项。

### 接收方

把 `.hflist` **拖进程序窗口**，也可以点击“加载清单”或按 Ctrl+V 粘贴清单路径。

- **含基础客户端来源**：选择空目录，自动下载固定版本客户端和附加资源，校验后安装。
- **仅含附加资源**：安装到当前选择的客户端；未选择时会提示选择现有客户端目录。
- **旧版 1.0 清单**：继续按资源 ID 从本地资源库安装。

完整客户端会在暂存目录中完成所有安装后再发布，失败或取消不会留下已发布的半成品。仅附加资源的安装会先完成下载和本地依赖检查；若后续安装阶段失败，已经成功安装的条目会保留并记录。

### 清单包含什么

| 内容 | 是否包含 |
| --- | --- |
| 已记录来源的官方客户端 | 固定 ZIP 链接、大小、SHA-256 |
| 已记录来源且文件未被修改的模组 / 资源包 | 固定附件链接、大小、SHA-256、安装位置 |
| 没有来源的本地脚本、配置等 | 本地依赖条目；接收方需要具备相同资源 |
| 存档、私人配置、未被工具管理的文件 | 不自动打包 |

清单是下载与安装配方，**不是整个游戏目录的文件快照**。无来源或已被手工修改的资源会在导出时提示；接收方缺少本地依赖或校验不一致时停止安装。旧版尚未记录的来源、其他启动器自行导入的客户端无法自动追溯。

双端安装记录会保留在清单中。没有服务端目录时，双端条目安装客户端部分；仅服务端条目需要先配置服务端目录。

## 资源管理与备份

| 资源类型 | 安装位置 |
| --- | --- |
| 模组 | 客户端；是否安装到服务端由资源的“服务端需要”标记决定 |
| 脚本、配置、ServerUtilities | 可安装到客户端和服务端 |
| 字体 | 客户端 `fonts` 和 `fontfiles` |
| 资源包、光影包 | 仅客户端 |

资源编辑器支持修改名称、版本、说明和文件名。配置目录采用合并复制，保留不冲突的文件；同路径文件会更新。编辑器检测到其他操作修改元数据时，会要求重新打开，避免覆盖更新。

侧栏 **备份与还原** 支持客户端、服务端及完整备份。新格式覆盖模组、配置、脚本、字体、资源包、光影和 ServerUtilities；还原时会清除这些覆盖范围内在备份后新增的目录。旧格式备份只还原其原有覆盖范围。

## 常见问题

**下载最新版就一定兼容吗？**

不一定。请阅读 Wiki、Release 说明和作者的依赖要求，特别留意原版、GTNH 特供版及适用的整合包版本。

**为什么 GitHub 查询失败？**

可能是网络访问失败、未登录请求额度耗尽、仓库没有正式 Release，或没有可安装附件。可以稍后重试，或打开发布页查看。清单重装使用固定链接，不查询 latest，但原文件被删除后也会无法下载。

**为什么清单缺少客户端链接？**

只有通过新版“下载并安装客户端”记录过来源的基础客户端，才能自动写入链接。仅下载 ZIP 后自行导入、旧安装记录和手工复制目录不会自动补推来源。

**为什么资源包没有显示效果？**

安装只复制文件。请在游戏资源包设置中启用，检查排列顺序，并按作者要求重启游戏。

**能直接覆盖现有游戏安装完整客户端吗？**

不能。完整客户端安装要求空目录，避免覆盖已有实例与存档；现有客户端可使用附加资源清单。

## 从源码运行与构建

需要 Python **3.11+**（使用 Tkinter）。发布构建在 Windows x64、Python 3.14 环境验证。

```powershell
git clone https://github.com/HOMEFTW/gtnh-mod-installer.git
cd gtnh-mod-installer
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

构建单文件 EXE：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller build.spec --clean --noconfirm
```

也可运行 `build.bat`，使用项目的 `.build-venv` 环境。输出为 `dist/GTNH私货安装器.exe`。应用版本集中在 `app_version.py`，窗口和 Windows 文件属性均从这里读取。

项目主要目录：

```text
core/         下载、清单、安装与备份逻辑
gui/          Tkinter 窗口和统一主题
utils/        文件、元数据和日志工具
tests/        回归测试及界面测试
Addcontent/   按 GTNH 版本组织的本地资源库
```

## 来源与反馈

- 客户端：[GTNH 官方版本历史](https://www.gtnewhorizons.com/version-history/)
- 模组索引：[GTNH 中文维基·可添加 MOD](https://gtnh.huijiwiki.com/wiki/%E5%8F%AF%E6%B7%BB%E5%8A%A0MOD)
- 资源包索引：[GTNH 中文维基·资源包与光影](https://gtnh.huijiwiki.com/wiki/%E8%B5%84%E6%BA%90%E5%8C%85%E4%B8%8E%E5%85%89%E5%BD%B1)

Wiki 内容按页面标注的 **CC BY-NC-SA 3.0** 使用。模组、资源包和客户端由各自作者及项目维护，其许可遵循原发布页面。

遇到问题请提交 [Issue](https://github.com/HOMEFTW/gtnh-mod-installer/issues)，附上程序版本、GTNH 版本、复现步骤和相关错误日志。请勿上传访问令牌、私人路径或存档等无关个人数据。

维护：**Andgatech / HOMEFTW**
