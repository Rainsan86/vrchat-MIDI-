@echo off
title MIDI Show - VRChat MIDI Player
chcp 65001 >nul

setlocal enabledelayedexpansion

:: ============================================================
::  MIDI Show — 一键启动脚本 (Windows Batch)
::  自动检查 Python、创建虚拟环境、安装依赖、启动应用
:: ============================================================

set ROOT=%~dp0
set VENV_DIR=%ROOT%.venv
set PYTHON_CMD=python
set MIN_PYTHON_VER=3.9

echo ========================================
echo    MIDI Show - VRChat MIDI Player
echo    One-Click Launcher
echo ========================================
echo.

:: ---- 1. 检查 Python 是否存在 ----
where %PYTHON_CMD% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Python，请确保 Python 已安装并加入 PATH。
    echo        下载: https://www.python.org/downloads/
    echo.
    echo        安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: ---- 2. 检查 Python 最低版本 ----
for /f "tokens=2" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VER=%%v
echo [OK] 检测到 Python %PY_VER%

:: 提取主版本和次版本号 (e.g. 3.10.2 -> 3.10)
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

:: 检查版本（扁平化结构，避免嵌套复合块解析问题）
if not defined PY_MAJOR (
    echo [警告] 无法解析 Python 版本号
    echo        原始输出: %PY_VER%
    pause
    exit /b 1
)
if not defined PY_MINOR set "PY_MINOR=0"
if %PY_MAJOR% GTR 3 (
    echo [错误] Python 主版本过高 (%PY_VER%^)，当前仅支持 Python 3.x
    pause
    exit /b 1
)
if %PY_MAJOR% LSS 3 (
    echo [错误] Python 版本过低 (%PY_VER%^)，需要 %MIN_PYTHON_VER% 或更高
    pause
    exit /b 1
)
if %PY_MINOR% LSS 9 (
    echo [错误] Python 版本过低 (%PY_VER%^)，需要 %MIN_PYTHON_VER% 或更高
    pause
    exit /b 1
)
echo [OK] Python 版本满足要求 (^>= %MIN_PYTHON_VER%^)

:: ---- 3. 检查/创建虚拟环境 ----
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo [..] 正在创建虚拟环境 ^(这可能需要一些时间^)...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! neq 0 (
        echo [错误] 虚拟环境创建失败
        echo        尝试: python -m venv .venv
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
) else (
    echo [OK] 虚拟环境已存在
)

:: ---- 4. 激活虚拟环境 ----
call "%VENV_DIR%\Scripts\activate.bat"
    if !ERRORLEVEL! neq 0 (
        echo [错误] 虚拟环境激活失败
        echo        可能原因：.venv 已损坏，请删除 .venv 目录后重试
    pause
    exit /b 1
    )

:: ---- 5. 升级 pip ----
echo.
echo [..] 升级 pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip -q

:: ---- 6. 安装依赖 ----
echo [..] 安装依赖 (首次安装可能需要从网络下载)...
echo.

"%VENV_DIR%\Scripts\pip" install -r "%ROOT%requirements.txt"
if !ERRORLEVEL! neq 0 (
    echo.
    echo [错误] 依赖安装失败，请检查网络连接。
    echo        可尝试手动执行:
    echo            .venv\Scripts\activate
    echo            pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

:: ---- 7. 验证关键依赖可导入 ----
echo [..] 验证关键依赖...
"%VENV_DIR%\Scripts\python.exe" -c "import mido; import rtmidi; print('[OK] 关键依赖检查通过')"
if !ERRORLEVEL! neq 0 (
    echo.
    echo [错误] 依赖导入检查未通过。
    echo        请尝试手动运行以下命令安装依赖：
    echo            .venv\Scripts\activate
    echo            pip install --upgrade mido python-rtmidi python-osc
    echo.
    echo        如果上述命令仍失败，请确认已安装 Visual C++ Redistributable：
    echo        https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    pause
    exit /b 1
)

:: ---- 8. 启动应用 ----
echo.
echo ========================================
echo   [..] 正在启动 MIDI Show...
echo ========================================
echo.
"%VENV_DIR%\Scripts\python.exe" "%ROOT%main.py"
set EXIT_CODE=!ERRORLEVEL!

:: ---- 9. 清理 ----
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul

:: ---- 10. 退出处理 ----
echo.
if %EXIT_CODE% equ 0 (
    echo [OK] 应用已正常退出
) else (
    echo [信息] 应用已退出 (代码: %EXIT_CODE%)
    echo        如果在启动时闪退，请尝试手动运行:
    echo            .venv\Scripts\activate ^&^& python main.py
    pause
)
exit /b %EXIT_CODE%
