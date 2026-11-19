@echo off
setlocal
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "D:\python\python.exe" set "PY=D:\python\python.exe"
if not defined PY if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY if exist "C:\Python311\python.exe" set "PY=C:\Python311\python.exe"

if not defined PY (
    echo.
    echo [ERROR] Python 3.10+ not found.
    echo Install it from https://www.python.org/downloads/ and tick "Add to PATH".
    echo.
    pause
    exit /b 1
)

set "HF_ENDPOINT=https://hf-mirror.com"
set "PYTHONIOENCODING=utf-8"

echo Starting ValoTalk with %PY% ...
echo.

"%PY%" -X utf8 -m valotalk
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [ERROR] ValoTalk exited with code %RC%
    echo Check what is missing by running:
    echo     "%PY%" -X utf8 tools\probe_env.py
    echo.
    pause
)