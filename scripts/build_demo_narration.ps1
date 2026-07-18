param(
    [string]$OutputDir = "D:\AI_GUI_DevTools\releases\Yishu-v1.4.0-demo-assets"
)

$ErrorActionPreference = "Stop"
$FfmpegRoot = "D:\AI_GUI_DevTools\ffmpeg\ffmpeg-8.1.2-full_build\bin"
$Ffmpeg = Join-Path $FfmpegRoot "ffmpeg.exe"
$Ffprobe = Join-Path $FfmpegRoot "ffprobe.exe"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$Narration = @(
    "这是译述，中国文化多模态外译工作台。它把图片、Word、音视频、文化术语和智能工作流整合在同一套可审校界面中。无需密钥也能完整演示，连接自己的模型后即可真实在线处理。",
    "左下角的模型接口是全局连接中心。用户可以选择 OpenAI、Ollama、LM Studio 或其他兼容服务，也可以连接 Coze 多模型工作流。所有密钥只保存在本机，不会上传到公开仓库。",
    "回到开始页，选择图片、Word、音频或视频，系统会自动进入对应流程。每种任务都说明当前步骤、人工确认位置和最后能得到的文件，小白也不需要理解项目目录。",
    "Word 流程先提取正文、表格、页眉和页脚，生成 Excel 译文确认表。在线模型分批翻译，人工审核后再通过 Word XML 精确回填，保留原来的图片和版式。",
    "音视频流程先在线转写并逐句切分，再进入术语约束翻译和人工审核。最终优先调用在线语音模型生成英文配音；接口不支持时，会自动回退到 Windows 本机语音。",
    "Coze 多模型精译是项目的核心能力。它先识别文化术语和儿童文学风格，再让 Kimi、DeepSeek 和豆包分别初译并交叉评议，最后由 GLM 融合终稿。真实工作流包含十八个节点和二十八条连接。",
    "文化术语库已经汇总二百五十一条可检索约束。译法、出处页码、上下文和官方来源可以一起查看，并能一键加入当前翻译任务，保证多人协作中的表达一致。",
    "批量处理把资源扫描、术语加载、文档回填、音频生成和最终质检放进同一条工作流。在线模型已连接时会追加语义质检，未连接时仍然完成全部本地结构验收。",
    "成果总览不是概念图，而是可打开的交付证据。这里集中展示七十一条图文审校、五套 Word 实测、二百一十九句英文配音，以及完整的资源索引和验收记录。",
    "所有新生成的 Word、Excel、图片、配音和报告都会进入统一成品区。老师或审核人员可以直接双击打开，不需要再按原来的协作分组查找文件。",
    "这就是译述一点四版本。它既能离线演示完整流程，也能连接用户自己的模型 API 执行真实任务。Windows 完整包、源代码、架构说明和在线产品导览都已经公开发布。"
)

Add-Type -AssemblyName System.Speech
$Synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
$Synthesizer.SelectVoice("Microsoft Huihui Desktop")
$Synthesizer.Rate = 3
$Synthesizer.Volume = 100

$AudioFiles = @()
for ($Index = 0; $Index -lt $Narration.Count; $Index++) {
    $Path = Join-Path $OutputDir ("{0:D2}.wav" -f $Index)
    $Synthesizer.SetOutputToWaveFile($Path)
    $Synthesizer.Speak($Narration[$Index])
    $Synthesizer.SetOutputToNull()
    $AudioFiles += $Path
}
$Synthesizer.Dispose()

$GapSeconds = 1.2
$Silence = Join-Path $OutputDir "silence.wav"
& $Ffmpeg -y -hide_banner -loglevel error -f lavfi -i "anullsrc=r=22050:cl=mono" -t $GapSeconds -c:a pcm_s16le $Silence
if ($LASTEXITCODE -ne 0) { throw "Could not create narration gap audio." }

$Starts = @()
$Cursor = 0.0
$ConcatLines = @()
for ($Index = 0; $Index -lt $AudioFiles.Count; $Index++) {
    $Starts += [math]::Round($Cursor, 3)
    $AudioPath = $AudioFiles[$Index]
    $EscapedAudio = $AudioPath.Replace("'", "''")
    $ConcatLines += "file '$EscapedAudio'"
    $DurationText = (& $Ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $AudioPath).Trim()
    $Cursor += [double]::Parse($DurationText, [Globalization.CultureInfo]::InvariantCulture)
    if ($Index -lt $AudioFiles.Count - 1) {
        $EscapedSilence = $Silence.Replace("'", "''")
        $ConcatLines += "file '$EscapedSilence'"
        $Cursor += $GapSeconds
    }
}

$ConcatFile = Join-Path $OutputDir "concat.txt"
[IO.File]::WriteAllLines($ConcatFile, $ConcatLines, (New-Object Text.UTF8Encoding($false)))
$OutputAudio = Join-Path $OutputDir "narration.wav"
& $Ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $ConcatFile -c:a pcm_s16le $OutputAudio
if ($LASTEXITCODE -ne 0) { throw "Could not combine narration audio." }

$Timing = [ordered]@{
    starts = $Starts
    audio_duration = [math]::Round($Cursor, 3)
}
$Timing | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir "timings.json") -Encoding utf8
Write-Host "Narration ready: $OutputAudio"
Write-Host "Duration: $($Timing.audio_duration) seconds"



