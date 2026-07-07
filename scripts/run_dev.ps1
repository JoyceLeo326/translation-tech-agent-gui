$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $VenvPython (Join-Path $ProjectRoot "main.py")

