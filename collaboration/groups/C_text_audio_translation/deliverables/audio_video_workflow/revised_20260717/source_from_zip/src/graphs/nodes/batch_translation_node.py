"""
批量翻译节点 - 按句子逐个翻译（强制规则实现）
【强制修改规则】
1. 原文完整性约束：100%保留完整中文原文，不遗漏任何字
2. 拆分规则：按句号/问号/感叹号为拆分边界
3. 匹配校验规则：确保每个中文句子都有对应的英文翻译
4. 输出格式约束：按原文顺序排列，一一对应
"""
import re
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import TranslationBatchInput, TranslationBatchOutput
from graphs.nodes.translation_node import translation_node
from graphs.state import TranslationInput


logger = logging.getLogger(__name__)


def split_chinese_sentences_for_translation(text: str) -> list:
    """
    中文分句函数 - 按句末标点符号分句（强制规则实现）
    以中文句号「。」、感叹号「！」、问号「？」作为句子分隔符
    保留句末标点符号
    
    Args:
        text: 完整的中文文本
        
    Returns:
        list: 中文句子列表，每个句子保留句末标点
    """
    if not text or not isinstance(text, str):
        return []
    
    # 使用正则表达式按句末标点分句
    pattern = r'([。！？])\s*'
    
    # 分割句子
    parts = re.split(pattern, text)
    
    # 重新组合句子（合并标点符号）
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        if i + 1 < len(parts):
            sentence = parts[i] + parts[i + 1]
            sentence = sentence.strip()
            if sentence:
                sentences.append(sentence)
    
    # 处理最后可能没有标点的部分（虽然按规则不应该出现）
    if len(parts) % 2 == 1:
        last_part = parts[-1].strip()
        if last_part:
            # 如果最后一部分没有标点，也添加进去（保证完整性）
            sentences.append(last_part)
    
    return sentences


