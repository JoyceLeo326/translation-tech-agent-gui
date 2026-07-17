"""
数据校验节点 - 校验并筛选人工审核列的有效英文内容
"""
import logging
import json
import re
import os
import subprocess
import tempfile
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import DataValidateInput, DataValidateOutput


logger = logging.getLogger(__name__)


def data_validate_node(
    state: DataValidateInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DataValidateOutput:
    """
    title: 数据校验过滤
    desc: 只读取人工审核列的英文内容,统计总条数,输出全部文本核对,确保不遗漏任何一条
    integrations: 无
    """
    ctx = runtime.context

    logger.info(f"开始数据校验,输入{len(state.table_data)}条数据")

    try:
        validated_data = []
        # 收集所有人工审核文本,用于最终核对
        all_manual_texts: list[str] = []

        for idx, row in enumerate(state.table_data):
            chinese_text = row.get("音频文字", "").strip()
            machine_translation = row.get("机器译文", "").strip()
            manual_review = row.get("人工审核", "").strip()
            row_index = row.get("_row_index", idx)

            # ⭐ 修复(本版本):优先人工审核,空则降级到机器翻译
            # 之前 bug:人工审核列空就直接跳过该行,导致用户必须填全所有人工审核列
            # 现在:用户可只修改部分句子,没修改的自动用机器翻译列生成音频
            if manual_review:
                final_translation_text = manual_review
                use_source = "人工审核"
            elif machine_translation:
                final_translation_text = machine_translation
                use_source = "机器翻译(人工审核为空,降级)"
                logger.info(f"第{row_index + 1}行人工审核列为空,降级使用机器翻译列: {final_translation_text[:50]}...")
            else:
                # 两列都空,跳过该行
                logger.warning(f"第{row_index + 1}行人工审核列和机器翻译列都为空,已跳过")
                continue

            # 统计一条有效数据
            all_manual_texts.append(final_translation_text)

            # 根据句子长度估算时间轴
            english_words = len(final_translation_text.split())
            # 英文每分钟150词
            english_duration = english_words / 150 * 60

            # 计算开始和结束时间(顺序排列)
            start_seconds = sum(
                len(t.split()) / 150 * 60 for t in all_manual_texts[:-1]
            )
            end_seconds = start_seconds + english_duration

            start_time_str = f"00:00:{int(start_seconds):02d}"
            end_time_str = f"00:00:{int(end_seconds):02d}"

            # 构造校验后的完整数据
            validated_item = {
                "segment_id": f"seg{(idx + 1):03d}",  # 顺序ID
                "row_index": row_index + 1,  # 原始行号
                "start_time": start_time_str,
                "end_time": end_time_str,
                "final_translation": final_translation_text,  # ⭐ 优先人工审核,空则降级到机器翻译
                "text_source": use_source,  # 记录用了哪一列(便于追踪)
                "chinese_text": chinese_text,  # 中文原文(辅助)
                "time_axis_params": {
                    "estimated_duration": english_duration,
                    "english_words": english_words
                }
            }

            validated_data.append(validated_item)

        # ⭐ 版本更新:不再做时间轴对齐
        # 用户需求:不需要让英文音频和原中文音频时长一致
        # TTS 合成将按统一语速 1.0 + 17 字/秒自然生成,不做 atempo 拉伸/压缩
        logger.info(
            f"[时长对齐] 已跳过时间轴对齐(按用户要求:不匹配原中文音频时长),"
            f"共 {len(validated_data)} 段将按统一语速 1.0 + 17 字/秒自然合成"
        )

        # 关键步骤:合成前输出全部审核列文本核对
        total_count = len(validated_data)
        logger.info(f"=" * 70)
        logger.info(f"【人工审核列文本核对】即将合成 {total_count} 段音频")
        logger.info(f"=" * 70)
        # 统计用了哪一列(便于用户追踪)
        manual_count = sum(1 for item in validated_data if item.get("text_source") == "人工审核")
        machine_count = sum(1 for item in validated_data if item.get("text_source", "").startswith("机器翻译"))

        for i, item in enumerate(validated_data, 1):
            text_preview = item["final_translation"]
            if len(text_preview) > 80:
                text_preview = text_preview[:80] + "..."
            source_tag = item.get("text_source", "人工审核")
            logger.info(f"  [{i:02d}/{total_count}] (seg{item['segment_id']}) [{source_tag}] {text_preview}")
        logger.info(f"=" * 70)
        logger.info(
            f"✅ 共核对 {total_count} 条文本(人工审核 {manual_count} 条 + 机器翻译降级 {machine_count} 条),"
            f"顺序与Excel完全一致,将进入TTS合成"
        )

        if total_count == 0:
            logger.error("❌ 没有有效的人工审核/机器翻译文本,无法继续")
            raise Exception("数据校验失败: 没有有效的人工审核或机器翻译文本,请检查Excel【人工审核】列和【机器译文】列是否填写")

        return DataValidateOutput(
            validated_data=validated_data,
            expected_audio_count=total_count
        )

    except Exception as e:
        logger.error(f"数据校验失败: {str(e)}")
        raise Exception(f"数据校验失败: {str(e)}")





def _measure_audio_duration_url(audio_url: str) -> float:
    """
    用 ffprobe 测远端音频 URL 的总时长(秒)
    ffprobe 支持 HTTP/HTTPS,无需先下载到本地

    返回: 总时长(秒),失败返回 0.0
    """
    if not audio_url or not audio_url.startswith(("http://", "https://")):
        return 0.0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             audio_url],
            capture_output=True, text=True, timeout=30
        )
        if probe.returncode != 0:
            logger.warning(f"[ffprobe] 测时长失败 rc={probe.returncode}: {probe.stderr[:200]}")
            return 0.0
        out = probe.stdout.strip()
        if not out:
            return 0.0
        return float(out)
    except Exception as e:
        logger.warning(f"[ffprobe] 测时长异常: {e}")
        return 0.0


