"""
ASR语音识别节点 - 从音视频中提取文本和时间戳
"""
import os
import logging
import requests
import base64
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ASRInput, ASROutput
from coze_coding_dev_sdk import ASRClient


logger = logging.getLogger(__name__)


def asr_recognition_node(
    state: ASRInput, 
    config: RunnableConfig, 
    runtime: Runtime[Context]
) -> ASROutput:
    """
    title: ASR语音识别
    desc: 从原始音视频中提取文本内容和时间戳信息,支持mp3/wav/mp4等格式
    integrations: ASR语音识别
    """
    ctx = runtime.context
    
    # 检查文件是否存在
    if state.media_file is None:
        raise Exception("模式1需要提供原始音视频文件,但media_file为空")
    
    logger.info(f"开始ASR识别,文件URL: {state.media_file.url}")
    
    try:
        # 初始化ASR客户端
        asr_client = ASRClient(ctx=ctx)
        
        # 先下载音频文件,然后转为base64传给ASR(避免URL过期问题)
        logger.info("下载音频文件...")
        audio_response = requests.get(state.media_file.url, timeout=30)
        if audio_response.status_code != 200:
            raise Exception(f"音频文件下载失败,状态码: {audio_response.status_code}")
        
        audio_data = audio_response.content
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        logger.info(f"音频文件下载成功,大小: {len(audio_data)} bytes")
        
        # 使用base64方式调用ASR识别
        recognized_text, response_data = asr_client.recognize(
            uid="workflow_user",
            base64_data=audio_base64
        )
        
        logger.info(f"ASR识别完成,识别文本长度: {len(recognized_text)}")
        logger.info(f"response_data结构: {response_data}")
        
        # 解析详细的时间戳信息
        result = response_data.get("result", {})
        logger.info(f"result结构: {result}")
        
        utterances = result.get("utterances", [])
        logger.info(f"提取到utterances列表,长度: {len(utterances)}")
        
        duration_ms = result.get("duration", 0) or response_data.get("audio_info", {}).get("duration", 0)
        
        # 构造ASR结果数组
        asr_result_list = []
        
        # 如果有utterances列表，按列表处理
        if utterances and len(utterances) > 0:
            for idx, utterance in enumerate(utterances):
                segment_id = f"seg{idx+1:03d}"
                start_time_ms = utterance.get("start_time", 0)
                end_time_ms = utterance.get("end_time", 0)
                text = utterance.get("text", "")
                
                # 格式化时间戳: HH:MM:SS
                start_time_str = format_timestamp(start_time_ms)
                end_time_str = format_timestamp(end_time_ms)
                
                asr_item = {
                    "segment_id": segment_id,
                    "start_time_ms": start_time_ms,
                    "end_time_ms": end_time_ms,
                    "start_time_str": start_time_str,
                    "end_time_str": end_time_str,
                    "text": text,
                    "duration_ms": end_time_ms - start_time_ms
                }
                asr_result_list.append(asr_item)
        else:
            # 如果没有utterances列表，使用result.text构造单条数据
            text = result.get("text", "")
            if text:
                logger.info(f"没有utterances列表，使用完整文本构造数据，文本长度: {len(text)}")
                logger.info(f"【关键诊断】完整文本内容: 【{text}】")
                logger.info(f"【关键诊断】完整文本包含标点符号: 句号({text.count('。')})个，感叹号({text.count('！')})个，问号({text.count('？')})个")
                
                asr_item = {
                    "segment_id": "seg001",
                    "start_time_ms": 0,
                    "end_time_ms": duration_ms,
                    "start_time_str": format_timestamp(0),
                    "end_time_str": format_timestamp(duration_ms),
                    "text": text,
                    "duration_ms": duration_ms
                }
                asr_result_list.append(asr_item)
                logger.info(f"构造单条ASR数据完成，text字段内容: 【{asr_item['text']}】")
                logger.info(f"构造单条ASR数据: {asr_item}")
        
        logger.info(f"提取到{len(asr_result_list)}个语音片段")
        
        return ASROutput(
            asr_result=asr_result_list,
            original_audio_url=state.media_file.url
        )
        
    except Exception as e:
        logger.error(f"ASR识别失败: {str(e)}")
        raise Exception(f"ASR语音识别失败: {str(e)}")


def format_timestamp(ms: int) -> str:
    """
    将毫秒时间戳转换为HH:MM:SS格式
    """
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"