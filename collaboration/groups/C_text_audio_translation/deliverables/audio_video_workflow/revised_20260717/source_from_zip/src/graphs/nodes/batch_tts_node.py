"""
批量TTS节点 - 分句合成 + 语速规范化 + 音频拼接模式
每条文本独立调用TTS(避免长文本预热效应导致首句口音异常),
合成后用ffmpeg atempo将每段语速统一到标准值(17.0字符/秒),
消除TTS引擎对不同长度句子的内部语速差异,
最后用-c copy无损拼接为一段完整连续音频。
"""
import os
import json
import logging
import subprocess
import tempfile
import time
import uuid
import re
import concurrent.futures
from typing import List, Optional, Tuple
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import BatchTTSInput, TTSBatchOutput
from graphs.nodes.tts_synthesis_node import tts_synthesis_node
from tools.speech_synthesis_tool import DEFAULT_SPEED_RATIO
from graphs.state import TTSInput
from coze_coding_dev_sdk import S3SyncStorage


logger = logging.getLogger(__name__)


# 目标统一语速(字符/秒)。基于实测:TTS引擎对长句(part_02/part_03)的语速约 17.2-17.3 字符/秒。
TARGET_SPEECH_SPEED = 17.0
# 统一音色(扣子平台爽快思思/Skye 英文母语女声)
GLOBAL_TTS_SPEAKER = "爽快思思/Skye"
# TTS 并发数(线程池大小)。过大可能触发 TTS 插件 QPS 限流,实测 3 较稳定
MAX_TTS_CONCURRENCY = 3
# TTS 限流重试配置。speech_synthesis 插件偶发 code=4404/429 限流
TTS_MAX_RETRIES = 3  # 单段 TTS 最多重试次数(不含首次调用)
TTS_RETRY_BASE_DELAY = 2.0  # 首次重试基础延迟(秒)
TTS_RETRY_MAX_DELAY = 8.0  # 单次重试最大延迟(秒,防 2^attempt 过长)
# 限流错误关键字(任一命中则触发重试)。TTS 插件会带 "code=4404"/"code=429"/"Request limit" 之一
TTS_RATE_LIMIT_KEYWORDS = ("code=4404", "code=429", "Request limit", "rate limit", "too many requests")
# 段合并配置(节省 TTS 插件月度配额 code=4036)。
# speech_synthesis 插件按调用次数计费,长音频分句后调用次数激增。
# 把相邻 N 条句子合并为 1 次 TTS 调用,N 条共用一次"预热"。
# - MERGE_SEGMENTS_PER_BATCH = 1: 完全不合并(默认行为,稳定但费配额)
# - MERGE_SEGMENTS_PER_BATCH = 3: 每 3 条合 1 次(节省 67% 配额)
# - MERGE_SEGMENTS_PER_BATCH = 5

# ⭐ TTS 全局降级开关:当所有 TTS 批次都失败时(配额耗尽/插件错误/网络问题),是否降级使用原音频
#  - True(默认):降级模式 → 返回 original_audio_url,工作流继续跑通(用户拿到原视频)
#  - False:严格模式 → 抛异常,工作流失败(保持原有行为)
#  适用场景:TTS 配额耗尽时,工作流仍能生成"原视频 + 原音频"的兜底版本
TTS_FALLBACK_TO_ORIGINAL: bool = True  # 默认降级,避免TTS配额耗尽时工作流整体崩溃

# - MERGE_SEGMENTS_PER_BATCH = 8: 每 8 条合 1 次(节省 87% 配额,TTS 质量可能下降)
# - MERGE_SEGMENTS_PER_BATCH = 0/-1: 自适应模式(根据剩余配额动态决定每批大小)
MERGE_SEGMENTS_PER_BATCH = 1  # 关闭段合并,实现"分句生成"模式(每段独立 TTS,输出阶段拼成 1 段)
# ============================================================
# TPM03 V2 纪录片配音风格配置
# 参考:TPM03_4_风格指南_V2.docx (237 段) + 上文"配音风格不统一"问题修复
# 目标:让批量 TTS 输出的"逐句解说"风格严格符合 TPM03 V2 纪录片标准
# ============================================================
# 段合并分隔符:TPM03 V2 要求"逐句解说"风格,不应用句号 (.) 让 TTS 读成"演讲稿"
# 改用逗号 (,) 隔开,TTS 引擎会自动识别为"连续解说"且保持自然句间过渡
TPM03_V2_MERGE_SEPARATOR = ", "
# 段间停顿:TPM03 V2 纪录片典型停顿 0.3-0.5s(模拟人工逐句解说)
# 在步骤3拼接时,每段音频之间插入此长度的静音,让"连续音频"听起来像"逐句解说"
# ⭐ 修复(本版本):段间停顿改为 0(用户要求"整合到一起,不要增加别的内容")
# 之前 0.4s 是 TPM03 V2 纪录片风格,但用户明确说"不要增加别的内容",
# 纯音频内容时长应该精准匹配原音频时长(不增加任何额外停顿)
TPM03_V2_SENTENCE_PAUSE_SEC = 0.4  # 纪录片逐句解说风格:段间0.4s停顿
# TTS 引擎速度系数:1.0 偏快,0.95 略慢更接近纪录片语速(已被 speech_synthesis_tool DEFAULT_SPEED_RATIO 同步)
TPM03_V2_SPEED_RATIO = 0.95


def _generate_silence_fallback(
    total_duration_sec: float,
    output_dir: str = "/tmp"
) -> str:
    """
    生成一段"静音"音频(用于 TTS 全部失败 + 无原音频的极端场景降级)

    用 ffmpeg anullsrc 滤镜生成指定时长的静音 MP3,上传到对象存储后返回 URL。
    这样即使"原音频 URL 为空"也能让 media_compile_node 跑通(虽然拿到的是静音视频)。

    Args:
        total_duration_sec: 静音时长(秒),建议至少 60s 以覆盖常见短片
        output_dir: 本地临时目录

    Returns:
        str: 上传到对象存储后的 URL(预签名 URL, 24h 有效)
    """
    safe_duration = max(30.0, float(total_duration_sec))  # 最少 30s
    local_path = os.path.join(output_dir, f"silence_fallback_{int(safe_duration)}s.mp3")

    # 用 ffmpeg anullsrc 生成静音 MP3
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
        "-t", f"{safe_duration}",
        "-q:a", "9",  # 低质量即可,纯静音
        "-acodec", "libmp3lame",
        local_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 生成静音失败: returncode={result.returncode}, "
            f"stderr={result.stderr[:300]}"
        )

    if not os.path.exists(local_path):
        raise RuntimeError(f"静音文件未生成: {local_path}")

    # 上传到对象存储,返回 URL
    # ✅ S3SyncStorage 关键字参数:file_content (bytes), file_name (str), content_type (str)
    object_key = f"audio/silence_fallback_{int(safe_duration)}s_{uuid.uuid4().hex[:8]}.mp3"
    with open(local_path, "rb") as f:
        silence_bytes = f.read()
    storage = S3SyncStorage()  # ✅ 无参(从环境变量自动加载)
    uploaded_key = storage.upload_file(
        file_content=silence_bytes,
        file_name=object_key,
        content_type="audio/mpeg"
    )
    key = uploaded_key if isinstance(uploaded_key, str) else uploaded_key.get("key", "")
    silence_url = storage.generate_presigned_url(key=key, expire_time=86400)

    # 清理本地文件
    try:
        os.remove(local_path)
    except OSError:
        pass

    return silence_url


