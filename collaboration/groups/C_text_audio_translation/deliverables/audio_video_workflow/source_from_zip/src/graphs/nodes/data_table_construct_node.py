"""
数据表格构造节点 - 将ASR结果组装成标准Excel表格数据
"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import DataTableConstructInput, DataTableConstructOutput


logger = logging.getLogger(__name__)


def _ms_to_hms(ms: int) -> str:
    """
    将毫秒转为 HH:MM:SS.mmm 格式时间字符串

    Args:
        ms: 毫秒数

    Returns:
        HH:MM:SS.mmm 格式字符串
    """
    if ms is None or ms < 0:
        return "00:00:00.000"
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def data_table_construct_node(
    state: DataTableConstructInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DataTableConstructOutput:
    """
    title: 数据表格构造
    desc: 将ASR识别结果组装成标准的Excel表格数据格式,包含原材料片段、中文原文等字段
    integrations: 无
    """
    ctx = runtime.context
    
    logger.info(f"==========================================")
    logger.info(f"数据表格构造节点开始执行")
    logger.info(f"输入数据asr_result长度: {len(state.asr_result)}")
    logger.info(f"输入数据完整内容: {state.asr_result}")
    logger.info(f"==========================================")
    
    if len(state.asr_result) == 0:
        logger.error("❌ 【严重问题】asr_result为空列表!")
        logger.error("这意味着ASR识别节点没有返回任何数据")
        logger.error("数据传递链路诊断:")
        logger.error("  1. ASR识别节点可能识别失败")
        logger.error("  2. ASR识别节点返回的utterances列表为空")
        logger.error("  3. 音频文件可能没有可识别的语音内容")
        logger.error("当前状态: 数据构造节点将返回空table_data")
        logger.error("后续影响: Excel生成节点将只生成表头,无数据行")
        return DataTableConstructOutput(table_data=[])
    
    logger.info(f"开始构造表格数据,共{len(state.asr_result)}条ASR结果")
    
    if len(state.asr_result) == 0:
        logger.error("❌ 【严重问题】asr_result为空列表!")
        logger.error("这意味着ASR识别节点没有返回任何数据")
        logger.error("数据传递链路诊断:")
        logger.error("  1. ASR识别节点可能识别失败")
        logger.error("  2. ASR识别节点返回的utterances列表为空")
        logger.error("  3. 音频文件可能没有可识别的语音内容")
        logger.error("当前状态: 数据构造节点将返回空table_data")
        logger.error("后续影响: Excel生成节点将只生成表头,无数据行")
        # 返回空table_data
        empty_output = DataTableConstructOutput(table_data=[])
        logger.info(f"返回空DataTableConstructOutput: {empty_output}")
        return empty_output
    
    # 打印第一条ASR数据用于验证
    logger.info(f"第一条ASR数据: {state.asr_result[0]}")
    logger.info(f"第一条ASR数据的text字段: 【{state.asr_result[0].get('text', '')}】")
    logger.info(f"第一条ASR数据的text字段长度: {len(state.asr_result[0].get('text', ''))}")
    logger.info(f"第二条ASR数据: {state.asr_result[1] if len(state.asr_result) > 1 else '无'}")
    
    try:
        table_rows = []
        
        for asr_item in state.asr_result:
            # 构造原材料片段字段: "seg001 | 00:00:02 - 00:00:05"
            segment_id = asr_item.get("segment_id", "")
            start_time_str = asr_item.get("start_time_str", "")
            end_time_str = asr_item.get("end_time_str", "")
            material_segment = f"{segment_id} | {start_time_str} - {end_time_str}"
            
            # 构造完整时间轴参数JSON
            time_axis_params = {
                "segment_id": segment_id,
                "start_time_ms": asr_item.get("start_time_ms", 0),
                "end_time_ms": asr_item.get("end_time_ms", 0),
                "duration_ms": asr_item.get("duration_ms", 0)
            }
            
            # 按照文档要求的字段顺序构造行数据
            row_data = {
                "原材料片段": material_segment,
                "中文原文": asr_item.get("text", ""),
                "机器翻译(英译)": "",  # 空字段,等待后续填充
                "人工编辑列": "",
                "审校列": "",
                "质量控制列": "",
                "最终译文列": "",
                "素材基准帧率": "自动读取",  # 实际应从原视频获取
                "素材基准语速": "自动读取",  # 实际应从原音频获取
                "完整时间轴参数": time_axis_params,  # 兼容旧字段名
                "时间戳": {  # ⭐ 新增：与 batch_translation_node 字段名一致,解决"时间戳丢失"bug
                    "segment_id": time_axis_params["segment_id"],
                    "start_time_ms": time_axis_params["start_time_ms"],
                    "end_time_ms": time_axis_params["end_time_ms"],
                    "duration_ms": time_axis_params["duration_ms"],
                    "start_time_str": _ms_to_hms(time_axis_params["start_time_ms"]),
                    "end_time_str": _ms_to_hms(time_axis_params["end_time_ms"])
                }
            }
            
            table_rows.append(row_data)
        
        logger.info(f"表格数据构造完成,共{len(table_rows)}行")
        
        return DataTableConstructOutput(table_data=table_rows)
        
    except Exception as e:
        logger.error(f"表格数据构造失败: {str(e)}")
        raise Exception(f"表格数据构造失败: {str(e)}")