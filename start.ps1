<#
.SYNOPSIS
    MIDI Show — 一键启动脚本 (Windows PowerShell)
.DESCRIPTION
    自动检查 Python、创建/复用虚拟环境、安装依赖、启动 MIDI Show 应用。
    比 start.bat 更健壮：更好的 Unicode 支持、彩色输出、错误处理。
#>

$Host.UI.RawUI.WindowTitle = "MIDI Show - VRChat MIDI Player"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR = Join-Path $ROOT ".venv"
$PYTHON_CMD = "python"
$MIN_VERSION = [Version]"3.9.0"

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Color, [string]$Label, [string]$Message)
    Write-Host "[$Label] " -ForegroundColor $Color -NoNewline
    Write-Host $Message
}

function Write-OK    { Write-Status -Color Green  -Label "OK"    -Message $args }
function Write-Warn  { Write-Status -Color Yellow -Label "WARN"  -Message $args }
function Write-Info  { Write-Status -Color Cyan   -Label ".."    -Message $args }
function Write-Error { Write-Status -Color Red    -Label "ERROR" -Message $args }

Write-Host "========================================" -ForegroundColor Magenta
Write-Host "   MIDI Show - VRChat MIDI Player"       -ForegroundColor Magenta
Write-Host "   One-Click Launcher (PowerShell)"      -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# ---- 1. 检查 Python ----
try {
    $pyVersionStr = & $PYTHON_CMD --version 2>&1
    Write-OK "检测到 $pyVersionStr"
} catch {
    Write-Error "未找到 Python。请确保 Python 已安装并加入 PATH。"
    Write-Host "  下载: https://www.python.org/downloads/"
    Write-Host "  安装时请勾选 'Add Python to PATH'"
    Read-Host "按回车键退出"
    exit 1
}

# ---- 2. 检查 Python 最低版本 ----
$pyVersion = [Version](($pyVersionStr -split ' ')[1].Trim())
if ($pyVersion.Major -gt 3) {
    Write-Error "Python 主版本过高 ($pyVersion)，当前仅支持 Python 3.x"
    Read-Host "按回车键退出"
    exit 1
}
if ($pyVersion -lt $MIN_VERSION) {
    Write-Error "Python 版本过低 ($pyVersion)，需要 $MIN_VERSION 或更高"
    Read-Host "按回车键退出"
    exit 1
}
Write-OK "Python 版本满足要求 (>= $MIN_VERSION)"

# ---- 3. 检查/创建虚拟环境 ----
$venvPython = Join-Path $VENV_DIR "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Info "正在创建虚拟环境..."
    try {
        & $PYTHON_CMD -m venv $VENV_DIR
        Write-OK "虚拟环境已创建: $VENV_DIR"
    } catch {
        Write-Error "虚拟环境创建失败: $_"
        Read-Host "按回车键退出"
        exit 1
    }
} else {
    Write-OK "虚拟环境已存在"
}

# ---- 4. 激活虚拟环境 & 升级 pip ----
$activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Error "虚拟环境不完整，请删除 .venv 目录后重试"
    Read-Host "按回车键退出"
    exit 1
}

# 在 PowerShell 中 dot-source 激活脚本
. $activateScript

Write-Info "检查 pip 版本..."
& $PYTHON_CMD -m pip install --upgrade pip -q

# ---- 5. 安装依赖 ----
Write-Info "安装依赖..."
try {
    & pip install -r (Join-Path $ROOT "requirements.txt") --prefer-binary
    if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }
    Write-OK "依赖安装完成"
} catch {
    Write-Warn "带 --prefer-binary 的安装失败，尝试普通安装..."
    try {
        & pip install -r (Join-Path $ROOT "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }
        Write-OK "依赖安装完成"
    } catch {
        Write-Error "依赖安装失败，请检查网络连接。"
        Write-Host "  可尝试手动执行:"
        Write-Host "    .venv\Scripts\activate"
        Write-Host "    pip install -r requirements.txt"
        Read-Host "按回车键退出"
        exit 1
    }
}

# ---- 6. 验证关键依赖 ----
try {
    & $PYTHON_CMD -c "import mido; import rtmidi; print('[OK] 关键依赖检查通过')"
    Write-OK "关键依赖导入验证通过"
} catch {
    Write-Warn "依赖导入验证未通过，可能存在兼容性问题。"
    Write-Warn "尝试: pip install --upgrade mido python-rtmidi python-osc"
}

# ---- 7. 启动应用 ----
Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "   [..] 正在启动 MIDI Show..."          -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

try {
    & $PYTHON_CMD (Join-Path $ROOT "main.py")
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error "启动失败: $_"
    $exitCode = 1
}

# ---- 8. 清理 ----
try { Deactivate } catch {}

Write-Host ""
if ($exitCode -eq 0) {
    Write-OK "应用已正常退出"
} else {
    Write-Warn "应用已退出 (代码: $exitCode)"
    Write-Host "  如果在启动时闪退，请尝试手动运行:"
    Write-Host "    .venv\Scripts\activate ; python main.py"
    Read-Host "按回车键退出"
}

exit $exitCode
