"""
模式1结束节点 - 输出待审校Excel提示
"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import EndMode1Input, EndMode1Output


logger = logging.getLogger(__name__)


def end_mode1_node(
    state: EndMode1Input,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EndMode1Output:
    """
    title: 输出待审校Excel
    desc: 生成提示消息,告知用户已完成预处理,需要线下审校Excel
    integrations: 无
    """
    ctx = runtime.context
    
    logger.info(f"模式1结束,Excel文件已生成: {state.excel_url}")
    
    # 构造提示消息
    message = f"已生成人工审核表格,请线下完成翻译审校,填写【最终译文列】后再使用回填模式。\n\nExcel文件下载链接: {state.excel_url}"
    
    logger.info(f"输出提示消息: {message}")
    
    return EndMode1Output(message=message)