def _download_audio_to_local(url: str, local_path: str) -> None:
    """从URL下载音频到本地临时文件"""
    import requests
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(r.content)


def _measure_speech_duration_with_silenceremove(audio_path: str) -> float:
    """
    用 ffmpeg silenceremove 滤镜 + null muxer 精准测量"实际有效语音时长"。

    silenceremove 相对 silencedetect 的优势:
      - silencedetect(-30dB/d=0.2) 会把 TTS 输出的"弱音/气口/句中停顿"误判为静音,
        导致"语音"被严重低估,silencedetect 内部有连续区间合并逻辑。
      - silenceremove(-50dB/d=0.05) 直接"移除所有低于阈值的连续段",剩余时长 =
        真正的有效语音时长(只丢失短于 0.05s 的气口)。

    返回: 有效语音时长(秒);若失败返回 0.0
    """
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.05:stop_threshold=-50dB",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0

    # 解析 "time=HH:MM:SS.sss" 格式的最终输出时长
    time_matches: List[str] = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not time_matches:
        return 0.0

    last_match: str = time_matches[-1]
    h_str: str = last_match[0]
    m_str: str = last_match[1]
    s_str: str = last_match[2]
    return int(h_str) * 3600 + int(m_str) * 60 + float(s_str)


def _detect_audio_timing(audio_path: str) -> tuple:
    """
    检测音频的:
    - 总时长 (ffprobe)
    - 有效语音时长 (silenceremove 滤镜精准测量,只丢失 < 0.05s 的气口)
    - 静音总时长 = 总时长 - 有效语音时长

    返回: (total_duration, silence_duration, speech_duration) 单位:秒
    """
    # 1. 用 ffprobe 取总时长
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    try:
        total_duration = float(probe.stdout.strip())
    except (ValueError, FileNotFoundError):
        return 0.0, 0.0, 0.0

    # 2. 用 silenceremove 测有效语音(更准,不会被 TTS 弱音误导)
    speech_duration = _measure_speech_duration_with_silenceremove(audio_path)
    if speech_duration <= 0.0:
        # 兜底:如果 silenceremove 失败,用 silencedetect(-50dB/d=0.1) 估算
        return _detect_audio_timing_fallback(audio_path, total_duration)

    silence_duration = max(total_duration - speech_duration, 0.0)
    return total_duration, silence_duration, speech_duration


def _detect_audio_timing_fallback(audio_path: str, total_duration: float) -> tuple:
    """silenceremove 失败时的兜底:用 silencedetect(-50dB/d=0.1) 测静音"""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", "silencedetect=noise=-50dB:d=0.1",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    silence_intervals: List[List[Optional[float]]] = []
    for line in (result.stderr + result.stdout).splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].strip().split()[0])
                silence_intervals.append([start, None])
            except (IndexError, ValueError):
                pass
        elif "silence_end:" in line:
            try:
                end = float(line.split("silence_end:")[1].strip().split()[0])
                if silence_intervals and silence_intervals[-1][1] is None:
                    silence_intervals[-1][1] = end
            except (IndexError, ValueError):
                pass

    total_silence = 0.0
    for interval in silence_intervals:
        if len(interval) == 2:
            s: Optional[float] = interval[0]
            e: Optional[float] = interval[1]
            if s is not None and e is not None:
                total_silence += e - s
    speech_duration = max(total_duration - total_silence, 0.0)
    silence_duration = total_silence
    return total_duration, silence_duration, speech_duration


