"""
翻译循环子图 - 遍历text_batch_list内每一段分片文本，调用大模型翻译
条件循环：current_index < total_batches 时继续
"""
import os
import re
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage
from graphs.state import (
    TranslateLoopState,
    TranslateLoopInput,
    TranslateLoopOutput,
)


def _invoke_llm(client: LLMClient, messages, llm_config: dict):
    """按配置调用LLM；SDK不支持thinking参数时自动回退，避免运行时失败。"""
    kwargs = {
        "messages": messages,
        "model": llm_config.get("model", "doubao-seed-2-0-mini-260215"),
        "temperature": llm_config.get("temperature", 0.1),
        "top_p": llm_config.get("top_p", 0.1),
        "max_completion_tokens": llm_config.get("max_completion_tokens", 8192),
    }
    if "thinking" in llm_config:
        kwargs["thinking"] = llm_config["thinking"]

    try:
        return client.invoke(**kwargs)
    except TypeError as exc:
        if "thinking" in kwargs and "thinking" in str(exc):
            kwargs.pop("thinking", None)
            return client.invoke(**kwargs)
        raise


def translate_one_batch_node(
    state: TranslateLoopState,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TranslateLoopState:
    """
    title: 翻译单个分片
    desc: 对当前分片文本调用大模型进行中译英，输出分片对应的中文和英文内容
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 获取当前分片
    batch_text = state.text_batch_list[state.current_index]

    # 读取LLM配置
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"), "config/translate_llm_cfg.json")
    with open(cfg_file, "r") as fd:
        _cfg = json.load(fd)

    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    llm_config = _cfg.get("config", {})

    # 渲染用户提示词模板
    up_tpl = Template(up)
    user_prompt_content = up_tpl.render({"batch_text": batch_text})

    # 初始化LLM客户端
    client = LLMClient(ctx=ctx)

    # 组装消息
    messages = [
        SystemMessage(content=sp),
        HumanMessage(content=user_prompt_content),
    ]

    # 调用大模型
    response = _invoke_llm(client, messages, llm_config)

    # 解析LLM响应内容
    resp_content = response.content
    if isinstance(resp_content, str):
        raw_en = resp_content.strip()
    elif isinstance(resp_content, list):
        text_parts = []
        for item in resp_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        raw_en = " ".join(text_parts).strip()
    else:
        raw_en = str(resp_content).strip()

    # 解析输入行号: [1] content
    input_lines = batch_text.split("\n")
    line_mapping = {}  # line_num -> original_content
    for line in input_lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'\[(\d+)\]\s*(.*)', line)
        if m:
            line_num = int(m.group(1))
            content = m.group(2).strip()
            line_mapping[line_num] = content

    # 解析输出行号: [1] translation
    output_lines = raw_en.split("\n")
    en_lines_map = {}
    for line in output_lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r'\[(\d+)\]\s*(.*)', line)
        if m:
            line_num = int(m.group(1))
            translation = m.group(2).strip()
            en_lines_map[line_num] = translation

    # 按行号对齐：用输入行号重建中文文本和英文文本
    sorted_nums = sorted(line_mapping.keys())
    total_input_lines = len(sorted_nums)

    if en_lines_map:
        # LLM输出了带行号的内容
        cn_lines = []
        en_lines = []
        for num in sorted_nums:
            cn_lines.append(line_mapping.get(num, ""))
            en_lines.append(en_lines_map.get(num, ""))
        # 检查是否有缺失行
        missing_count = sum(1 for e in en_lines if not e)
        if missing_count > 0 and missing_count == total_input_lines:
            # 完全没有匹配的行号，按顺序对齐
            raw_lines = [l.strip() for l in raw_en.split("\n") if l.strip()]
            en_lines = []
            for i, num in enumerate(sorted_nums):
                if i < len(raw_lines):
                    m = re.match(r'\[(\d+)\]\s*(.*)', raw_lines[i])
                    if m:
                        en_lines.append(m.group(2).strip())
                    else:
                        en_lines.append(raw_lines[i])
                else:
                    # 行数不足时，用原文填充（避免空白或重复）
                    en_lines.append(line_mapping.get(num, ""))
            cn_lines = [line_mapping[num] for num in sorted_nums]
        elif missing_count > 0:
            # 部分行缺失，用原文填充缺失行
            for i, num in enumerate(sorted_nums):
                if not en_lines[i]:
                    en_lines[i] = cn_lines[i]  # 用原文作为占位
    else:
        # 回退：LLM未输出行号，按顺序对齐
        raw_lines = [l.strip() for l in raw_en.split("\n") if l.strip()]
        cn_lines = [line_mapping[num] for num in sorted_nums]
        en_lines = []
        for i, num in enumerate(sorted_nums):
            if i < len(raw_lines):
                en_lines.append(raw_lines[i])
            else:
                # 行数不足时，用原文填充（避免空白或重复）
                en_lines.append(cn_lines[i])

    # 转换为带行号的格式，确保merge时能正确对齐
    cn_text = "\n".join([f"[{num}] {content}" for num, content in zip(sorted_nums, cn_lines)])
    en_text = "\n".join([f"[{num}] {content}" for num, content in zip(sorted_nums, en_lines)])

    # 更新状态
    new_cn_parts = list(state.cn_text_parts) + [cn_text]
    new_en_parts = list(state.en_text_parts) + [en_text]
    new_index = state.current_index + 1

    return TranslateLoopState(
        text_batch_list=state.text_batch_list,
        current_index=new_index,
        cn_text_parts=new_cn_parts,
        en_text_parts=new_en_parts,
        total_batches=state.total_batches,
    )


def check_loop_condition(
    state: TranslateLoopState
) -> str:
    """
    title: 循环条件判断
    desc: 判断是否所有分片都已翻译完成，未完成则继续循环
    """
    if state.current_index < state.total_batches:
        return "continue"
    else:
        return "done"


# ============================================================
# 构建循环子图
# ============================================================
subgraph_builder = StateGraph(
    TranslateLoopState,
    input_schema=TranslateLoopInput,
    output_schema=TranslateLoopOutput,
)

# 添加节点
subgraph_builder.add_node(
    "translate_one_batch",
    translate_one_batch_node,
    metadata={"type": "agent", "llm_cfg": "config/translate_llm_cfg.json"},
)

# 设置入口点
subgraph_builder.set_entry_point("translate_one_batch")

# 添加条件边（循环核心 - 直接从translate_one_batch判断是否继续）
subgraph_builder.add_conditional_edges(
    source="translate_one_batch",
    path=check_loop_condition,
    path_map={
        "continue": "translate_one_batch",
        "done": END,
    },
)

# 编译子图
subgraph = subgraph_builder.compile()
