$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ToolRoot = "D:\AI_GUI_DevTools"
$PipCache = Join-Path $ToolRoot "pip-cache"

New-Item -ItemType Directory -Force -Path $PipCache | Out-Null
$env:PIP_CACHE_DIR = $PipCache

function New-ProjectVenv {
    if (Test-Path $VenvPython) {
        return
    }

    $created = $false
    try {
        & py -3.11 -m venv $VenvDir
        $created = $true
    }
    catch {
        try {
            & py -3.12 -m venv $VenvDir
            $created = $true
        }
        catch {
            & python -m venv $VenvDir
            $created = $true
        }
    }

    if (-not $created -or -not (Test-Path $VenvPython)) {
        throw "Failed to create virtual environment."
    }
}

New-ProjectVenv

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host "Environment ready: $VenvPython"
