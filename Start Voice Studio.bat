@echo off
cd /d "%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Missing app Python:
  echo   %~dp0.venv\Scripts\python.exe
  echo.
  echo Run setup.bat first. You need Python 3.11, ffmpeg, and an NVIDIA GPU.
  echo See README.md for the full install list.
  echo.
  pause
  exit /b 1
)

REM wscript hides the console. `start python.exe` opens Windows Terminal (often acrylic).
wscript.exe "%~dp0Start Voice Studio.vbs"
