@echo off
chcp 65001 >nul
echo ========================================
echo GTNH 私货安装器 - 打包脚本
echo ========================================
echo.

REM Create build venv if not exists
if not exist ".build-venv\Scripts\python.exe" (
    echo 正在创建构建虚拟环境...
    python -m venv .build-venv
    echo 正在安装依赖...
    .build-venv\Scripts\pip.exe install requests py7zr tkinterdnd2 Pillow pyinstaller
)

REM Check UPX
set UPX_DIR=
if exist "tools\upx-5.1.1-win64\upx.exe" (
    set UPX_DIR=--upx-dir tools\upx-5.1.1-win64
    echo UPX 压缩已启用
) else (
    echo 注意: UPX 未安装，跳过压缩 ^(可选优化^)
)

echo 正在打包程序...
echo.

REM Build with PyInstaller in venv
.build-venv\Scripts\python.exe -m PyInstaller build.spec --clean %UPX_DIR%

echo.
if exist "dist\GTNH私货安装器.exe" (
    echo ========================================
    echo 打包完成！
    echo 输出文件: dist\GTNH私货安装器.exe
    for %%A in ("dist\GTNH私货安装器.exe") do echo 文件大小: %%~zA bytes
    echo ========================================
    echo.
    echo 首次运行程序时，Addcontent 文件夹将自动解压到 exe 同级目录
) else (
    echo 打包失败，请检查错误信息
)

pause
