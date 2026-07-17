"""
智能模式判断节点
根据输入文件类型自动判断运行模式
"""
import logging
import time
import uuid
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import AutoModeJudgeInput, AutoModeJudgeOutput

logger = logging.getLogger(__name__)


def auto_mode_judge_node(
    state: AutoModeJudgeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> AutoModeJudgeOutput:
    """
    title: 根据输入文件类型自动判断运行模式，实现双模式智能分流。只有音频文件时，执行分之一预处理，在上传excel表格之后，自动复用预处理时上传的音频，执行分支二回填
    desc: 根据输入文件类型自动判断运行模式，实现双模式智能分流。只有音频文件时，执行分之一预处理，在上传excel表格之后，自动复用预处理时上传的音频，执行分支二回填

    判断逻辑：
    1. 上传Excel文件 → 模式2（回填），自动从Supabase复用原始音频URL
    2. 只上传音频文件 → 模式1（预处理），自动保存音频URL到Supabase
    3. 都不上传 → 报错
    """
    ctx = runtime.context

    logger.info("【智能模式判断节点】开始判断运行模式")

    # 检查输入文件
    has_media_file = state.media_file is not None and state.media_file.url
    has_excel_file = state.finalized_excel is not None and state.finalized_excel.url

    logger.info(f"输入文件检查: 音频={has_media_file}, Excel={has_excel_file}")

    # 智能判断逻辑（优先级：Excel文件 > 音频文件）
    if has_excel_file:
        # 识别到Excel文件 → 优先执行模式2（回填）
        # 自动从Supabase查询最新的原始音频URL
        cached_audio_url = None
        try:
            from tools.audio_session_storage import get_latest_audio_url
            cached_audio_url = get_latest_audio_url()
            if cached_audio_url:
                logger.info(f"从Supabase自动复用到原始音频URL: {cached_audio_url[:80]}...")
        except Exception as e:
            logger.warning(f"从Supabase查询音频URL失败: {e}")

        # ⭐ 修复:原视频来源优先级(支持 4 种方式,缺一不可)
        # 1) 用户显式传入 original_audio_url
        # 2) 本次调用中上传的 media_file(同时传媒体+Excel 的场景)
        # 3) Supabase 缓存(之前模式一保存的)
        # 4) 都没有 → 抛异常(让用户知道缺原视频)
        final_audio_url = (
            state.original_audio_url
            or (state.media_file.url if state.media_file else None)
            or cached_audio_url
        )

        if final_audio_url:
            run_mode = "回填・生成成品音视频"
            # 标注原视频来源(便于排查)
            if state.original_audio_url:
                source_desc = "用户显式传入的 original_audio_url"
            elif state.media_file:
                source_desc = "本次调用中上传的 media_file"
            else:
                source_desc = "Supabase 缓存(模式一保存)"
            logger.info(f"判断结果: {run_mode}（识别到Excel文件,原视频来源: {source_desc}）")
            return AutoModeJudgeOutput(
                run_mode=run_mode,
                finalized_excel=state.finalized_excel,
                original_audio_url=final_audio_url,  # 自动复用原始音频URL
                message=f"识别到Excel文件，自动启动回填模式（原视频来源: {source_desc}）"
            )
        else:
            # ⭐ 修复:mode 2 没有原视频时直接抛异常(不再静默继续)
            # 原因:之前 return error_msg 不抛异常,会导致:
            #   1) 工作流继续跑(看似成功)
            #   2) batch_tts_node 拿到 original_audio_url=None, TTS 失败时降级到静音兜底
            #   3) media_compile_node 合成"原视频+静音" → 用户拿到"无声音视频"
            # 现在直接抛异常,让用户明确知道"必须提供原视频"
            error_msg = (
                "识别到Excel文件，但未找到可用的原始音频。"
                "请按以下任一方式提供原视频：\n"
                "  ① 在本次调用中同时上传 media_file（原始音视频文件）\n"
                "  ② 显式传入 original_audio_url 参数\n"
                "  ③ 先单独跑一次模式一（只传 media_file）生成待审校Excel，再用本Excel跑模式二（回填）"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    elif has_media_file:
        # 只上传音频文件 → 模式1（预处理）
        # 自动保存音频URL到Supabase供模式二复用
        try:
            from tools.audio_session_storage import save_audio_url
            session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            audio_url = state.media_file.url
            # 根据URL后缀判断文件类型
            file_type = "video" if any(audio_url.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']) else "audio"
            save_audio_url(session_id, audio_url, file_type)
            logger.info(f"音频URL已保存到Supabase, session_id={session_id}, file_type={file_type}")
        except Exception as e:
            logger.warning(f"保存音频URL到Supabase失败(不影响模式一执行): {e}")

        run_mode = "预处理・生成待审校Excel"
        logger.info(f"判断结果: {run_mode}（只上传音频文件）")
        return AutoModeJudgeOutput(
            run_mode=run_mode,
            media_file=state.media_file,
            original_audio_url=state.media_file.url if state.media_file else None,
            message="检测到音频文件，自动启动预处理模式"
        )

    else:
        # 都不上传 → 报错
        error_msg = "未检测到任何输入文件，请上传音频文件或Excel文件"
        logger.error(error_msg)
        return AutoModeJudgeOutput(
            run_mode="预处理・生成待审校Excel",
            message=error_msg
        )
