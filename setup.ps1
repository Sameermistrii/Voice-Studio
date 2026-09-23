#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Voice Studio setup" -ForegroundColor Green
Write-Host "Requires: Windows 10/11 x64, Python 3.11, NVIDIA GPU (4GB+), ffmpeg, ~15 GB disk"
Write-Host "Full list: README.md"

$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  try {
    & py -3.11 -c "import sys" | Out-Null
    if ($LASTEXITCODE -eq 0) { $py = "py" }
  } catch { }
}
if ($py -eq "py") {
  & py -3.11 gpu_jobs\install.py
} else {
  python gpu_jobs\install.py
}
if ($LASTEXITCODE -ne 0) { throw "install.py failed" }
Write-Host ""
Write-Host "Launch: .\.venv\Scripts\python.exe app.py"
Write-Host "Or double-click Start Voice Studio.bat"
