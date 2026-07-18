$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ExePath = Join-Path $ProjectRoot "dist\CultureTranslate\CultureTranslate.exe"
$SerifFontPath = Join-Path $ProjectRoot "dist\CultureTranslate\_internal\assets\fonts\NotoSerifSC-VF.ttf"
$LucideIconPath = Join-Path $ProjectRoot "dist\CultureTranslate\_internal\assets\icons\lucide\play.svg"
$ChannelIconPath = Join-Path $ProjectRoot "dist\CultureTranslate\_internal\assets\icons\lucide\scan-text.svg"
$LucideLicensePath = Join-Path $ProjectRoot "dist\CultureTranslate\_internal\assets\icons\lucide\LICENSE"

if (-not (Test-Path $VenvPython)) {
    throw "Missing virtual environment. Run scripts\setup_env.ps1 first."
}

Push-Location $ProjectRoot
try {
    & $VenvPython (Join-Path $ProjectRoot "scripts\verify_delivery.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Delivery verification failed with exit code $LASTEXITCODE."
    }
    & $VenvPython (Join-Path $ProjectRoot "main.py") --self-check
    & $VenvPython (Join-Path $ProjectRoot "main.py") --smoke-test

    if (-not (Test-Path $ExePath)) {
        throw "Missing packaged executable. Run scripts\build_exe.ps1 first."
    }
    if (-not (Test-Path $SerifFontPath)) {
        throw "Missing packaged display font: $SerifFontPath"
    }
    if (-not (Test-Path $LucideIconPath)) {
        throw "Missing packaged Lucide icon: $LucideIconPath"
    }
    if (-not (Test-Path $ChannelIconPath)) {
        throw "Missing packaged channel icon: $ChannelIconPath"
    }
    if (-not (Test-Path $LucideLicensePath)) {
        throw "Missing packaged Lucide license: $LucideLicensePath"
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
    if ([string]::IsNullOrWhiteSpace($proc.MainWindowTitle)) {
        throw "GUI window title is empty."
    }
    Stop-Process -Id $proc.Id -Force
}
finally {
    Pop-Location
}

Write-Host "Verification passed."