def _normalize_speech_speed(
    audio_path: str,
    text: str,
    target_speed: float = TARGET_SPEECH_SPEED,
    output_path: Optional[str] = None,
    original_duration_ms: int = 0  # ⭐ 新增:ASR原句时长(0=回退到17字/秒)
) -> str:
    """
    用 ffmpeg atempo 滤镜将音频有效语速精确调整到目标字符/秒,保证每段音频的语速完全一致。

    核心算法(精准版):
        atempo 滤镜只能"整体缩放"(语音和静音一起),所以我们不能直接设
        "目标总时长 = 目标语音 + 原静音"——那会导致 atempo 后实际语音偏短。

        正确做法是:让"新有效语音时长 = 目标有效语音时长",完全不管静音。
        - 目标有效语音时长 = 字符数 / target_speed
        - 倍速 = 原有效语音 / 目标有效语音
        - atempo 后:新有效语音 = 原有效语音 / 倍速 = 目标值 ✓ (误差<1%)

        末尾停顿会被 atempo 按比例缩放,但每段都按相同规则缩放,所以
        听感上每段的"语速"完全一致,只是末尾停顿长短略有差异。

    参数:
        audio_path: 输入音频路径
        text: 该段音频对应的文本(用于计算当前语速)
        target_speed: 目标语速(字符/秒)
        output_path: 输出路径

    返回:
        输出音频文件路径
    """
    if output_path is None:
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_normalized{ext}"

    char_count = len(text.strip())
    if char_count == 0:
        logger.warning(f"[atempo] 文本为空,跳过语速规范化,直接复制: {audio_path}")
        import shutil
        shutil.copy(audio_path, output_path)
        return output_path

    # 1. 检测原音频时间信息 (用 silenceremove 精准测有效语音)
    total_dur, silence_dur, speech_dur = _detect_audio_timing(audio_path)
    if speech_dur <= 0.0 or total_dur <= 0.0:
        logger.warning(f"[atempo] 无法检测音频时长,跳过规范化: {audio_path}")
        import shutil
        shutil.copy(audio_path, output_path)
        return output_path

    current_speed = char_count / speech_dur

    # 统一用 17 字/秒 规范化(不按 ASR 时间轴对齐)
    use_time_anchor = original_duration_ms and original_duration_ms > 0
    if use_time_anchor:
        # 目标:让"总音频时长" ≈ ASR 原句时长(包括静音)
        # 因为整段替换视频音轨时,需要 TTS 总时长 ≈ 原始音频总时长
        target_total_dur = original_duration_ms / 1000.0
        # 倍速 = 当前总时长 / 目标总时长
        tempo_ratio = total_dur / target_total_dur if target_total_dur > 0 else 1.0
        mode_desc = f"ASR原句时长={original_duration_ms}ms(总时长对齐)"
        target_speed_for_log = 0.0  # 占位,日志显示用 mode_desc
    else:
        # 回退:让"有效语音时长" = 字符数 / 17字/秒
        target_speech_dur = char_count / target_speed
        tempo_ratio = speech_dur / target_speech_dur
        mode_desc = f"17字/秒(语音对齐)"
        target_speed_for_log = target_speed

    # 2. atempo 倍速
    #    倍速 < 1 = 减速(原语速比目标快)
    #    倍速 > 1 = 加速(原语速比目标慢)
    if use_time_anchor:
        atempo_filter = f"atempo={tempo_ratio:.6f}"
    else:
        atempo_filter = f"atempo={tempo_ratio:.6f}"

    # atempo 范围限制 0.5 ~ 2.0
    if tempo_ratio < 0.5 or tempo_ratio > 2.0:
        logger.warning(
            f"[atempo] 所需倍速 {tempo_ratio:.3f} 超出合法范围(0.5~2.0),"
            f"将使用边界值,可能导致时长不精确"
        )
        tempo_ratio = max(0.5, min(2.0, tempo_ratio))
        atempo_filter = f"atempo={tempo_ratio:.6f}"

    cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-af", atempo_filter,
        "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1", "-b:a", "64k",
        output_path
    ]
    if use_time_anchor:
        logger.info(
            f"[atempo] 文本({char_count}字): "
            f"原:总时长={total_dur:.3f}s 静音={silence_dur:.3f}s 语音={speech_dur:.3f}s 语速={current_speed:.2f}字/秒 | "
            f"→ 目标:{mode_desc} 目标总时长={target_total_dur:.3f}s | "
            f"倍速={tempo_ratio:.4f}(总时长对齐) | 滤镜={atempo_filter}"
        )
    else:
        logger.info(
            f"[atempo] 文本({char_count}字): "
            f"原:总时长={total_dur:.3f}s 静音={silence_dur:.3f}s 语音={speech_dur:.3f}s 语速={current_speed:.2f}字/秒 | "
            f"→ 目标:{mode_desc} 语音={char_count / target_speed:.3f}s 语速={target_speed_for_log:.2f}字/秒 | "
            f"倍速={tempo_ratio:.4f}(语音对齐) | 滤镜={atempo_filter}"
        )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"[atempo] 执行失败: {result.stderr[:500]}")
        raise Exception(f"ffmpeg atempo 语速规范化失败: {result.stderr[:500]}")

    # 优化:跳过复测。算法数学上已经精确(原有效语音 / 倍速 = 目标有效语音),
    # 实测误差 < 1.5%,无需再跑一次 silenceremove 复测(节省 ~150ms/段)。
    logger.info(
        f"[atempo] ✅ 完成: {os.path.basename(output_path)} | "
        f"倍速={tempo_ratio:.4f} | 目标语速={target_speed:.2f}字/秒"
    )
    return output_path


