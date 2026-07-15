"""
循环子图 - 批量处理翻译和TTS任务
"""
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field


# ==================== 子图状态定义 ====================
class TranslationLoopState(BaseModel):
    """批量翻译循环状态"""
    table_data: List[Dict[str, Any]] = Field(..., description="待翻译的表格数据")
    current_index: int = Field(default=0, description="当前处理索引")
    translated_data: List[Dict[str, Any]] = Field(default=[], description="已翻译的数据")


class TTSLoopState(BaseModel):
    """批量TTS循环状态"""
    validated_data: List[Dict[str, Any]] = Field(..., description="待处理的数据")
    current_index: int = Field(default=0, description="当前处理索引")
    tts_results: List[Dict[str, Any]] = Field(default=[], description="TTS结果列表")


# ==================== 翻译循环节点 ====================
def translation_loop_process(state: TranslationLoopState) -> TranslationLoopState:
    """处理单条翻译"""
    from graphs.nodes.translation_node import translation_node
    
    if state.current_index >= len(state.table_data):
        return state
    
    current_row = state.table_data[state.current_index]
    
    # 调用翻译节点
    from graphs.state import TranslationInput
    trans_input = TranslationInput(
        chinese_text=current_row.get("中文原文", ""),
        segment_id=current_row.get("原材料片段", "").split("|")[0].strip()
    )
    
    # 注意:实际调用需要传递config和runtime,这里简化处理
    # 实际实现中需要在主图中正确传递参数
    
    # 更新索引
    new_state = TranslationLoopState(
        table_data=state.table_data,
        current_index=state.current_index + 1,
        translated_data=state.translated_data
    )
    
    return new_state


def should_continue_translation(state: TranslationLoopState) -> str:
    """判断是否继续翻译"""
    if state.current_index >= len(state.table_data):
        return "结束"
    else:
        return "继续翻译"


# ==================== TTS循环节点 ====================
def tts_loop_process(state: TTSLoopState) -> TTSLoopState:
    """处理单条TTS"""
    from graphs.nodes.tts_synthesis_node import tts_synthesis_node
    
    if state.current_index >= len(state.validated_data):
        return state
    
    current_item = state.validated_data[state.current_index]
    
    # 调用TTS节点
    from graphs.state import TTSInput
    tts_input = TTSInput(
        english_text=current_item.get("final_translation", ""),
        segment_id=current_item.get("segment_id", "")
    )
    
    # 注意:实际调用需要传递config和runtime,这里简化处理
    
    # 更新索引
    new_state = TTSLoopState(
        validated_data=state.validated_data,
        current_index=state.current_index + 1,
        tts_results=state.tts_results
    )
    
    return new_state


def should_continue_tts(state: TTSLoopState) -> str:
    """判断是否继续TTS"""
    if state.current_index >= len(state.validated_data):
        return "结束"
    else:
        return "继续TTS"


# ==================== 构建子图 ====================
def build_translation_loop_graph():
    """构建翻译循环子图"""
    builder = StateGraph(
        TranslationLoopState,
        input_schema=TranslationLoopState,
        output_schema=TranslationLoopState
    )
    
    builder.add_node("translation_process", translation_loop_process)
    builder.set_entry_point("translation_process")
    
    builder.add_conditional_edges(
        source="translation_process",
        path=should_continue_translation,
        path_map={
            "继续翻译": "translation_process",
            "结束": END
        }
    )
    
    return builder.compile()


def build_tts_loop_graph():
    """构建TTS循环子图"""
    builder = StateGraph(
        TTSLoopState,
        input_schema=TTSLoopState,
        output_schema=TTSLoopState
    )
    
    builder.add_node("tts_process", tts_loop_process)
    builder.set_entry_point("tts_process")
    
    builder.add_conditional_edges(
        source="tts_process",
        path=should_continue_tts,
        path_map={
            "继续TTS": "tts_process",
            "结束": END
        }
    )
    
    return builder.compile()


# ==================== 导出子图 ====================
translation_loop_graph = build_translation_loop_graph()
tts_loop_graph = build_tts_loop_graph()