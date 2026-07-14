@echo off
title MIDI Show - Build EXE
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    MIDI Show - 打包为 EXE 可执行文件
echo ========================================
echo.

set ROOT=%~dp0
set VENV_DIR=%ROOT%.venv
set PYTHON_CMD=python

:: ---- 1. 检查 Python ----
where %PYTHON_CMD% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Python，请确保 Python 已安装并加入 PATH。
    pause
    exit /b 1
)

:: ---- 2. 检查/创建虚拟环境 ----
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [..] 正在创建虚拟环境...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! neq 0 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
) else (
    echo [OK] 虚拟环境已存在
)

:: ---- 3. 激活虚拟环境 ----
call "%VENV_DIR%\Scripts\activate.bat"

:: ---- 4. 安装依赖 ----
echo [..] 安装项目依赖...
"%VENV_DIR%\Scripts\pip" install -r "%ROOT%requirements.txt" -q
if !ERRORLEVEL! neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 项目依赖安装完成

:: ---- 5. 安装 PyInstaller ----
echo [..] 安装 PyInstaller...
"%VENV_DIR%\Scripts\pip" install pyinstaller -q
if !ERRORLEVEL! neq 0 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)
echo [OK] PyInstaller 安装完成

:: ---- 6. 清理旧的构建文件 ----
if exist "%ROOT%dist" (
    echo [..] 清理旧的 dist 目录...
    rmdir /s /q "%ROOT%dist"
)
if exist "%ROOT%build" (
    echo [..] 清理旧的 build 目录...
    rmdir /s /q "%ROOT%build"
)

:: ---- 7. 执行打包 ----
echo.
echo ========================================
echo   [..] 正在打包 MIDI_Show.exe ...
echo   这可能需要几分钟，请耐心等待...
echo ========================================
echo.

cd /d "%ROOT%"
"%VENV_DIR%\Scripts\pyinstaller" midi_show.spec --noconfirm
if !ERRORLEVEL! neq 0 (
    echo.
    echo [错误] 打包失败！请检查错误信息。
    echo.
    pause
    exit /b 1
)

:: ---- 8. 复制配置文件到 dist 目录 ----
echo.
echo [..] 复制配置文件...
if exist "%ROOT%midi_show_config.sample.json" (
    copy /y "%ROOT%midi_show_config.sample.json" "%ROOT%dist\" >nul
)
if exist "%ROOT%midi_show_library.sample.json" (
    copy /y "%ROOT%midi_show_library.sample.json" "%ROOT%dist\" >nul
)

:: ---- 9. 完成 ----
echo.
echo ========================================
echo   [OK] 打包完成！
echo.
echo   可执行文件位置:
echo   %ROOT%dist\MIDI_Show.exe
echo.
echo   使用方法:
echo   1. 将 dist 目录中的 MIDI_Show.exe 复制到任意位置
echo   2. 双击运行即可，无需安装 Python
echo   3. 配置文件会自动在 exe 同目录生成
echo ========================================
echo.

:: 清理
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul

pause
exit /b 0