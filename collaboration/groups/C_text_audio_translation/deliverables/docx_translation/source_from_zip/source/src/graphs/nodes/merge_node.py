"""
分批合并节点 - 按分片顺序拼接全部中文和英文内容
"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import MergeInput, MergeOutput


def merge_node(state: MergeInput, config: RunnableConfig, runtime: Runtime[Context]) -> MergeOutput:
    """
    title: 分批合并
    desc: 按分片原有顺序拼接全部中文和英文内容，恢复完整文档层级结构
    """
    ctx = runtime.context

    cn_parts = state.cn_text_parts
    en_parts = state.en_text_parts

    # 按顺序拼接
    cn_raw = "\n".join(cn_parts)
    en_raw = "\n".join(en_parts)

    return MergeOutput(
        cn_raw=cn_raw,
        en_raw=en_raw
    )