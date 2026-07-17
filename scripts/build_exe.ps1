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
        --name CultureTranslationWorkbench `
        --paths (Join-Path $ProjectRoot "src") `
        (Join-Path $ProjectRoot "main.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$ExePath = Join-Path $ProjectRoot "dist\CultureTranslationWorkbench\CultureTranslationWorkbench.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build failed. Missing $ExePath"
}

$DistRoot = Split-Path $ExePath -Parent
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
        Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }
    }
}

Copy-FileIfExists (Join-Path $ProjectRoot "collaboration\README.md") (Join-Path $SnapshotRoot "README.md")
Copy-DirIfExists (Join-Path $ProjectRoot "collaboration\shared\terminology") (Join-Path $SnapshotRoot "shared\terminology")
Copy-DirIfExists (Join-Path $ProjectRoot "collaboration\integration\manifests") (Join-Path $SnapshotRoot "integration\manifests")
Copy-FileIfExists (Join-Path $ProjectRoot "collaboration\integration\README.md") (Join-Path $SnapshotRoot "integration\README.md")

foreach ($GroupDir in @("A_image_translation", "B_terms_style", "C_text_audio_translation")) {
    Copy-FileIfExists `
        (Join-Path $ProjectRoot "collaboration\groups\$GroupDir\README.md") `
        (Join-Path $SnapshotRoot "groups\$GroupDir\README.md")
}

Copy-DirIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\A_image_translation\deliverables\notes") `
    (Join-Path $SnapshotRoot "groups\A_image_translation\deliverables\notes")
Copy-DirIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\A_image_translation\deliverables\extracted_20260715\manifests") `
    (Join-Path $SnapshotRoot "groups\A_image_translation\deliverables\extracted_20260715\manifests")
Copy-DirIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\B_terms_style\prompts") `
    (Join-Path $SnapshotRoot "groups\B_terms_style\prompts")
Copy-DirIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\B_terms_style\deliverables\notes") `
    (Join-Path $SnapshotRoot "groups\B_terms_style\deliverables\notes")
Copy-DirIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\C_text_audio_translation\deliverables\notes") `
    (Join-Path $SnapshotRoot "groups\C_text_audio_translation\deliverables\notes")
Copy-FileIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\C_text_audio_translation\deliverables\docx_translation\revised_20260717\README.md") `
    (Join-Path $SnapshotRoot "groups\C_text_audio_translation\deliverables\docx_translation\revised_20260717\README.md")
Copy-FileIfExists `
    (Join-Path $ProjectRoot "collaboration\groups\C_text_audio_translation\deliverables\audio_video_workflow\revised_20260717\README.md") `
    (Join-Path $SnapshotRoot "groups\C_text_audio_translation\deliverables\audio_video_workflow\revised_20260717\README.md")

Write-Host "Build ready: $ExePath"
Write-Host "Collaboration snapshot ready: $SnapshotRoot"
