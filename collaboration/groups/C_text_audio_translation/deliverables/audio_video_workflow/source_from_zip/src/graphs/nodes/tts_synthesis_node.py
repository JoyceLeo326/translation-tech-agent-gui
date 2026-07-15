"""
TTS语音合成节点 - 将人工审核列英文文本转为标准美式英语语音

使用扣子平台官方「语音合成 speech_synthesis」插件
固定参数：爽快思思/Skye + language=en-US + speed_ratio=1
解决中文字色说英文带中式口音的问题。
"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import TTSInput, TTSOutput
from tools.speech_synthesis_tool import (
    call_speech_synthesis,
    DEFAULT_SPEAKER_ID,
    DEFAULT_LANGUAGE,
    DEFAULT_SPEED_RATIO,
)


logger = logging.getLogger(__name__)


def tts_synthesis_node(
    state: TTSInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TTSOutput:
    """
    title: 英文语音合成
    desc: 将人工审核列的英文文本合成为标准美式英语配音，使用扣子官方爽快思思/Skye英文母语音色，发音自然标准无中式口音
    integrations: 扣子语音合成插件
    """
    ctx = runtime.context  # noqa: F841 保留对运行时上下文的引用

    if not state.english_text or not state.english_text.strip():
        raise Exception(f"TTS合成失败: {state.segment_id} 文本为空")

    text_preview = (
        state.english_text[:60] + "..."
        if len(state.english_text) > 60
        else state.english_text
    )
    logger.info(
        f"[TTS-{state.segment_id}] 合成中 | 音色={DEFAULT_SPEAKER_ID} | "
        f"language={DEFAULT_LANGUAGE} | speed_ratio={DEFAULT_SPEED_RATIO} | "
        f"文本={text_preview!r}"
    )

    try:
        result = call_speech_synthesis(
            text=state.english_text,
            speaker_id=DEFAULT_SPEAKER_ID,
            speed_ratio=DEFAULT_SPEED_RATIO,
            language=DEFAULT_LANGUAGE,
        )
        audio_url = result["audio_url"]
        duration = result["duration"]

        logger.info(
            f"[TTS-{state.segment_id}] ✅ 合成完成 | duration={duration:.3f}s | "
            f"URL={audio_url[:80]}..."
        )

        return TTSOutput(
            audio_url=audio_url,
            segment_id=state.segment_id,
        )

    except Exception as e:
        logger.error(f"[TTS-{state.segment_id}] ❌ 合成失败: {e}")
        raise Exception(f"TTS语音合成失败: {e}") from e
