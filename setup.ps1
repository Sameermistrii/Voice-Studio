#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Voice Studio setup" -ForegroundColor Green
Write-Host "This downloads Python packages, CUDA PyTorch, OmniVoice, F5-TTS, Vocos, and Whisper."

function Test-Python311 {
  param([string]$Exe, [string[]]$PrefixArgs = @())
  try {
    & $Exe @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)" | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

$pyLauncher = $false
$pyExe = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  if (Test-Python311 -Exe "py" -PrefixArgs @("-3.11")) { $pyLauncher = $true }
}
if (-not $pyLauncher) {
  foreach ($path in @(
      "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
      "$env:ProgramFiles\Python311\python.exe"
    )) {
    if (Test-Path $path) { $pyExe = $path; break }
  }
}
if (-not $pyLauncher -and -not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
  if (Test-Python311 -Exe "python") { $pyExe = "python" }
}

if (-not $pyLauncher -and -not $pyExe) {
  Write-Host "Python 3.11 not found. Installing with winget..."
  winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  if (Get-Command py -ErrorAction SilentlyContinue) {
    if (Test-Python311 -Exe "py" -PrefixArgs @("-3.11")) { $pyLauncher = $true }
  }
  if (-not $pyLauncher) {
    foreach ($path in @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
      )) {
      if (Test-Path $path) { $pyExe = $path; break }
    }
  }
}

if ($pyLauncher) {
  py -3.11 gpu_jobs\install.py
} elseif ($pyExe) {
  & $pyExe gpu_jobs\install.py
} else {
  throw "Python 3.11 is required. Install it from https://www.python.org/downloads/ then re-run."
}
if ($LASTEXITCODE -ne 0) { throw "install.py failed" }
Write-Host ""
Write-Host "Launch: .\.venv\Scripts\python.exe app.py"
Write-Host "Or double-click Start Voice Studio.bat"