def _allocate_durations_by_word_count(
    validated_data: list[dict],
    total_target_duration_sec: float
) -> int:
    """
    根据"英文词数"按比例分配 duration_ms 给 validated_data 中"时间戳缺失"的段。
    用于模式二(无 ASR 时间戳,但有 original_audio_url)的场景:
      - 让 TTS 总时长 ≈ original_audio_url 总时长
      - 每段时长 = 剩余时间 × (本段词数 / 剩余段总词数)

    逻辑:
      1. 先标记哪些段已有有效 duration_ms("已锚定"),哪些没有("未锚定")
      2. 累计"已锚定"总时长
      3. 剩余时间 = total_target_duration_sec - 已锚定总时长
      4. "未锚定"段按词数比例分配剩余时间
      5. 把分配的 duration_ms 写入 item["时间戳"]["duration_ms"] 字段

    返回: 实际写入时间戳的段数
    """
    if not validated_data or total_target_duration_sec <= 0:
        return 0

    # 1) 统计"未锚定"段的词数 + "已锚定"段的总时长
    anchored_total_ms: float = 0.0
    unanchored_indices: list[int] = []
    unanchored_word_counts: list[int] = []

    for idx, item in enumerate(validated_data):
        if not isinstance(item, dict):
            continue
        ts = item.get("时间戳") or item.get("完整时间轴参数") or {}
        if not isinstance(ts, dict):
            ts = {}
        cur_dur_ms = ts.get("duration_ms", 0) if isinstance(ts.get("duration_ms", 0), (int, float)) else 0
        if cur_dur_ms and 300 <= cur_dur_ms <= 30000:
            anchored_total_ms += float(cur_dur_ms)
        else:
            unanchored_indices.append(idx)
            text = item.get("final_translation") or item.get("人工审核") or item.get("机器译文") or ""
            unanchored_word_counts.append(len(str(text).split()) if text else 1)

    if not unanchored_indices:
        return 0

    # 2) 剩余时间 = 目标总时长 - 已锚定总时长
    total_target_ms = total_target_duration_sec * 1000.0
    remaining_ms = total_target_ms - anchored_total_ms

    if remaining_ms <= 0:
        logger.warning(
            f"[时长分配] 已锚定总时长({anchored_total_ms / 1000:.2f}s) "
            f"已超出目标总时长({total_target_duration_sec:.2f}s),"
            f"未锚定段({len(unanchored_indices)}段)无法再分配,将保留0"
        )
        return 0

    # 3) 词数权重分配
    total_unanchored_words = sum(unanchored_word_counts)
    if total_unanchored_words <= 0:
        # 兜底:等分
        per_segment_ms = remaining_ms / len(unanchored_indices)
        for i, idx in enumerate(unanchored_indices):
            if not isinstance(validated_data[idx], dict):
                continue
            ts = validated_data[idx].get("时间戳") or {}
            if not isinstance(ts, dict):
                ts = {}
            ts["duration_ms"] = int(per_segment_ms)
            validated_data[idx]["时间戳"] = ts
        return len(unanchored_indices)

    # 词数比例分配
    allocated = 0
    for i, idx in enumerate(unanchored_indices):
        if not isinstance(validated_data[idx], dict):
            continue
        share = (unanchored_word_counts[i] / total_unanchored_words) * remaining_ms
        # 合理性校验:每段至少 0.3s,最多 30s(防止词数极小/极大的极端情况)
        share = max(300, min(30000, int(share)))
        ts = validated_data[idx].get("时间戳") or {}
        if not isinstance(ts, dict):
            ts = {}
        ts["duration_ms"] = share
        validated_data[idx]["时间戳"] = ts
        allocated += 1

    return allocated


def parse_material_segment(material_segment: str) -> tuple:
    """
    解析原材料片段字符串,提取ID和时间戳
    格式: "seg001 | 00:00:02 - 00:00:05"
    """
    try:
        pattern = r'(seg\d+)\s*\|\s*(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})'
        match = re.match(pattern, material_segment)

        if match:
            segment_id = match.group(1)
            start_time = match.group(2)
            end_time = match.group(3)
            return segment_id, start_time, end_time
        else:
            return "unknown", "00:00:00", "00:00:00"

    except Exception as e:
        logger.error(f"解析原材料片段失败: {str(e)}")
        return "unknown", "00:00:00", "00:00:00"