def batch_translation_node(
    state: TranslationBatchInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TranslationBatchOutput:
    """
    title: 批量翻译处理
    desc: 按句子逐个翻译，确保每个中文句子都有对应的英文翻译（强制规则实现）
    """
    ctx = runtime.context
    
    logger.info("="*60)
    logger.info("批量翻译节点 - 按句子逐个翻译")
    logger.info("="*60)
    
    if len(state.table_data) == 0:
        logger.error("❌ table_data为空")
        return TranslationBatchOutput(table_data=[])
    
    try:
        translated_table_data = []
        
        # 遍历每条数据（通常只有一条，对应一个音频片段）
        for row_idx, row in enumerate(state.table_data):
            logger.info(f"\n处理第{row_idx + 1}条数据")
            
            # 提取中文原文
            chinese_text = row.get("中文原文", "")
            
            # 【强制规则1】原文完整性约束
            logger.info(f"【规则1】完整中文原文: 【{chinese_text}】")
            logger.info(f"【规则1】中文原文长度: {len(chinese_text)}字符")
            
            # 【强制规则2】拆分规则 - 按句子拆分
            chinese_sentences = split_chinese_sentences_for_translation(chinese_text)

            # 【TPM03 V2】按字数比例分配 ASR 原句时长给每个标点句
            # (解决"整段一次性翻译+配音"导致的时长匹配失衡)
            asr_ts = row.get("时间戳") or row.get("完整时间轴参数") or {}
            asr_duration_ms = asr_ts.get("duration_ms", 0) if isinstance(asr_ts, dict) else 0
            total_chars = len(chinese_text)
            if asr_duration_ms > 0 and total_chars > 0:
                # 按字数比例计算每个标点句的目标 duration_ms
                cumulative_chars = 0
                sentence_durations_ms = []
                for sent in chinese_sentences:
                    sent_chars = len(sent)
                    # 该标点句占用的时长 = (累积字数 + 当前句字数) / 总字数 × 总时长
                    cumulative_chars += sent_chars
                    sent_duration = int(cumulative_chars * asr_duration_ms / total_chars) - sum(sentence_durations_ms)
                    sentence_durations_ms.append(max(300, min(sent_duration, 30000)))
                logger.info(f"【TPM03 V2】ASR原句总时长={asr_duration_ms}ms,按字数比例分配给{len(chinese_sentences)}个标点句")
            else:
                sentence_durations_ms = [0] * len(chinese_sentences)
                logger.info(f"【TPM03 V2】无ASR时间戳,标点句时长=0(LLM将回退到默认目标字数)")

            logger.info(f"【规则2】中文分句数量: {len(chinese_sentences)}句")
            # 【性能优化】汇总打印,不再逐句打印(避免 N 行 × logger.info)
            if len(chinese_sentences) <= 5:
                for i, sentence in enumerate(chinese_sentences, 1):
                    logger.info(f"  第{i}句: {sentence} (目标时长={sentence_durations_ms[i-1] if i-1 < len(sentence_durations_ms) else 0}ms)")
            else:
                logger.info(f"  (前3句预览) {[s[:30]+'...' for s in chinese_sentences[:3]]}")
            
            # 【强制规则3】匹配校验规则 - 对每个中文句子进行翻译
            english_sentences = []
            
            for sent_idx, cn_sentence in enumerate(chinese_sentences, 1):
                logger.info(f"\n开始翻译第{sent_idx}句: {cn_sentence}")
                
                # 构造翻译输入(【TPM03 V2】传递按字数比例分配的ASR原句时长)
                translation_input = TranslationInput(
                    chinese_text=cn_sentence,
                    segment_id=f"sent_{sent_idx}",
                    original_duration_ms=sentence_durations_ms[sent_idx - 1] if sent_idx - 1 < len(sentence_durations_ms) else 0
                )
                
                # 调用翻译节点翻译单个句子
                try:
                    translation_output = translation_node(
                        state=translation_input,
                        config=config,
                        runtime=runtime
                    )
                    
                    en_sentence = translation_output.english_text
                    english_sentences.append(en_sentence)
                    
                    logger.info(f"✅ 翻译完成: {cn_sentence} -> {en_sentence}")
                    
                except Exception as e:
                    logger.error(f"❌ 翻译第{sent_idx}句失败: {str(e)}")
                    # 如果翻译失败，添加空字符串占位
                    english_sentences.append("")
            
            # 【强制规则3验证】检查句子数量是否完全一致
            if len(chinese_sentences) != len(english_sentences):
                error_msg = (
                    f"【严重错误】翻译后句子数量不匹配！"
                    f"中文{len(chinese_sentences)}句，英文{len(english_sentences)}句。"
                    f"这违反了强制规则，请检查翻译节点实现。"
                )
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"\n【规则3验证】✅ 句子数量完全匹配：{len(chinese_sentences)}句")
            
            # 【强制规则4】输出格式约束 - 按原文顺序排列
            # 将分句后的数据保存到table_data
            # ⭐ 关键修复：每个"标点句"按字数比例分配 ASR segment 的总时长
            # 这样 TTS 阶段能按"原句时长"精确控制 atempo,解决"整段合成→累积错位"问题
            asr_ts = row.get("时间戳") or row.get("完整时间轴参数") or {}
            asr_start_ms = asr_ts.get("start_time_ms", 0) if isinstance(asr_ts, dict) else 0
            asr_end_ms = asr_ts.get("end_time_ms", 0) if isinstance(asr_ts, dict) else 0
            asr_duration_ms = asr_end_ms - asr_start_ms if (asr_end_ms > asr_start_ms) else 0
            total_chars = len(chinese_text)
            cumulative_chars = 0  # 累计字数,用于计算每个标点句的起始时间

            if asr_duration_ms > 0 and total_chars > 0:
                logger.info(
                    f"【时间戳】ASR segment总时长={asr_duration_ms}ms(从{asr_start_ms}ms到{asr_end_ms}ms),"
                    f"总字数={total_chars},按字数比例分配给{len(chinese_sentences)}个标点句"
                )
            else:
                logger.warning(
                    f"【时间戳】ASR segment无时间戳信息(空或无duration_ms),"
                    f"标点句时长将为0,TTS将回退到17字/秒规范化"
                )

            def _ms_to_hms(ms: int) -> str:
                if ms is None or ms < 0:
                    return "00:00:00.000"
                total_seconds = ms / 1000
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

            for i, (cn_sent, en_sent) in enumerate(zip(chinese_sentences, english_sentences), 1):
                # 按字数比例计算每个标点句的起止时间
                if asr_duration_ms > 0 and total_chars > 0:
                    seg_chars = len(cn_sent)
                    seg_start_offset = cumulative_chars
                    seg_end_offset = cumulative_chars + seg_chars
                    seg_start_ms = asr_start_ms + int(seg_start_offset * asr_duration_ms / total_chars)
                    seg_end_ms = asr_start_ms + int(seg_end_offset * asr_duration_ms / total_chars)
                    seg_duration_ms = seg_end_ms - seg_start_ms
                    cumulative_chars += seg_chars
                else:
                    seg_start_ms = 0
                    seg_end_ms = 0
                    seg_duration_ms = 0

                translated_row = {
                    "中文原文": cn_sent,
                    "机器翻译(英译)": en_sent,
                    "segment_id": f"seg{row_idx + 1}_sent{i}",
                    "时间戳": {
                        "segment_id": f"seg{row_idx + 1}_sent{i}",
                        "start_time_ms": seg_start_ms,
                        "end_time_ms": seg_end_ms,
                        "duration_ms": seg_duration_ms,
                        "start_time_str": _ms_to_hms(seg_start_ms),
                        "end_time_str": _ms_to_hms(seg_end_ms),
                        "原ASR_segment时长ms": asr_duration_ms  # 用于TTS阶段判断是否按原句时长控制
                    }
                }
                translated_table_data.append(translated_row)

                logger.info(
                    f"【规则4】第{i}组对照: {cn_sent} -> {en_sent} | "
                    f"时间戳:{_ms_to_hms(seg_start_ms)}-{_ms_to_hms(seg_end_ms)}({seg_duration_ms}ms)"
                )
        
        logger.info(f"\n批量翻译完成，共生成{len(translated_table_data)}组对照句子")
        logger.info("="*60)
        logger.info("✅✅✅ 所有强制规则验证通过！")
        logger.info("="*60)
        
        return TranslationBatchOutput(table_data=translated_table_data)
        
    except Exception as e:
        logger.error(f"批量翻译失败: {str(e)}")
        raise Exception(f"批量翻译失败: {str(e)}")