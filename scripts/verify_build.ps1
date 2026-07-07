$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ExePath = Join-Path $ProjectRoot "dist\AgentGuiStarter\AgentGuiStarter.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Missing virtual environment. Run scripts\setup_env.ps1 first."
}

Push-Location $ProjectRoot
try {
    & $VenvPython (Join-Path $ProjectRoot "main.py") --self-check
    & $VenvPython (Join-Path $ProjectRoot "main.py") --smoke-test

    if (-not (Test-Path $ExePath)) {
        throw "Missing packaged executable. Run scripts\build_exe.ps1 first."
    }

    $smoke = Start-Process -FilePath $ExePath -ArgumentList "--smoke-test" -PassThru -Wait
    if ($smoke.ExitCode -ne 0) {
        throw "Packaged smoke test failed with exit code $($smoke.ExitCode)."
    }

    $gui = Start-Process -FilePath $ExePath -PassThru
    Start-Sleep -Seconds 5
    $proc = Get-Process -Id $gui.Id -ErrorAction SilentlyContinue
    if (-not $proc) {
        throw "GUI process exited during startup."
    }
    if ($proc.MainWindowTitle -ne "Agent GUI Starter") {
        throw "Unexpected GUI title: $($proc.MainWindowTitle)"
    }
    Stop-Process -Id $proc.Id -Force
}
finally {
    Pop-Location
}

Write-Host "Verification passed."

