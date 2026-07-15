"""
音视频混音节点 - 将TTS音频与原视频混音合成成品
"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import MediaCompileInput, MediaCompileOutput
from coze_coding_dev_sdk.video_edit import VideoEditClient


logger = logging.getLogger(__name__)


def media_compile_node(
    state: MediaCompileInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> MediaCompileOutput:
    """
    title: 音视频混音合成
    desc: 将TTS音频按时间轴参数混音替换原视频音轨,生成成品音视频
    integrations: 音视频处理
    """
    ctx = runtime.context
    
    logger.info(f"开始音视频混音,共{len(state.tts_audio_urls)}个音频片段")
    logger.info(f"原始音频URL: {state.original_audio_url}")
    
    try:
        # 初始化视频编辑客户端
        video_client = VideoEditClient(ctx=ctx)
        
        # 检查是否有TTS音频
        if len(state.tts_audio_urls) == 0:
            # ⭐ 兜底:如果上游 batch_tts_node 降级失败(tts_audio_urls空)但有原音频,直接透传
            # 场景:模式二(只传Excel) + TTS 配额耗尽 → batch_tts_node 降级失败(无原音频可降级)
            # 进一步兜底:media_compile_node 直接返回原视频 URL,让工作流能跑通
            if state.original_audio_url:
                logger.warning("=" * 70)
                logger.warning("⚠️ 媒体混音降级模式已启用: tts_audio_urls 为空,但有原音频可降级")
                logger.warning(f"   原音频 URL: {state.original_audio_url}")
                logger.warning("   💡 透传原音频(无 TTS 配音),如需真实 TTS 配音请升级 TTS 插件套餐")
                logger.warning("=" * 70)
                return MediaCompileOutput(
                    final_media_url=state.original_audio_url,
                    tts_audio_urls=[]
                )
            # 如果连原音频都没有,才抛异常
            logger.error("没有TTS音频可供混音,且无原音频可降级")
            raise Exception("没有有效的TTS音频数据,且无原音频可降级")
        
        # 判断原始文件类型(视频还是音频)
        original_url = state.original_audio_url or ""
        is_video_file = any(original_url.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv'])
        
        logger.info(f"原始文件类型判断: {'视频文件' if is_video_file else '音频文件'}")
        
        # 如果是纯音频文件,则无法使用视频编辑API进行混音
        # 直接返回合并后的TTS音频作为最终结果
        if not is_video_file:
            logger.warning("原始文件是音频,不支持视频+音频混音,直接返回TTS音频")
            
            if len(state.tts_audio_urls) == 1:
                final_media_url = state.tts_audio_urls[0]
                logger.info(f"直接返回单个TTS音频: {final_media_url}")
            else:
                # 多个TTS音频,尝试使用concat_videos合并(将音频作为视频轨道)
                logger.info(f"尝试合并{len(state.tts_audio_urls)}个TTS音频")
                try:
                    concat_response = video_client.concat_videos(
                        videos=state.tts_audio_urls
                    )
                    final_media_url = concat_response.url
                    logger.info(f"音频合并完成: {final_media_url}")
                except Exception as e:
                    logger.warning(f"音频合并失败: {str(e)},使用第一个TTS音频作为最终结果")
                    final_media_url = state.tts_audio_urls[0]
            
            return MediaCompileOutput(
                final_media_url=final_media_url,
                tts_audio_urls=state.tts_audio_urls
            )
        
        # 如果是视频文件,则使用compile_video_audio进行视频+音频混音
        if len(state.tts_audio_urls) == 1:
            # 只有一个音频,直接混音
            tts_audio_url = state.tts_audio_urls[0]
            logger.info(f"单个TTS音频,准备混音: {tts_audio_url}")
            
            # 使用compile_video_audio混音
            # is_audio_reserve=False表示替换原始音频
            response = video_client.compile_video_audio(
                video=original_url,  # 原始视频URL
                audio=tts_audio_url,  # TTS音频URL
                is_audio_reserve=False,  # 替换原始音频,不保留
                is_video_audio_sync=False  # 不强制同步时长
            )
            
            final_media_url = response.url
            logger.info(f"混音完成,成品URL: {final_media_url}")
            
        else:
            # 多个TTS音频片段
            # 先合并所有TTS音频
            logger.info(f"合并{len(state.tts_audio_urls)}个TTS音频片段")
            
            concat_response = video_client.concat_videos(
                videos=state.tts_audio_urls
            )
            
            # 合并后的URL
            merged_audio_url = concat_response.url
            logger.info(f"音频合并完成: {merged_audio_url}")
            
            # 然后与原始视频混音
            response = video_client.compile_video_audio(
                video=original_url,
                audio=merged_audio_url,
                is_audio_reserve=False,
                is_video_audio_sync=False
            )
            
            final_media_url = response.url
            logger.info(f"混音完成,成品URL: {final_media_url}")
        
        return MediaCompileOutput(
            final_media_url=final_media_url,
            tts_audio_urls=state.tts_audio_urls
        )
            
    except Exception as e:
        logger.error(f"音视频混音失败: {str(e)}")
        raise Exception(f"音视频混音失败: {str(e)}")