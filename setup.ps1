# ValoTalk 一键安装
# 用法：右键 → 使用 PowerShell 运行，或在终端里
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "`n=== ValoTalk 安装 ===`n" -ForegroundColor Cyan

# ---------- 1. 找 Python ----------
$candidates = @()
foreach ($p in @("python", "py", "D:\python\python.exe", "C:\Python313\python.exe",
                 "C:\Python312\python.exe", "C:\Python311\python.exe")) {
    $candidates += $p
}
$PY = $null
foreach ($c in $candidates) {
    try {
        $v = & $c -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) {
            $parts = $v.Split(".")
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10) {
                $PY = $c
                Write-Host "找到 Python $v  ->  $c" -ForegroundColor Green
                break
            }
        }
    } catch { }
}
if (-not $PY) {
    Write-Host "没找到 Python 3.10+，请先装 https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "安装时务必勾选 Add Python to PATH。"
    Read-Host "按回车退出"
    exit 1
}

# ---------- 2. 装依赖 ----------
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple"
$env:PIP_TRUSTED_HOST = "mirrors.aliyun.com"
$env:HF_ENDPOINT = "https://hf-mirror.com"

Write-Host "`n[1/3] 安装 Python 依赖（阿里云镜像，约 1.5GB）…" -ForegroundColor Yellow
& $PY -m pip install --upgrade pip
& $PY -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "依赖安装失败，检查网络后重跑本脚本。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host "`n[2/4] 安装 GPU 加速库（NVIDIA 显卡，约 1.2GB；没有就跳过）…" -ForegroundColor Yellow
Write-Host "      没有这一步，识别会慢 15 倍以上，基本没法实时用。" -ForegroundColor DarkGray
& $PY -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
if ($LASTEXITCODE -ne 0) {
    Write-Host "  GPU 库没装上，会走 CPU（很慢）。可以稍后单独装。" -ForegroundColor DarkYellow
}

# ---------- 3. 预下模型 ----------
Write-Host "`n[3/4] 预下载语音识别模型 small（约 480MB，走 hf-mirror）…" -ForegroundColor Yellow
Write-Host "      想更小可以改用 base/tiny：改 config.json 里 asr.model" -ForegroundColor DarkGray
& $PY -X utf8 -c @"
import os
os.environ.setdefault('HF_ENDPOINT','https://hf-mirror.com')
from faster_whisper import WhisperModel
import numpy as np
m = WhisperModel('small', device='cpu', compute_type='int8', download_root='models', num_workers=1)
m.transcribe(np.zeros(16000, dtype=np.float32), language='en')[0]
print('模型就绪')
"@

Write-Host "`n[4/4] 环境自检" -ForegroundColor Yellow
& $PY -X utf8 tools\probe_env.py

Write-Host "`n=== 装完了。双击 run.bat 启动。 ===" -ForegroundColor Cyan
Write-Host "别忘了按 README 第 2 节改游戏里的麦克风设置。" -ForegroundColor Cyan
Read-Host "按回车关闭"