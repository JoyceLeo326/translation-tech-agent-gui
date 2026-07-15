"""
批量翻译节点 - 在主图中调用循环子图进行多分片翻译
"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import TranslateBatchInput, TranslateBatchOutput
from graphs.loop_graph import subgraph


def translate_batch_node(
    state: TranslateBatchInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TranslateBatchOutput:
    """
    title: 批量翻译
    desc: 调用循环子图，遍历所有分片调用大模型翻译，收集所有分片的中文和英文结果
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 设置递归限制，确保足够处理所有分片
    invoke_config = {"recursion_limit": 200, "configurable": config.get("configurable", {})}
    # 调用子图进行循环翻译
    result = subgraph.invoke(
        input={
            "text_batch_list": state.text_batch_list,
            "total_batches": state.batch_count,
        },
        config=invoke_config,
    )

    return TranslateBatchOutput(
        cn_text_parts=result.get("cn_text_parts", []),
        en_text_parts=result.get("en_text_parts", []),
    )