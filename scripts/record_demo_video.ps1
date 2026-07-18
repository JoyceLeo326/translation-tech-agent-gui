param(
    [string]$AssetsDir = "D:\AI_GUI_DevTools\releases\Yishu-v1.4.0-demo-assets"
)

$ErrorActionPreference = "Stop"
$AllowedRoot = [IO.Path]::GetFullPath("D:\AI_GUI_DevTools\releases")
$ResolvedAssets = [IO.Path]::GetFullPath($AssetsDir)
if (-not $ResolvedAssets.StartsWith($AllowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write demo outside $AllowedRoot"
}
New-Item -ItemType Directory -Path $ResolvedAssets -Force | Out-Null

$Ready = Join-Path $ResolvedAssets "record-ready.flag"
$Start = Join-Path $ResolvedAssets "record-start.flag"
$Screen = Join-Path $ResolvedAssets "screen-recording.mp4"
foreach ($File in ($Ready, $Start, $Screen)) {
    if (Test-Path -LiteralPath $File) {
        Remove-Item -LiteralPath $File -Force
    }
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Pythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$TourScript = Join-Path $PSScriptRoot "record_demo_tour.py"
$Timing = Join-Path $ResolvedAssets "timings.json"
$Ffmpeg = "D:\AI_GUI_DevTools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class RecordingNative {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$HiddenChatHandles = @(
    Get-Process -Name "ChatGPT" -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        ForEach-Object { $_.MainWindowHandle }
)
foreach ($Handle in $HiddenChatHandles) {
    [void][RecordingNative]::ShowWindow($Handle, 0)
}

try {
$Tour = Start-Process -FilePath $Pythonw `
    -ArgumentList @($TourScript, "--ready-file", $Ready, "--start-file", $Start, "--timing-file", $Timing) `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -PassThru

$Deadline = (Get-Date).AddSeconds(30)
while (-not (Test-Path -LiteralPath $Ready)) {
    if ((Get-Date) -gt $Deadline) {
        Stop-Process -Id $Tour.Id -Force
        throw "Demo tour did not become ready."
    }
    Start-Sleep -Milliseconds 200
}

$CaptureArguments = @(
    "-y", "-hide_banner", "-loglevel", "warning",
    "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "1", "-i", "desktop",
    "-t", "166", "-vf", "scale=1920:1200",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
    "-an", $Screen
)
$Capture = Start-Process -FilePath $Ffmpeg `
    -ArgumentList $CaptureArguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Milliseconds 1200
Set-Content -LiteralPath $Start -Value "" -Encoding ascii
$Capture.WaitForExit()
$Tour.WaitForExit()

if ($Capture.ExitCode -ne 0) { throw "Screen recording failed with exit code $($Capture.ExitCode)." }
if ($Tour.ExitCode -ne 0) { throw "Demo tour failed with exit code $($Tour.ExitCode)." }
if (-not (Test-Path -LiteralPath $Screen)) { throw "Screen recording was not created." }

Get-Item -LiteralPath $Screen | Select-Object FullName, Length
}
finally {
    foreach ($Handle in $HiddenChatHandles) {
        [void][RecordingNative]::ShowWindow($Handle, 8)
    }
}
