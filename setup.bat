@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3.11 -c "import sys" >nul 2>&1
  if %ERRORLEVEL%==0 (
    py -3.11 gpu_jobs\install.py
    goto :after
  )
)

python --version || (
  echo Install Python 3.11 64-bit from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH".
  echo Full list: README.md
  pause
  exit /b 1
)
python gpu_jobs\install.py

:after
if errorlevel 1 (
  echo Install failed. Read README.md "Complete install requirements".
  pause
  exit /b 1
)
echo.
echo Done. Double-click "Start Voice Studio.bat"
pause
endlocal
