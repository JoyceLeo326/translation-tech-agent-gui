"""
DOCX分层分句分批翻译+审核回填替换DOCX工具 - 主图编排
两条独立支路：
  支路1：DOCX上传→解析→分片→循环翻译→合并→生成Excel
  支路2：Excel上传→读取→生成英文DOCX
"""
from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    RouterInput,
    RouterOutput,
    DocxParseInput,
    DocxParseOutput,
    SplitInput,
    SplitOutput,
    TranslateBatchInput,
    TranslateBatchOutput,
    MergeInput,
    MergeOutput,
    GenerateExcelInput,
    GenerateExcelOutput,
    ReadExcelInput,
    ReadExcelOutput,
    GenerateDocxInput,
    GenerateDocxOutput,
)
from graphs.nodes.router_node import router_node
from graphs.nodes.docx_parse_node import docx_parse_node
from graphs.nodes.split_node import split_node
from graphs.nodes.translate_batch_node import translate_batch_node
from graphs.nodes.merge_node import merge_node
from graphs.nodes.generate_excel_node import generate_excel_node
from graphs.nodes.read_excel_node import read_excel_node
from graphs.nodes.generate_docx_node import generate_docx_node


# ============================================================
# 路由条件函数
# ============================================================
def route_branch(state: RouterOutput) -> str:
    """
    title: 路由分支
    desc: 根据路由节点输出判断走支路1（DOCX翻译）或支路2（回填生成DOCX）
    """
    if state.branch == "branch1":
        return "docx_parse"
    elif state.branch == "branch2":
        return "read_excel"
    else:
        return END


# ============================================================
# 构建主图
# ============================================================
builder = StateGraph(
    GlobalState,
    input_schema=GraphInput,
    output_schema=GraphOutput,
)

# 添加所有节点
builder.add_node("router", router_node)
builder.add_node("docx_parse", docx_parse_node)
builder.add_node("split", split_node)
builder.add_node("translate_batch", translate_batch_node, metadata={"type": "loopcond"})
builder.add_node("merge", merge_node)
builder.add_node("generate_excel", generate_excel_node)
builder.add_node("read_excel", read_excel_node)
builder.add_node("generate_docx", generate_docx_node)

# 设置入口点
builder.set_entry_point("router")

# 路由条件分支
builder.add_conditional_edges(
    source="router",
    path=route_branch,
    path_map={
        "docx_parse": "docx_parse",
        "read_excel": "read_excel",
        END: END,
    },
)

# ============================================================
# 支路1：DOCX → 分片 → 翻译 → 合并 → Excel
# ============================================================
builder.add_edge("docx_parse", "split")
builder.add_edge("split", "translate_batch")
builder.add_edge("translate_batch", "merge")
builder.add_edge("merge", "generate_excel")
builder.add_edge("generate_excel", END)

# ============================================================
# 支路2：Excel → 读取 → 生成DOCX
# ============================================================
builder.add_edge("read_excel", "generate_docx")
builder.add_edge("generate_docx", END)

# 编译主图
main_graph = builder.compile()