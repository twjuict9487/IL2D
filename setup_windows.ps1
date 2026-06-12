$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python launcher 'py' not found. Install Python 3.11+ first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    py -3 -m venv $VenvDir
}

& $PythonExe -m pip install --upgrade pip
& $PipExe install -r (Join-Path $RepoRoot "requirements.txt")

Write-Host ""
Write-Host "IL2D environment is ready." -ForegroundColor Green
Write-Host "Run game with:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe .\main.py"