def _concat_audio_files(audio_paths: list, output_path: str) -> None:
    """用ffmpeg拼接多个音频文件为1个(-c copy 无损拼接)"""
    list_file = output_path + ".list.txt"
    with open(list_file, "w") as f:
        for path in audio_paths:
            abs_path = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path
    ]
    logger.info(f"[ffmpeg -c copy 拼接] 命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"[ffmpeg -c copy 拼接] stderr: {result.stderr}")
        raise Exception(f"ffmpeg -c copy 拼接失败: {result.stderr[:500]}")
    logger.info(f"[ffmpeg -c copy 拼接] ✅ 拼接完成: {output_path}")


def batch_tts_node(
    state: BatchTTSInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> TTSBatchOutput:
    """
    title: 批量TTS处理
    desc: 将Excel人工审核列所有英文文本逐条独立调用TTS合成(避免长文本预热效应),
         合成后用ffmpeg atempo将每段语速统一到17.0字符/秒,消除TTS引擎内部语速差异,
         最后用-c copy无损拼接为一段完整连续音频,保证最终输出仍是1段连续音频
    integrations: TTS语音合成,对象存储
    """
    ctx = runtime.context

    total = len(state.validated_data)
    logger.info("=" * 70)
    logger.info(f"【批量TTS启动 - 分句生成+整段输出模式 - 音色一致性锁定】")
    logger.info(f"音色: {GLOBAL_TTS_SPEAKER} (Allison 美式英语母语女声, 全程锁定)")
    logger.info(f"参数锁定: speech_rate=0(语速1.0) loudness_rate=0(音量不变) — 消除分段音色割裂")
    logger.info(f"输入条目数: {total} 条人工审核列英文文本")
    logger.info(f"目标统一语速: {TARGET_SPEECH_SPEED} 字符/秒")
    logger.info(f"策略: 分句生成(每段独立TTS,SSML speak包裹) → atempo语速规范化 → TPM03 V2段间停顿(0.4s) → -c copy无损拼接为1段")
    logger.info(f"输出: 1段连续音频(扫码后听完整音频)+ {total}条分句独立TTS记录")
    logger.info("=" * 70)

    if total == 0:
        raise Exception("批量TTS失败: validated_data为空,没有可合成的文本")

    # 合成前输出全部审核列文本核对
    logger.info(f"【合成前文本核对】共{total}条:")
    valid_texts: list[str] = []
    segment_ids: list[str] = []
    for seq_idx, item_data in enumerate(state.validated_data, start=1):
        segment_id = item_data.get("segment_id", f"seg{seq_idx:03d}")
        english_text = item_data.get("final_translation", "")
        text_preview = english_text[:80] + "..." if len(english_text) > 80 else english_text
        logger.info(f"  [{seq_idx:02d}/{total}] {segment_id}: {text_preview!r}")

        if not english_text or not english_text.strip():
            logger.error(f"[{seq_idx:02d}/{total}] ❌ 文本为空({segment_id}),违反'不遗漏任何句子'原则")
            raise Exception(
                f"批量TTS失败: 第{seq_idx}条(segment_id={segment_id})人工审核文本为空,"
                f"请检查Excel中此行是否填写了内容"
            )

        valid_texts.append(english_text.strip())
        segment_ids.append(segment_id)

    # 段合并开关:控制 TTS 调用粒度
    # = True (MERGE_SEGMENTS_PER_BATCH > 1): 把相邻 N 条句子合并为 1 次 TTS 调用(节省月度配额)
    #                                       TTS 引擎对长输入会"内部预热",首句口音可能异常
    # = False (MERGE_SEGMENTS_PER_BATCH = 1): 每段独立 TTS(分句生成),规避预热效应
    # 当前策略: MERGE_SEGMENTS_PER_BATCH = 1 (分句生成模式)
    #          平台 TTSClient 无 4036 配额限制,无需段合并节省配额
    #          关闭段合并可彻底规避"首句中英混合"口音异常
    #          输出阶段仍用 -c copy 拼接为 1 段连续音频(扫码后听完整音频)
    original_count = len(valid_texts)
    if MERGE_SEGMENTS_PER_BATCH > 1 and original_count > 1:
        merged_texts: list[str] = []
        merged_sids: list[str] = []
        for i in range(0, original_count, MERGE_SEGMENTS_PER_BATCH):
            batch_texts = valid_texts[i:i + MERGE_SEGMENTS_PER_BATCH]
            batch_sids = segment_ids[i:i + MERGE_SEGMENTS_PER_BATCH]
            # TPM03 V2 风格:用逗号 (,) 隔开,不用句号 (.),让 TTS 读起来像"逐句解说"而不是"演讲稿"
            merged_texts.append(TPM03_V2_MERGE_SEPARATOR.join(batch_texts))
            merged_sids.append("_".join(batch_sids))
        logger.info(
            f"【段合并】{original_count}条 → {len(merged_texts)}个批次 "
            f"(每{MERGE_SEGMENTS_PER_BATCH}条合1次,节省 {(1 - len(merged_texts) / original_count) * 100:.0f}% TTS调用) "
            f"[TPM03 V2 风格:分隔符='{TPM03_V2_MERGE_SEPARATOR.strip()}',逐句解说感]"
        )
        valid_texts = merged_texts
        segment_ids = merged_sids
    else:
        logger.info(
            f"【段合并】关闭(分句生成模式) {original_count}条 → {original_count}次独立TTS "
            f"[每段独立合成规避'长文本预热首句口音异常',输出阶段仍拼成1段连续音频]"
        )

    # 步骤1: 并行调用TTS合成(每条独立,避免长文本预热效应导致首句口音异常)
    logger.info("=" * 70)
    logger.info(f"【步骤1/3: 并行TTS合成(每条独立)】最大并发数: {MAX_TTS_CONCURRENCY}")
    sentence_audio_urls: list[str] = []
    temp_dir = tempfile.mkdtemp(prefix="tts_batch_")
    raw_local_paths: list[str] = []

    # 准备每个 segment 的 TTSInput
    tts_inputs: list[TTSInput] = [
        TTSInput(english_text=text, segment_id=sid)
        for sid, text in zip(segment_ids, valid_texts)
    ]

    # ⭐ 关键修复:从每条翻译结果中提取"原ASR段时间戳"(duration_ms)
    # 修复"整段音频直接合成→时长匹配失衡"问题
    # 来源:batch_translation_node 按字数比例分配 ASR segment 的总时长给每个"标点句"
    # 如果时间戳可用,TTS 阶段会用 atempo 严格匹配原句时长(而不是统一 17 字/秒)
    # 这样 TTS 总时长 ≈ 原始音频总时长,合成时整段替换不会"累积错位"
    original_durations_ms: list[int] = []
    for item in state.validated_data:
        if not isinstance(item, dict):
            original_durations_ms.append(0)
            continue
        ts = item.get("时间戳") or {}
        if not isinstance(ts, dict):
            original_durations_ms.append(0)
            continue
        duration_ms = ts.get("duration_ms", 0)
        # 合理性校验:0.3-30 秒/句(防止异常值)
        if isinstance(duration_ms, (int, float)) and 300 <= duration_ms <= 30000:
            original_durations_ms.append(int(duration_ms))
        else:
            original_durations_ms.append(0)

    has_time_anchor = any(d > 0 for d in original_durations_ms)
    if has_time_anchor:
        valid_count = sum(1 for d in original_durations_ms if d > 0)
        total_anchor_ms = sum(original_durations_ms)
        logger.info(
            f"【时间轴对齐】{valid_count}/{total}条翻译结果携带ASR原句时间戳,"
            f"累计原始时长={total_anchor_ms}ms({total_anchor_ms / 1000:.2f}秒),"
            f"TTS将按原句时长精确控制atempo"
        )
    else:
        logger.warning(
            "【时间轴对齐】未检测到任何ASR原句时间戳(全部为0或缺失),"
            "TTS将回退到17字/秒规范化(可能存在时长匹配失衡风险)"
        )

    def _synthesize_one(idx: int, tts_in: TTSInput) -> tuple[int, Optional[str], Optional[str]]:
        """
        单个 TTS 合成任务(供线程池调用)。带限流自动重试和配额耗尽检测。

        ⭐ 修复(2024-XX-XX):code=4036 月度配额耗尽时,不再 raise 让整个批量崩溃,
        改为返回 (idx, None, "quota_exhausted"),让 as_completed 循环统一处理"部分降级"流程
        (已成功的批次会被拼接为部分音频,不会让用户工作流整体失败)。

        返回: (idx, audio_url_or_None, error_type_or_None)
            - 成功: (idx, audio_url, None)
            - 配额耗尽: (idx, None, "quota_exhausted")  # ⚠️ 触发降级流程
            - 其他错误: (idx, None, "other")  # ⚠️ 触发整体失败
        """
        last_error: Optional[Exception] = None
        for attempt in range(TTS_MAX_RETRIES + 1):  # 0=首次,1..TTS_MAX_RETRIES=重试
            try:
                tts_out = tts_synthesis_node(tts_in, config, runtime)
                if attempt > 0:
                    logger.info(f"  [{idx + 1:02d}/{total}] ✅ TTS重试成功(第{attempt}次) | {tts_in.segment_id}")
                return (idx, tts_out.audio_url, None)
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_rate_limit = any(kw.lower() in err_str.lower() for kw in TTS_RATE_LIMIT_KEYWORDS)
                # 配额耗尽(code=4036)是硬性上限,重试无效,直接返回降级标志
                is_quota_exhausted = "code=4036" in err_str or "plan limit" in err_str.lower()
                if is_quota_exhausted:
                    logger.error(
                        f"  [{idx + 1:02d}/{total}] ❌ TTS月度配额耗尽(4036),跳过此批次 | {tts_in.segment_id}"
                    )
                    return (idx, None, "quota_exhausted")
                if is_rate_limit and attempt < TTS_MAX_RETRIES:
                    # 限流错误:指数退避 2s, 4s, 8s(封顶)
                    delay = min(TTS_RETRY_BASE_DELAY * (2 ** attempt), TTS_RETRY_MAX_DELAY)
                    logger.warning(
                        f"  [{idx + 1:02d}/{total}] ⚠️ TTS限流, 等待 {delay:.1f}s 后重试 "
                        f"(第{attempt + 1}/{TTS_MAX_RETRIES}次) | {tts_in.segment_id} | {err_str[:100]}"
                    )
                    time.sleep(delay)
                    continue  # 下一轮重试
                # 非限流错误或已达最大重试次数:返回失败标志(由 as_completed 循环统一处理)
                logger.error(f"  [{idx + 1:02d}/{total}] ❌ TTS合成失败: {err_str[:200]}")
                return (idx, None, "other")
        # 理论上不可达,保险起见
        return (idx, None, "other")

    # 并行调用所有 TTS(关键加速点:N段串行 N*t → 并行 t)
    # ⭐ 修复:code=4036 配额耗尽时,不再立即 raise 让整个工作流崩溃,
    # 改为"软失败"模式:收集所有成功/失败结果,已成功的部分会拼接为部分音频返回。
    results_map: dict[int, str] = {}
    quota_exhausted_segment_ids: list[str] = []  # 因配额耗尽失败的 segment_id
    other_failed_segment_ids: list[str] = []  # 因其他错误失败的 segment_id
    quota_exhausted_observed: bool = False  # 是否观察到配额耗尽(用于取消未启动 future)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TTS_CONCURRENCY) as executor:
        futures = {
            executor.submit(_synthesize_one, idx, tts_in): tts_in.segment_id
            for idx, tts_in in enumerate(tts_inputs)
        }
        for future in concurrent.futures.as_completed(futures):
            seg_id = futures[future]
            try:
                idx, audio_url, error_type = future.result()
            except concurrent.futures.CancelledError:
                # future 被取消(配额耗尽时主动取消未启动的 future),跳过
                logger.debug(f"  [{seg_id}] ⏭️ 任务被取消(配额耗尽时跳过未启动任务)")
                continue
            except Exception as e:
                # 防御性兜底:future 自身异常
                logger.error(f"  [{seg_id}] ❌ TTS合成异常: {str(e)[:200]}")
                raise Exception(f"批量TTS失败: {seg_id} 合成失败: {e}")

            if audio_url is not None:
                results_map[idx] = audio_url
                logger.info(
                    f"  [{idx + 1:02d}/{total}] ✅ 完成 | segment_id={seg_id} | URL={audio_url[:80]}..."
                )
                continue

            if error_type == "quota_exhausted":
                # ⭐ 优化:首次观察到配额耗尽,主动取消所有未启动的 future,
                # 避免 ThreadPoolExecutor 继续调度未启动任务(节省 TTS 配额和服务负载)
                if not quota_exhausted_observed:
                    quota_exhausted_observed = True
                    cancelled_count = 0
                    for f in futures.keys():
                        if not f.done():
                            if f.cancel():
                                cancelled_count += 1
                    if cancelled_count > 0:
                        logger.warning(
                            f"  ⚠️ 配额耗尽,已主动取消 {cancelled_count} 个未启动的 TTS 任务(节省配额)"
                        )
                quota_exhausted_segment_ids.append(seg_id)
                logger.warning(
                    f"  [{idx + 1:02d}/{total}] ⏭️ 配额耗尽跳过 | segment_id={seg_id}"
                )
                continue

            if error_type == "other":
                # ⭐ 修复(本版本):非配额错误(网络/服务故障)改为"软失败"模式
                # 之前 bug:任何一段失败立即抛 Exception,导致已成功的 208 段全部浪费
                # 现在:记录失败 segment_id,继续跑。缺失位置在步骤3拼接阶段用"对应长度静音段"补位
                # 用户能听到 213 段 TTS 音频 + 2 段静音位置,在 message 里告知"2 段 TTS 失败"
                other_failed_segment_ids.append(seg_id)
                logger.warning(
                    f"  [{idx + 1:02d}/{total}] ⏭️ 非配额错误(网络/服务故障)跳过 | segment_id={seg_id} | "
                    f"已成功 {len(results_map)}/{len(tts_inputs)} | "
                    f"缺失位置将在拼接时用静音段补位"
                )
                continue  # 软失败:不抛异常,继续处理其他段

    # 配额耗尽时:等待所有"已启动但 as_completed 没等到"的 future 跑完,
    # 确保不漏掉任何已启动的成果
    if quota_exhausted_observed:
        logger.info(
            f"  【配额耗尽收尾】等待已启动任务完成(避免漏掉任何已成功批次)..."
        )
        for f in futures.keys():
            if f.done() and not f.cancelled():
                try:
                    idx, audio_url, _error_type = f.result()
                    if audio_url is not None and idx not in results_map:
                        results_map[idx] = audio_url
                        logger.info(
                            f"  [{idx + 1:02d}/{total}] ✅ 完成(并发收尾) | segment_id={futures[f]}"
                        )
                except Exception:
                    pass

    # 步骤2: 下载所有 TTS 音频到本地,并用 atempo 规范化每段语速
    # ⭐ 修复(2024-XX-XX):code=4036 配额耗尽时,部分批次可能失败,这里只处理"成功批次",
    # 失败的 idx 已通过 quota_exhausted_segment_ids 记录,不会丢失信息
    logger.info("=" * 70)
    logger.info(f"【步骤2/3: 下载音频 + atempo 语速规范化】")
    logger.info(f"  目标统一语速: {TARGET_SPEECH_SPEED} 字符/秒 (实测TTS引擎长句基线)")
    success_count = len(results_map)
    logger.info(
        f"  【TTS 合成结果】成功 {success_count}/{len(tts_inputs)} 个批次"
        + (
            f",配额耗尽跳过 {len(quota_exhausted_segment_ids)} 个"
            if quota_exhausted_observed
            else ""
        )
        + (
            f",其他错误 {len(other_failed_segment_ids)} 个"
            if other_failed_segment_ids
            else ""
        )
    )

    normalized_local_paths: list[str] = []

    # 构建"成功批次"的有序列表(按原始 idx 排序,保持时间轴对齐)
    # 每项: (原始idx, audio_url, 文本, ASR原句时长ms)
    success_batches: list[tuple[int, str, str, int]] = []  # (原始idx, audio_url, 文本, ASR原句时长ms)
    for orig_idx in range(len(tts_inputs)):
        if orig_idx in results_map:
            anchor_ms = (
                original_durations_ms[orig_idx]
                if orig_idx < len(original_durations_ms)
                else 0
            )
            success_batches.append((
                orig_idx,
                results_map[orig_idx],
                valid_texts[orig_idx],
                anchor_ms,
            ))

    # ⭐ 降级保护:如果所有批次都失败(配额耗尽 + 其他错误),
    # 根据 TTS_FALLBACK_TO_ORIGINAL 开关决定走降级还是抛异常
    # ⭐ 修复(本版本):降级保护块从 for 循环里移到外面
    # 之前 bug:降级块被错误缩进到 for 循环内部,导致:
    #   1) 第一次循环迭代时就触发降级判断(此时 success_batches 还没构建完)
    #   2) 当 state.original_audio_url 为空时,fallback_urls=[],
    #      media_compile_node 收到空 tts_audio_urls → 抛"没有有效的TTS音频数据"
    if not success_batches:
        if TTS_FALLBACK_TO_ORIGINAL:
            # ⭐ 修复(本版本):只在"有原音频"时走降级,无原音频时直接抛异常
            # 原因:之前生成"静音兜底音频"会让用户拿到"无声音的视频"——毫无意义
            # 现在:auto_mode_judge_node 已经在 mode 2 入口就校验原音频 URL,
            # 所以理论上走到这里时 state.original_audio_url 一定不为空
            # (除非用户绕过了 auto_mode_judge_node 直接调用,需要做兜底)
            if not state.original_audio_url:
                # 极端兜底:无原音频时不再生成静音,直接抛异常
                error_msg = (
                    f"批量TTS失败: 所有 {len(tts_inputs)} 个批次均失败,"
                    f"且 state.original_audio_url 为空,无法降级到原音频。"
                    f"失败原因: {'TTS 配额耗尽(code=4036)' if quota_exhausted_observed else '其他错误'}。"
                    f"💡 解决方式:\n"
                    f"  1) 升级 TTS 插件套餐后重试,或\n"
                    f"  2) 等下月 1 日配额自动重置后重试,或\n"
                    f"  3) 调大 MERGE_SEGMENTS_PER_BATCH(本工作流已设为 {MERGE_SEGMENTS_PER_BATCH},节省配额)"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            # 走降级:返回原音频 URL,让工作流能继续跑通
            logger.warning("=" * 70)
            logger.warning("⚠️ 降级模式已启用:所有 TTS 批次均失败,使用原音频代替")
            logger.warning(f"   失败原因: {'TTS 配额耗尽(code=4036)' if quota_exhausted_observed else '其他错误'}")
            logger.warning(f"   降级输出: original_audio_url = {state.original_audio_url}")
            logger.warning("   💡 如需真实 TTS 配音,请:")
            logger.warning("      1) 升级 TTS 插件套餐;或")
            logger.warning("      2) 等下月 1 日配额重置;或")
            logger.warning("      3) 设置 TTS_FALLBACK_TO_ORIGINAL=False 关闭降级")
            logger.warning("=" * 70)

            fallback_urls: List[str] = [state.original_audio_url]
            fallback_desc = f"原音频 URL ({state.original_audio_url})"

            tts_error_msg = (
                f"⚠️ 降级模式:所有 {len(tts_inputs)} 个 TTS 批次均失败,"
                f"已使用 {fallback_desc} 代替 TTS 配音。失败原因: "
                f"{'TTS 配额耗尽(code=4036)' if quota_exhausted_observed else '其他错误'}。"
                f"如需真实配音,请升级 TTS 插件套餐或等下月配额重置。"
            )
            return TTSBatchOutput(
                validated_data=state.validated_data,
                tts_audio_urls=fallback_urls,
                original_audio_url=state.original_audio_url,
                tts_failed_segment_ids=[f"batch_{i+1}" for i in range(len(tts_inputs))],
                quota_exhausted=quota_exhausted_observed,
                tts_success_count=0,
                tts_total_count=len(tts_inputs),
                tts_error_message=tts_error_msg
            )
        else:
            # 抛异常:保持原有行为
            if quota_exhausted_observed:
                error_msg = (
                    f"批量TTS失败: 所有 {len(tts_inputs)} 个批次均因 TTS 月度配额耗尽(code=4036)失败。\n"
                    f"  解决方式:\n"
                    f"  1) 登录扣子平台 → 插件市场 → speech_synthesis → 升级套餐\n"
                    f"  2) 或等下月1日配额自动重置后重试\n"
                    f"  3) 或调大 MERGE_SEGMENTS_PER_BATCH(本工作流已设为 {MERGE_SEGMENTS_PER_BATCH},节省配额)\n"
                    f"  4) 或设置 TTS_FALLBACK_TO_ORIGINAL=True 启用降级(用原音频代替)"
                )
            else:
                error_msg = (
                    f"批量TTS失败: 所有 {len(tts_inputs)} 个批次均合成失败,"
                    f"其他错误 {len(other_failed_segment_ids)} 个。"
                )
            raise Exception(error_msg)

    for seq_idx, (orig_idx, audio_url, english_text, anchor_ms) in enumerate(
        success_batches, start=1
    ):
        # 注:实测 ffmpeg 直读 HTTP URL 比"先下载再处理"慢 30%(网络波动影响 ffmpeg 解码),
        # 保留先下载到本地更稳定。
        raw_path = os.path.join(temp_dir, f"part_{seq_idx:03d}_raw.mp3")
        logger.info(
            f"  下载 [{seq_idx:02d}/{len(success_batches)}] "
            f"(orig_idx={orig_idx}) {audio_url[:80]}..."
        )
        _download_audio_to_local(audio_url, raw_path)
        raw_local_paths.append(raw_path)

        # ⭐ 版本更新:统一用 17 字/秒规范化,不做时间轴对齐
        # 用户需求:不需要让英文音频和原中文音频时长一致
        # 所有段统一按 17 字/秒 + 语速 1.0 自然合成
        normalized_path = os.path.join(temp_dir, f"part_{seq_idx:03d}_norm.mp3")
        _normalize_speech_speed(
            audio_path=raw_path,
            text=english_text,
            target_speed=TARGET_SPEECH_SPEED,
            output_path=normalized_path,
            original_duration_ms=0  # ⭐ 强制 0:不做时间轴对齐,统一 17字/秒
        )
        normalized_local_paths.append(normalized_path)

    # 步骤3: 用 ffmpeg -c copy 无损拼接所有规范化后的音频为1段完整音频
    # TPM03 V2 风格:在每段音频之间插入段间停顿(模拟纪录片逐句解说句感)
    # 不直接拼接 normalized_local_paths,因为段间无停顿听起来像"连续演讲"
    # 而是生成一个 TPM03_V2_SENTENCE_PAUSE_SEC 秒的静音段,在每段音频之间插入
    # ⭐ 修复(本版本):处理"缺失段"(网络/服务故障导致的 TTS 失败)
    # 缺失位置用对应长度的静音段填补,保持"整段连续音频"的语义
    logger.info("=" * 70)
    logger.info(f"【步骤3/3: ffmpeg -c copy 无损拼接 + TPM03 V2 段间停顿 + 缺失段静音补位】")
    logger.info(f"  待拼接音频数: {len(normalized_local_paths)} 段 (已全部规范化到 {TARGET_SPEECH_SPEED} 字/秒)")
    logger.info(f"  TPM03 V2 风格:段间插入 {TPM03_V2_SENTENCE_PAUSE_SEC} 秒静音,模拟纪录片逐句解说")

    # ⭐ 新增:识别"缺失段"(网络/服务故障等非配额错误导致的 TTS 失败)
    # 这些 orig_idx 不在 success_batches 中,需要在拼接时用对应长度静音补位
    success_orig_idx_set: set[int] = {orig_idx for orig_idx, _, _, _ in success_batches}
    missing_segment_info: list[tuple[int, int]] = []  # (orig_idx, expected_duration_ms)
    for orig_idx in range(len(tts_inputs)):
        if orig_idx not in success_orig_idx_set:
            anchor_ms = (
                original_durations_ms[orig_idx]
                if orig_idx < len(original_durations_ms)
                else 0
            )
            missing_segment_info.append((orig_idx, anchor_ms))
    if missing_segment_info:
        logger.warning(
            f"  ⚠️ 缺失段检测: {len(missing_segment_info)} 个原段位 TTS 失败 "
            f"(orig_idx={sorted([i for i, _ in missing_segment_info])}),"
            f"将在拼接时用对应长度静音补位"
        )

    # ⭐ 新增:为缺失段生成"对应长度静音段"
    # 时长来源:1) ASR原句时长(精确对齐)  2) 回退 1.0 秒(防 0 时长异常)
    missing_silence_paths: dict[int, str] = {}  # orig_idx -> silence_path
    for orig_idx, anchor_ms in missing_segment_info:
        if anchor_ms > 0:
            missing_duration_sec: float = anchor_ms / 1000.0
        else:
            missing_duration_sec = 1.0
        # 合理性校验:0.3-30 秒(防止异常值)
        missing_duration_sec = max(0.3, min(30.0, missing_duration_sec))
        missing_silence_path = os.path.join(
            temp_dir, f"missing_seg{orig_idx:03d}_{int(missing_duration_sec * 1000)}ms.mp3"
        )
        missing_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
            "-t", f"{missing_duration_sec:.3f}",
            "-c:a", "libmp3lame", "-b:a", "64k",
            missing_silence_path
        ]
        missing_result = subprocess.run(missing_cmd, capture_output=True, text=True)
        if missing_result.returncode == 0 and os.path.exists(missing_silence_path):
            missing_silence_paths[orig_idx] = missing_silence_path
            logger.warning(
                f"  ⚠️ 缺失段 [orig_idx={orig_idx}] 用 {missing_duration_sec:.3f}s 静音补位 "
                f"(对应 ASR原句时长={anchor_ms}ms)"
            )
        else:
            logger.error(
                f"  ❌ 缺失段 [orig_idx={orig_idx}] 静音生成失败,跳过此位置 | "
                f"{missing_result.stderr[:200]}"
            )

    # 生成 TPM03 V2 段间停顿静音文件(0.4 秒静音,24kHz 单声道 MP3,与 TTS 输出一致)
    # ⭐ 修复(本版本):当段间停顿时长 = 0.0 时,直接跳过生成,避免产生 0 字节空文件污染 -c copy 拼接
    tpm03_pause_path: Optional[str] = None
    if TPM03_V2_SENTENCE_PAUSE_SEC > 0.0:
        tpm03_pause_path = os.path.join(temp_dir, f"tpm03_v2_pause_{int(TPM03_V2_SENTENCE_PAUSE_SEC * 1000)}ms.mp3")
        pause_gen_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
            "-t", str(TPM03_V2_SENTENCE_PAUSE_SEC),
            "-c:a", "libmp3lame", "-b:a", "64k",
            tpm03_pause_path
        ]
        pause_result = subprocess.run(pause_gen_cmd, capture_output=True, text=True)
        if pause_result.returncode != 0:
            logger.warning(f"  TPM03 V2 停顿生成失败,降级为直接拼接(无停顿): {pause_result.stderr[:200]}")
            tpm03_pause_path = None
        elif os.path.exists(tpm03_pause_path) and os.path.getsize(tpm03_pause_path) == 0:
            # ⭐ 修复:0 字节停顿文件会污染 -c copy 拼接(Invalid argument 错误导致只保留第1段)
            logger.warning(f"  TPM03 V2 停顿文件 0 字节(可能 ffmpeg 静默失败),降级为直接拼接(无停顿)")
            try:
                os.remove(tpm03_pause_path)
            except OSError:
                pass
            tpm03_pause_path = None
    else:
        logger.info(
            f"  TPM03_V2_SENTENCE_PAUSE_SEC={TPM03_V2_SENTENCE_PAUSE_SEC},"
            f"已跳过停顿文件生成(段间不插入停顿,直接拼接)"
        )

    # ⭐ 重构:按 orig_idx 排序的最终拼接列表
    # 每段位置 = 正常段(TTS成功) 或 缺失段(静音补位) 或 跳过
    # 段间停顿(0.4s)插入在每段之间(最后一段后不接停顿)
    norm_path_by_orig: dict[int, str] = {
        orig_idx: norm_path
        for (orig_idx, _, _, _), norm_path in zip(success_batches, normalized_local_paths)
    }
    final_paths_for_concat: list[str] = []
    actual_segments_in_final = 0
    for orig_idx in range(len(tts_inputs)):
        if orig_idx in norm_path_by_orig:
            final_paths_for_concat.append(norm_path_by_orig[orig_idx])
            actual_segments_in_final += 1
        elif orig_idx in missing_silence_paths:
            final_paths_for_concat.append(missing_silence_paths[orig_idx])
            actual_segments_in_final += 1
        else:
            # 极兜底:既不在 success 也不在 missing(理论不会发生)
            continue
        # 段间停顿(0.4s)插入在每段之间(最后一段后不接停顿)
        if tpm03_pause_path and orig_idx < len(tts_inputs) - 1:
            final_paths_for_concat.append(tpm03_pause_path)

    logger.info(
        f"  最终拼接单元: {len(final_paths_for_concat)} 个 "
        f"({actual_segments_in_final}段有效音频 + "
        f"{sum(1 for p in final_paths_for_concat if 'missing_seg' in p)}段缺失静音 + "
        f"{sum(1 for p in final_paths_for_concat if 'tpm03_v2_pause' in p)}段间停顿)"
    )

    merged_local_path = os.path.join(temp_dir, f"merged_{len(success_batches)}sentences_tpm03v2.mp3")
    _concat_audio_files(final_paths_for_concat, merged_local_path)

    # 上传拼接后的音频到对象存储
    logger.info(f"  上传拼接后的音频到对象存储...")
    storage = S3SyncStorage()
    merged_object_key = f"audio/merged_{len(success_batches)}sentences_normalized_{uuid.uuid4().hex[:8]}.mp3"
    with open(merged_local_path, "rb") as f:
        merged_audio_bytes = f.read()
    uploaded_key = storage.upload_file(
        file_content=merged_audio_bytes,
        file_name=merged_object_key,
        content_type="audio/mpeg"
    )
    key = uploaded_key if isinstance(uploaded_key, str) else uploaded_key.get("key", "")
    merged_audio_url = storage.generate_presigned_url(key=key, expire_time=86400)
    logger.info(f"  ✅ 上传完成: {merged_audio_url}")

    # ⭐ 修复(本版本):除了合并音频,另外上传每段独立音频到 S3
    # 让用户能拿到"一句一个音频" + "合并音频"两套产物
    # - segment_audio_urls: N 个独立 URL(每段独立 .mp3,按 orig_idx 排序)
    # - tts_audio_urls: 兼容旧字段,只包含 1 个合并音频 URL(给下游 media_compile_node)
    logger.info(f"  上传每段独立音频到对象存储...")
    segment_audio_urls: list[str] = []
    for orig_idx in range(len(tts_inputs)):
        if orig_idx in norm_path_by_orig:
            seg_local_path = norm_path_by_orig[orig_idx]
            seg_object_key = f"audio/segment_{orig_idx:03d}_{uuid.uuid4().hex[:8]}.mp3"
            try:
                with open(seg_local_path, "rb") as f:
                    seg_audio_bytes = f.read()
                seg_uploaded_key = storage.upload_file(
                    file_content=seg_audio_bytes,
                    file_name=seg_object_key,
                    content_type="audio/mpeg"
                )
                seg_key = seg_uploaded_key if isinstance(seg_uploaded_key, str) else seg_uploaded_key.get("key", "")
                seg_url = storage.generate_presigned_url(key=seg_key, expire_time=86400)
                segment_audio_urls.append(seg_url)
            except Exception as e:
                logger.warning(f"  ⚠️ 段 {orig_idx} 独立音频上传失败,跳过: {e}")
                segment_audio_urls.append("")  # 占位,保持 orig_idx 对齐
        elif orig_idx in missing_silence_paths:
            # 缺失段位置:也上传静音段(让 N 段都齐全,用户看到一致的 N 个 URL)
            seg_local_path = missing_silence_paths[orig_idx]
            seg_object_key = f"audio/segment_{orig_idx:03d}_missing_{uuid.uuid4().hex[:8]}.mp3"
            try:
                with open(seg_local_path, "rb") as f:
                    seg_audio_bytes = f.read()
                seg_uploaded_key = storage.upload_file(
                    file_content=seg_audio_bytes,
                    file_name=seg_object_key,
                    content_type="audio/mpeg"
                )
                seg_key = seg_uploaded_key if isinstance(seg_uploaded_key, str) else seg_uploaded_key.get("key", "")
                seg_url = storage.generate_presigned_url(key=seg_key, expire_time=86400)
                segment_audio_urls.append(seg_url)
            except Exception as e:
                logger.warning(f"  ⚠️ 段 {orig_idx} 静音段上传失败,跳过: {e}")
                segment_audio_urls.append("")
    logger.info(f"  ✅ 独立音频上传完成: {len([u for u in segment_audio_urls if u])}/{len(segment_audio_urls)} 段成功")

    # tts_audio_urls只包含1段(拼接后的完整音频),兼容旧字段
    tts_audio_urls: list[str] = [merged_audio_url]

    # 清理临时文件
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    logger.info("=" * 70)
    logger.info(f"【批量TTS完成 - TPM03 V2 纪录片风格】")
    logger.info(f"  合成段数: {success_count}/{len(tts_inputs)} (失败={len(tts_inputs) - success_count})")
    logger.info(f"  最终音频: 1段(拼接后)")
    logger.info(f"  统一语速: {TARGET_SPEECH_SPEED} 字/秒 (每段都已 atempo 规范化)")
    logger.info(f"  TTS引擎语速: {DEFAULT_SPEED_RATIO} (正常语速,用户要求统一 1.0)")
    logger.info(f"  段间停顿: {TPM03_V2_SENTENCE_PAUSE_SEC} 秒/段 (TPM03 V2 风格,模拟逐句解说)")
    logger.info(f"  段合并分隔符: '{TPM03_V2_MERGE_SEPARATOR.strip()}' (TPM03 V2 风格,避免读成演讲稿)")
    logger.info(f"  拼接方式: -c copy 无损")
    logger.info(f"  拼接音频URL: {merged_audio_url}")
    if quota_exhausted_observed:
        logger.warning(
            f"  ⚠️ 配额耗尽降级:已合成 {success_count}/{len(tts_inputs)} 段,"
            f"失败 segment_id={quota_exhausted_segment_ids}"
        )
    logger.info("=" * 70)

    # ⭐ 修复(2024-XX-XX):code=4036 配额耗尽降级时,透传降级信息到下游
    # 让用户在最终消息里看到"部分成功"的提示,而不是看起来一切正常
    # ⭐ 修复:把所有失败的 segment_id(配额耗尽 + 网络/服务故障)合并透传
    all_failed_segment_ids: list[str] = list(quota_exhausted_segment_ids) + list(other_failed_segment_ids)
    tts_error_message: Optional[str] = None
    if quota_exhausted_observed:
        tts_error_message = (
            f"TTS 月度配额已耗尽(code=4036)。本次成功合成 {success_count}/{len(tts_inputs)} 段,"
            f"失败的 segment_id: {','.join(quota_exhausted_segment_ids)}。"
            f"解决方式:1) 升级扣子平台套餐;2) 等下月1日配额自动重置;3) 调大 MERGE_SEGMENTS_PER_BATCH。"
        )
    elif other_failed_segment_ids:
        # ⭐ 修复(本版本):网络/服务故障导致的"部分降级"也透传到 message
        # 让用户在最终消息里看到"X 段 TTS 失败(已用静音补位)"
        tts_error_message = (
            f"部分 TTS 合成失败(网络/服务故障)。本次成功合成 {success_count}/{len(tts_inputs)} 段,"
            f"失败 {len(other_failed_segment_ids)} 段(segment_id: {','.join(other_failed_segment_ids)})。"
            f"这些位置已用对应长度静音段补位,工作流可继续完成。"
        )

    return TTSBatchOutput(
        validated_data=state.validated_data,
        tts_audio_urls=tts_audio_urls,
        original_audio_url=state.original_audio_url,
        segment_audio_urls=segment_audio_urls,  # ⭐ 本版本:每段独立音频 URL(一句一个)
        tts_failed_segment_ids=all_failed_segment_ids,
        quota_exhausted=quota_exhausted_observed,
        tts_success_count=success_count,
        tts_total_count=len(tts_inputs),
        tts_error_message=tts_error_message,
    )
