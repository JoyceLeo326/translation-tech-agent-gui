"""
翻译节点 - 将中文翻译为英文(Agent节点)
"""
import os
import json
import re
import logging
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import TranslationInput, TranslationOutput
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage


logger = logging.getLogger(__name__)


def _clean_translation_output(raw: str) -> str:
    """
    清理翻译输出中的"思考链污染"(LLM 推理过程混入译文)。

    检测特征:
      - 包含"不对"、"重新"、"数一下"、"我错了"、"哦"等自我对话标记
      - 包含数字编号的单词列表(如 "1.A 2.poetic 3.encyclopedia")
      - 多行输出中夹杂推理过程

    策略:
      1) 若只有 1 行:直接返回(纯译文)
      2) 若多行:取最后一行非空、非推理的行作为译文
      3) 若所有行都是推理:取第一行(兜底)
      4) 去除行首的数字编号(如 "1. "、"1.A ")
    """
    if not raw or not isinstance(raw, str):
        return ""

    # 推理标记词(中文自我对话)
    thinking_markers: list[str] = [
        "不对", "重新", "数一下", "数一数", "我错", "我笨",
        "哦", "等", "哦对了", "哦不对", "算了", "换一个",
        "重来", "再试", "再来", "试一下", "加个", "去掉",
    ]

    lines: list[str] = [ln.strip() for ln in raw.split("\n") if ln.strip()]

    if not lines:
        return raw

    if len(lines) == 1:
        # 单行:可能是纯译文,也可能是一行推理
        txt: str = lines[0]
        if any(m in txt for m in thinking_markers):
            # 一整行都是推理,尝试从最后提取英文
            logger.warning(f"[翻译输出清理] 单行推理污染,尝试提取英文: {txt[:60]}...")
            # 从末尾往前找第一个完整的英文句
            matches = re.findall(r"[A-Z][A-Za-z\s,;'\-]+\.", txt)
            if matches:
                return matches[-1].strip()
        return txt

    # 多行:逐行判断,取最后一行非推理行
    for i in range(len(lines) - 1, -1, -1):
        line: str = lines[i]
        is_thinking: bool = any(m in line for m in thinking_markers)
        # 也检测"数字编号列表"模式(如 "1.A 2.poetic 3.encyclopedia")
        if not is_thinking:
            # 检查是否是编号列表行
            numbered_list_pattern: bool = bool(re.match(r"^[\d]+[\.\)]\s*[A-Za-z]", line))
            if numbered_list_pattern and i > 0:
                # 上一行可能才是译文
                continue
            # 取这一行作为译文
            cleaned: str = _strip_number_prefix(line)
            logger.info(f"[翻译输出清理] 从第{i+1}/{len(lines)}行提取译文(跳过{len(lines)-i-1}行推理)")
            return cleaned

    # 所有行都是推理:取第一行(兜底,但 strip 掉编号)
    logger.warning(f"[翻译输出清理] 全部{len(lines)}行均为推理,取首行兜底: {lines[0][:60]}...")
    return _strip_number_prefix(lines[0])


def _strip_number_prefix(line: str) -> str:
    """去除行首的数字编号,如 '12. ' → '' 或 '1.A poetic...' → 'A poetic...'"""
    import re
    stripped = re.sub(r"^[\d]+[\.\)]\s*", "", line)
    return stripped.strip()


def translation_node(
    state: TranslationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TranslationOutput:
    """
    title: 中文翻译英文
    desc: 将中文文本翻译为标准英文,用于后续TTS语音合成
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    logger.info(f"开始翻译片段{state.segment_id}: {state.chinese_text[:50]}...")
    
    try:
        # 从config读取模型配置文件路径
        cfg_file = os.path.join(
            os.getenv("COZE_WORKSPACE_PATH", ""),
            config.get("metadata", {}).get("llm_cfg", "config/translation_llm_cfg.json")
        )
        
        # 加载配置文件
        with open(cfg_file, 'r', encoding='utf-8') as fd:
            _cfg = json.load(fd)
        
        llm_config = _cfg.get("config", {})
        sp = _cfg.get("sp", "")
        up = _cfg.get("up", "")
        
        logger.info(f"加载翻译配置文件: {cfg_file}")
        
        # 使用Jinja2模板渲染用户提示词
        # 修复:TPM03 V2 长度控制 - 计算目标英文单词数(中文 × 1.0-1.5,适配原句时长)
        chinese_char_count = len(state.chinese_text)
        target_word_count = max(1, int(chinese_char_count * 1.2))  # 中文字符数 × 1.2
        original_duration_ms = state.original_duration_ms if state.original_duration_ms and state.original_duration_ms > 0 else 0

        up_tpl = Template(up)
        user_prompt = up_tpl.render({
            "chinese_text": state.chinese_text,
            "segment_id": state.segment_id,
            "chinese_char_count": chinese_char_count,
            "target_word_count": target_word_count,
            "original_duration_ms": original_duration_ms
        })
        
        # 初始化LLM客户端
        llm_client = LLMClient(ctx=ctx)
        
        # 构造消息列表
        messages = [
            HumanMessage(content=user_prompt)
        ]
        
        # 调用LLM翻译
        response = llm_client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-2-0-lite-260215"),
            temperature=llm_config.get("temperature", 0.3),
            max_completion_tokens=llm_config.get("max_completion_tokens", 512)
        )
        
        # 提取翻译结果(防御性处理)
        raw_text: str = ""
        if isinstance(response.content, str):
            raw_text = response.content.strip()
        elif isinstance(response.content, list):
            # 如果是list,提取文本部分
            if response.content and isinstance(response.content[0], str):
                raw_text = " ".join(response.content).strip()
            else:
                # list[dict]格式
                text_parts = [
                    item.get("text", "") 
                    for item in response.content 
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                raw_text = " ".join(text_parts).strip()
        else:
            raw_text = str(response.content)

        # ⭐ 输出清理(本版本新增):
        # 豆包 seed 系列模型即使 thinking=disabled,偶发情况下仍会输出推理过程。
        # 此处用启发式规则检测并清洗"思考链污染",提取真正译文。
        english_text: str = _clean_translation_output(raw_text)

        logger.info(f"翻译完成: {english_text[:50]}...")
        
        return TranslationOutput(
            english_text=english_text,
            segment_id=state.segment_id
        )
        
    except Exception as e:
        logger.error(f"翻译失败: {str(e)}")
        raise Exception(f"翻译失败: {str(e)}")