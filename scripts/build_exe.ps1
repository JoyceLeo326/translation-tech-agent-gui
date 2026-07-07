$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ToolRoot = "D:\AI_GUI_DevTools"
$PyInstallerCache = Join-Path $ToolRoot "pyinstaller-cache"

New-Item -ItemType Directory -Force -Path $PyInstallerCache | Out-Null
$env:PYINSTALLER_CONFIG_DIR = $PyInstallerCache

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name AgentGuiStarter `
        --paths (Join-Path $ProjectRoot "src") `
        (Join-Path $ProjectRoot "main.py")
}
finally {
    Pop-Location
}

$ExePath = Join-Path $ProjectRoot "dist\AgentGuiStarter\AgentGuiStarter.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build failed. Missing $ExePath"
}

Write-Host "Build ready: $ExePath"
