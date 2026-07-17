"""
主图编排 - 双模式自动分流工作流

工作流入口：auto_mode_judge_node (智能模式判断节点)
根据输入类型自动分流：
- 模式一：仅上传音频文件时，执行ASR识别、翻译、生成Excel
- 模式二：上传Excel文件时，复用原始音频，执行TTS、混音、生成成品
"""

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from utils.file.file import File

from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    AutoModeJudgeInput,
    ModeCheckInput
)

# 导入所有节点函数
from graphs.nodes.auto_mode_judge_node import auto_mode_judge_node
from graphs.nodes.asr_recognition_node import asr_recognition_node
from graphs.nodes.data_table_construct_node import data_table_construct_node
from graphs.nodes.batch_translation_node import batch_translation_node
from graphs.nodes.excel_generate_node import excel_generate_node
from graphs.nodes.excel_data_fill_node import excel_data_fill_node
from graphs.nodes.end_mode1_node import end_mode1_node
from graphs.nodes.excel_read_node import excel_read_node
from graphs.nodes.data_validate_node import data_validate_node
from graphs.nodes.batch_tts_node import batch_tts_node
from graphs.nodes.media_compile_node import media_compile_node
from graphs.nodes.end_mode2_node import end_mode2_node
from graphs.nodes.qr_code_generation_node import qr_code_generation_node
from graphs.nodes.excel_output_generate_node import excel_output_generate_node


def check_run_mode(state: ModeCheckInput) -> str:
    """
    title: 运行模式判断
    desc: 根据run_mode字段判断运行模式一还是模式二
    """
    run_mode = state.run_mode
    
    if "预处理" in run_mode or "模式一" in run_mode or "生成待审校Excel" in run_mode:
        return "模式一_预处理"
    elif "回填" in run_mode or "模式二" in run_mode or "生成成品音视频" in run_mode:
        return "模式二_回填"
    else:
        # 默认执行模式一
        return "模式一_预处理"


# 创建状态图
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("auto_mode_judge", auto_mode_judge_node)

# 模式一节点
builder.add_node("asr_recognition", asr_recognition_node)
builder.add_node("data_table_construct", data_table_construct_node)
builder.add_node("batch_translation", batch_translation_node)
builder.add_node("excel_generate", excel_generate_node)
builder.add_node("excel_data_fill", excel_data_fill_node)
builder.add_node("end_mode1", end_mode1_node)

# 模式二节点
builder.add_node("excel_read", excel_read_node)
builder.add_node("data_validate", data_validate_node)
builder.add_node("batch_tts", batch_tts_node)
builder.add_node("media_compile", media_compile_node)
builder.add_node("end_mode2", end_mode2_node)
builder.add_node("qr_code_generation", qr_code_generation_node)
builder.add_node("excel_output_generate", excel_output_generate_node)

# 设置入口点：智能模式判断节点
builder.set_entry_point("auto_mode_judge")

# 添加条件分支：根据智能判断结果分流
builder.add_conditional_edges(
    source="auto_mode_judge",
    path=check_run_mode,
    path_map={
        "模式一_预处理": "asr_recognition",
        "模式二_回填": "excel_read"
    }
)

# 模式一流程
builder.add_edge("asr_recognition", "data_table_construct")
builder.add_edge("data_table_construct", "batch_translation")
builder.add_edge("batch_translation", "excel_generate")
builder.add_edge("excel_generate", "excel_data_fill")
builder.add_edge("excel_data_fill", "end_mode1")
builder.add_edge("end_mode1", END)

# 模式二流程
builder.add_edge("excel_read", "data_validate")
builder.add_edge("data_validate", "batch_tts")
builder.add_edge("batch_tts", "media_compile")
builder.add_edge("media_compile", "end_mode2")
# end_mode2 后并行执行二维码生成和Excel输出生成
builder.add_edge("end_mode2", "qr_code_generation")
builder.add_edge("end_mode2", "excel_output_generate")
# 两个并行分支都完成后结束
builder.add_edge(["qr_code_generation", "excel_output_generate"], END)

# 编译图
main_graph = builder.compile()