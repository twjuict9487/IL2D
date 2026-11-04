$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$BasePython = $null
foreach ($Candidate in @("python", "py")) {
    if (-not (Get-Command $Candidate -ErrorAction SilentlyContinue)) { continue }
    $Args = if ($Candidate -eq "py") { @("-3") } else { @() }
    & $Candidate @Args -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $BasePython = $Candidate
        $BaseArgs = $Args
        break
    }
}
if (-not $BasePython) { throw "Python 3.11+ not found. Install Python first." }

if (-not (Test-Path $PythonExe)) {
    & $BasePython @BaseArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PythonExe)) { throw "Failed to create virtual environment." }
}

& $PythonExe -m pip install -r (Join-Path $RepoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

Write-Host ""
Write-Host "IL2D environment is ready." -ForegroundColor Green
Write-Host "Run game with:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe .\main.py"
