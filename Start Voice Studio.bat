@echo off
setlocal
cd /d "%~dp0"

set "PYW=%~dp0.venv\Scripts\pythonw.exe"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Missing app Python:
  echo   %PY%
  echo.
  echo Run setup.bat first. You need Python 3.11, ffmpeg, and an NVIDIA GPU.
  echo See README.md for the full install list.
  echo.
  pause
  exit /b 1
)

set "HF_HUB_DISABLE_XET=1"
if exist "D:\HuggingFace" set "HF_HOME=D:\HuggingFace"

if exist "%PYW%" (
  start "Voice Studio" "%PYW%" "%~dp0app.py"
) else (
  start "Voice Studio" "%PY%" "%~dp0app.py"
)
endlocal
