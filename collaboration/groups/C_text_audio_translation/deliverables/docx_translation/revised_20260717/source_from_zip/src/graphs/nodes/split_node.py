"""
文本分片节点 - 将长文本按行均等切分为多个分片，每行添加行号确保LLM输出可对齐
"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import SplitInput, SplitOutput


def split_node(state: SplitInput, config: RunnableConfig, runtime: Runtime[Context]) -> SplitOutput:
    """
    title: 超长文本分片
    desc: 自动将文本按行切分为单个小分片，每片1行，每行添加[行号]前缀确保LLM逐行翻译不偏移
    """
    ctx = runtime.context

    text = state.parsed_text
    # 每片目标行数 - 1行确保LLM绝不合并行，保证逐行完整翻译
    MAX_LINES_PER_BATCH = 1

    # 按行分割
    lines = text.split("\n")

    if len(lines) <= MAX_LINES_PER_BATCH:
        # 无需分片，但也要加行号
        numbered = "\n".join([f"[{i+1}] {line}" for i, line in enumerate(lines)])
        return SplitOutput(
            text_batch_list=[numbered],
            batch_count=1
        )

    batches = []
    current_batch = []
    global_idx = 0

    for line in lines:
        # 添加全局行号前缀
        numbered_line = f"[{global_idx + 1}] {line}"
        current_batch.append(numbered_line)
        global_idx += 1
        if len(current_batch) >= MAX_LINES_PER_BATCH:
            batches.append("\n".join(current_batch))
            current_batch = []

    # 处理最后一批
    if current_batch:
        batches.append("\n".join(current_batch))

    batch_count = len(batches)

    return SplitOutput(
        text_batch_list=batches,
        batch_count=batch_count
    )