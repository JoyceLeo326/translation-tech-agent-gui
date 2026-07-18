$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ToolRoot = "D:\AI_GUI_DevTools"
$PyInstallerCache = Join-Path $ToolRoot "pyinstaller-cache"
$FontData = "$(Join-Path $ProjectRoot 'assets\fonts');assets\fonts"
$IconData = "$(Join-Path $ProjectRoot 'assets\icons');assets\icons"
$DistRoot = Join-Path $ProjectRoot "dist\CultureTranslate"

New-Item -ItemType Directory -Force -Path $PyInstallerCache | Out-Null
$env:PYINSTALLER_CONFIG_DIR = $PyInstallerCache

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

& $VenvPython (Join-Path $PSScriptRoot "build_unified_delivery.py")
if ($LASTEXITCODE -ne 0) {
    throw "Unified delivery build failed with exit code $LASTEXITCODE."
}

& $VenvPython (Join-Path $PSScriptRoot "verify_delivery.py")
if ($LASTEXITCODE -ne 0) {
    throw "Delivery verification failed with exit code $LASTEXITCODE."
}

if (Test-Path $DistRoot) {
    $resolvedDist = (Resolve-Path $DistRoot).Path
    $allowedDistRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "dist"))
    if (-not $resolvedDist.StartsWith($allowedDistRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean unexpected build directory: $resolvedDist"
    }
    $emptyMirror = Join-Path $ToolRoot "empty-dist-mirror"
    New-Item -ItemType Directory -Force -Path $emptyMirror | Out-Null
    $null = & robocopy.exe $emptyMirror $resolvedDist /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    $cleanExitCode = $LASTEXITCODE
    if ($cleanExitCode -ge 8) {
        throw "Build directory cleanup failed with robocopy exit code $cleanExitCode."
    }
    Remove-Item -LiteralPath $resolvedDist -Force
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name CultureTranslate `
        --icon (Join-Path $ProjectRoot "assets\app_icon.ico") `
        --add-data $FontData `
        --add-data $IconData `
        --paths (Join-Path $ProjectRoot "src") `
        (Join-Path $ProjectRoot "main.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$ExePath = Join-Path $ProjectRoot "dist\CultureTranslate\CultureTranslate.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build failed. Missing $ExePath"
}

$SnapshotRoot = Join-Path $DistRoot "collaboration"

if (Test-Path $SnapshotRoot) {
    $resolvedSnapshot = (Resolve-Path $SnapshotRoot).Path
    $resolvedDist = (Resolve-Path $DistRoot).Path
    if (-not $resolvedSnapshot.StartsWith($resolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean unexpected snapshot path: $resolvedSnapshot"
    }
    Remove-Item -LiteralPath $SnapshotRoot -Recurse -Force
}

function Copy-FileIfExists {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

function Copy-DirIfExists {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path $Destination | Out-Null
        $null = & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
        $copyExitCode = $LASTEXITCODE
        if ($copyExitCode -ge 8) {
            throw "Directory snapshot copy failed with robocopy exit code $copyExitCode."
        }
    }
}

Copy-FileIfExists (Join-Path $ProjectRoot ".env.example") (Join-Path $DistRoot ".env.example")
Copy-DirIfExists (Join-Path $ProjectRoot "collaboration") $SnapshotRoot

$ReleaseRoot = Join-Path $ToolRoot "releases"
$ReleaseArchive = Join-Path $ReleaseRoot "CultureTranslate-v1.1.0-windows-x64.zip"
New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
& $VenvPython (Join-Path $PSScriptRoot "package_release.py") --source $DistRoot --output $ReleaseArchive
if ($LASTEXITCODE -ne 0) {
    throw "Release archive creation failed with exit code $LASTEXITCODE."
}

Write-Host "Build ready: $ExePath"
Write-Host "Collaboration snapshot ready: $SnapshotRoot"
Write-Host "Release archive ready: $ReleaseArchive"
