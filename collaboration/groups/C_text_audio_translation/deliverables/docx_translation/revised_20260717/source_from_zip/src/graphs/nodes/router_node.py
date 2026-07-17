"""
路由节点 - 根据输入判断走支路1还是支路2
"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import RouterInput, RouterOutput


def router_node(state: RouterInput, config: RunnableConfig, runtime: Runtime[Context]) -> RouterOutput:
    """
    title: 路由判断
    desc: 根据输入参数判断执行支路1（DOCX翻译）或支路2（回填生成DOCX）
    """
    ctx = runtime.context

    if state.review_excel is not None:
        return RouterOutput(branch="branch2")
    elif state.file_docx is not None:
        return RouterOutput(branch="branch1")
    else:
        return RouterOutput(branch="end")