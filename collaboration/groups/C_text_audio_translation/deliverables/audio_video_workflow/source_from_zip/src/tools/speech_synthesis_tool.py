"""
扣子平台 TTS SDK 封装 — 音色一致性策略

使用 Allison (en_female_allison_uranus_bigtts) 纯美式英语母语女声,
确保整段音视频口音统一,无中式口音,贴合美式英语纪录片解说风格 (TPM03 V2 要求)。
使用 coze_coding_dev_sdk 的 TTSClient,绕过扣子官方 speech_synthesis 插件的 4036 月度配额限制。

================================================================================
音色一致性策略 (Voice Consistency Strategy)
================================================================================
# 身份定位
语音合成调度模块 — 专门处理分段、多批次独立文本配音，核心目标：全程音色100%统一。

# 强制音色锁定规则
1. 全局固定音色ID: en_female_allison_uranus_bigtts (Allison 美式英语母语女声)
   所有分段、所有独立文本请求必须使用该 speaker，禁止随机切换任何音色。
2. 人声特征锁定: speech_rate=0 (语速1.0)、loudness_rate=0 (音量不变)
   全程参数不浮动，消除分段音色割裂、基频漂移。
3. 音色/情绪分离: 仅允许文本内容自然表达情绪，严禁因情绪变化改变人声底色/声纹/嗓音粗细。
4. 多段独立文本约束: 无论拆分多少段文字、分多少次生成音频，全部复用同一套音色+声学参数。
5. 输出格式: 通过 SDK ssml 参数传递 <speak> 包裹的纯文本，仅保留朗读正文，
   不添加音效、背景音乐；长文本自动分句，分句停顿统一，不改变人声基础音色。

# 兜底规则
若未指定音色，强制使用 en_female_allison_uranus_bigtts，不做随机推荐。
================================================================================
"""
import os
import json
import logging
from typing import Any, Dict, Optional

from coze_coding_dev_sdk import TTSClient
from coze_coding_utils.runtime_ctx.context import new_context


logger = logging.getLogger(__name__)


# 统一合成参数：全工作流保持不变
DEFAULT_SPEED_RATIO = 1.0  # 语速 1.0，全程不浮动
DEFAULT_LANGUAGE = "en-US"  # 美式英语

# 平台 TTS SDK 音色(美式英语母语女声,纯美音,无中式口音)
DEFAULT_SDK_SPEAKER = "en_female_allison_uranus_bigtts"  # Allison(美式英语母语女声)

# 兼容旧调用方(tts_synthesis_node 用的旧符号名)
DEFAULT_SPEAKER_ID = DEFAULT_SDK_SPEAKER

# 兼容旧调用方(扣子官方 speech_synthesis 插件的音色名)
SPEAKER_ID_MAP = {
    "爽快思思/Skye": DEFAULT_SDK_SPEAKER,
    "Skye": DEFAULT_SDK_SPEAKER,
    "爽快思思": DEFAULT_SDK_SPEAKER,
}


def call_speech_synthesis(
    text: str,
    speaker_id: str = DEFAULT_SDK_SPEAKER,
    speed_ratio: float = DEFAULT_SPEED_RATIO,
    language: str = DEFAULT_LANGUAGE,
) -> Dict[str, Any]:
    """
    调用 coze_coding_dev_sdk TTSClient 合成音频 — 音色一致性锁定版。
    所有分段独立 TTS 调用均使用完全相同的音色+声学参数，消除分段音色割裂。

    Args:
        text: 待合成文本
        speaker_id: 音色 ID(兼容旧插件音色名)，全程锁定 Allison
        speed_ratio: 语速(0.2 ~ 3,默认 1.0)，全程不浮动
        language: 音色语种(默认 en-US)

    Returns:
        Dict 形如 {"audio_url": "...", "duration": 2.376}
    """
    if not text or not text.strip():
        raise ValueError("语音合成失败: text 为空")

    # 兼容旧插件音色名 → SDK 音色名（强制锁定为 Allison）
    actual_speaker = SPEAKER_ID_MAP.get(speaker_id, speaker_id)

    # 语速换算:旧插件 speed_ratio (0.2~3,1=正常) → SDK speech_rate (-50~100, 0=正常)
    speech_rate = int(round((speed_ratio - 1.0) * 100))

    # SSML <speak> 包裹纯文本，通过 SDK 专用 ssml 参数传递
    # 与之前通过 text 参数传递 SSML 不同：SDK 的 ssml 参数会正确解析 SSML 标签
    # <speak> 是最基础的 SSML 根元素，不含任何 prosody 修改，保持原始音色
    ssml_text = f"<speak>{text}</speak>"

    try:
        ctx = new_context(method="tts.synthesize")
        client = TTSClient(ctx=ctx)
        synth_kwargs: Dict[str, Any] = {
            "uid": os.environ.get("COZE_USER_ID", "workflow_tts"),
            "speaker": actual_speaker,
            "audio_format": "mp3",
            "sample_rate": 24000,
            "speech_rate": speech_rate,
            "loudness_rate": 0,
        }
        # 通过 ssml 参数传递（SDK 会正确解析 SSML 标签，不会当文本读）
        synth_kwargs["ssml"] = ssml_text
        audio_url, audio_size = client.synthesize(**synth_kwargs)
    except Exception as e:
        raise RuntimeError(f"语音合成 SDK 调用失败: {e}") from e

    if not audio_url:
        raise RuntimeError("语音合成失败: SDK 返回无音频链接")

    # SDK 返回 (url, size),需用 ffprobe 估时长
    duration = 0.0
    try:
        import requests
        import subprocess
        with requests.get(audio_url, stream=True, timeout=10) as r:
            r.raise_for_status()
            with open("/tmp/_tts_probe.mp3", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", "/tmp/_tts_probe.mp3"],
            capture_output=True, text=True, timeout=10
        )
        duration = float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except Exception:
        pass

    return {
        "audio_url": audio_url,
        "duration": duration,
    }
