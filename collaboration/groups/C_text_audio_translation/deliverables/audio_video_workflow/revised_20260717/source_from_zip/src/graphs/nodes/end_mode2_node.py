"""
模式2结束节点 - 输出成品音视频提示
"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import EndMode2Input, EndMode2Output


logger = logging.getLogger(__name__)


def end_mode2_node(
    state: EndMode2Input,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EndMode2Output:
    """
    title: 输出成品音视频
    desc: 生成提示消息,告知用户已完成音视频翻译回填。如果 TTS 配额耗尽导致部分失败,会在消息中显示降级信息
    integrations: 无
    """
    ctx = runtime.context

    logger.info(
        f"模式2结束,成品音视频已生成: {state.final_media_url}, "
        f"TTS音频数={len(state.tts_audio_urls)}, "
        f"期望音频数={state.expected_audio_count}"
    )
    if state.quota_exhausted:
        logger.warning(
            f"⚠️ TTS 配额耗尽降级:成功 {state.tts_success_count}/{state.tts_total_count} 段,"
            f"失败 segment_ids={state.tts_failed_segment_ids}"
        )

    # 构造基础提示消息
    # ⭐ 本版本:明确说明两套产物(N 个独立音频 + 1 个合并音频)
    # - segment_audio_urls: 一句一个(用户可单独下载每段)
    # - final_media_url: 合并的整段(给二维码扫码听)
    message_parts = [
        f"翻译回填成品已生成。\n\n",
        f"【一句一个音频】(共 {len(state.segment_audio_urls)} 段,按 orig_idx 排序):",
    ]
    for idx, seg_url in enumerate(state.segment_audio_urls):
        if seg_url:
            message_parts.append(f"  段{idx + 1}: {seg_url}")
    message_parts.append(
        f"\n【合并音频】(给二维码,扫码后听完整音频):\n  {state.final_media_url}"
    )
    message = "".join(message_parts)

    # ⭐ 修复(2024-XX-XX):code=4036 配额耗尽降级时,在最终消息里追加"部分成功"说明
    # 让用户清楚知道当前输出是降级结果,而不是完整音频
    if state.quota_exhausted and state.tts_error_message:
        message += (
            f"\n\n⚠️ 重要提示(TTS 配额耗尽降级):\n"
            f"{state.tts_error_message}\n\n"
            f"本次输出为部分成功的降级结果,如需完整音频请:\n"
            f"  1) 登录扣子平台 → 插件市场 → speech_synthesis → 升级套餐,或\n"
            f"  2) 等下月1日配额自动重置后重新执行工作流"
        )
    elif state.tts_failed_segment_ids:
        # ⭐ 修复(本版本):非配额原因的部分失败(网络/服务故障)也透传 tts_error_message
        # 让用户看到"X 段 TTS 失败,已用静音补位"的明确说明
        if state.tts_error_message:
            message += (
                f"\n\n⚠️ 部分 TTS 合成失败(已用静音段补位):\n"
                f"{state.tts_error_message}"
            )
        else:
            message += (
                f"\n\n⚠️ 部分 TTS 合成失败: {len(state.tts_failed_segment_ids)} 段,"
                f"失败的 segment_id: {','.join(state.tts_failed_segment_ids)}"
            )

    logger.info(f"输出提示消息: {message}")

    return EndMode2Output(
        message=message,
        segment_audio_urls=state.segment_audio_urls,  # ⭐ 本版本:透传每段独立 URL
    )