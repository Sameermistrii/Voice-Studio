@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Voice Studio setup
echo This downloads Python packages, CUDA PyTorch, OmniVoice, F5-TTS, Vocos, and Whisper.
echo Keep this window open. First run can take 30-90 minutes.
echo.

where winget >nul 2>&1
if errorlevel 1 (
  echo winget not found. Install "App Installer" from the Microsoft Store, then re-run setup.bat.
)

set "USE_PY="
set "PYEXE="
call :find_python
if not defined PYEXE if not defined USE_PY (
  echo Python 3.11 not found. Installing with winget...
  winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  call :find_python
)

if not defined PYEXE if not defined USE_PY (
  echo Could not install Python 3.11 automatically.
  echo Download 64-bit Python 3.11 from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH", then run setup.bat again.
  echo NVIDIA GPU driver is still required: https://www.nvidia.com/Download/index.aspx
  pause
  exit /b 1
)

if defined USE_PY (
  echo Using py -3.11
  py -3.11 gpu_jobs\install.py
) else (
  echo Using %PYEXE%
  "%PYEXE%" gpu_jobs\install.py
)
if errorlevel 1 (
  echo Install failed. Read README.md.
  pause
  exit /b 1
)
echo.
echo Done. Double-click "Start Voice Studio.bat"
pause
endlocal
exit /b 0

:find_python
set "USE_PY="
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "USE_PY=1"
    goto :eof
  )
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  goto :eof
)
if exist "%ProgramFiles%\Python311\python.exe" (
  set "PYEXE=%ProgramFiles%\Python311\python.exe"
  goto :eof
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)
goto :eof
