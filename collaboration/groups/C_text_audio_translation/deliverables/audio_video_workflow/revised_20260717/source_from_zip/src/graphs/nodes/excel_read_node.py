"""
Excel读取节点 - 从定稿Excel中只提取人工审核列内容
"""
import os
import time
import zipfile
import logging
import requests
import pandas as pd
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ExcelReadInput, ExcelReadOutput
from utils.file.file import File, FileOps


logger = logging.getLogger(__name__)


# HTTP请求头
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def _is_valid_xlsx(file_path: str) -> bool:
    """
    验证文件是否是有效的xlsx(本质是zip)
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # xlsx文件必须包含 [Content_Types].xml
            return '[Content_Types].xml' in zf.namelist()
    except (zipfile.BadZipFile, Exception):
        return False


def _download_with_retry(file_obj: File, max_retries: int = 3) -> str:
    """
    带重试机制的文件下载（本地+远程都支持）

    关键点:
    - 本地文件: FileOps.save_to_local 直接返回原 url(不会复制到 /tmp)
    - 远程文件: FileOps.save_to_local 下载到 /tmp/{filename}
    - 因此必须用 FileOps.save_to_local 的返回值作为 local_path,不能硬编码
    - 403/401 错误: 预签名 URL 已过期，立即终止重试（重试无意义）

    Returns:
        str: 文件的最终本地路径
    """
    filename = "finalized_excel.xlsx"
    last_error: Exception | None = None
    last_error_msg: str = ""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"下载Excel (尝试 {attempt}/{max_retries}): {file_obj.url}")

            # ✅ 使用平台 FileOps(自动处理 TOS 签名 URL 过期/认证,本地文件直接返回原路径)
            saved_path = FileOps.save_to_local(file_obj, filename)

            # 下载成功后立即验证文件
            if _is_valid_xlsx(saved_path):
                logger.info(f"下载成功且验证为有效xlsx: {saved_path}")
                return saved_path
            else:
                # 检查文件内容,看是否是HTML错误页面
                file_size = os.path.getsize(saved_path) if os.path.exists(saved_path) else 0
                with open(saved_path, 'rb') as f:
                    head = f.read(200)
                is_html = b'<html' in head.lower() or b'<!doctype html' in head.lower()
                if is_html:
                    raise RuntimeError(f"下载的内容是HTML页面而非xlsx文件(可能URL已过期或重定向到错误页)")
                else:
                    raise RuntimeError(f"下载的文件不是有效的xlsx格式 (大小: {file_size} bytes)")

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
            last_error = e
            last_error_msg = str(e)
            # 403 Forbidden / 401 Unauthorized: 预签名 URL 已过期或无权访问，重试无意义
            if status_code in (401, 403):
                logger.error(
                    f"Excel预签名URL已过期(HTTP {status_code})，停止重试。"
                    f"请重新上传Excel文件获取新的预签名URL。"
                )
                raise RuntimeError(
                    f"Excel文件预签名URL已过期(HTTP {status_code})，请重新上传Excel文件。"
                    f"原URL: {file_obj.url[:120]}..."
                ) from e
            logger.warning(f"第{attempt}次下载失败(HTTP {status_code}): {last_error_msg}")
            if attempt >= max_retries:
                break
            wait_time = 2 ** attempt
            logger.info(f"等待{wait_time}秒后重试...")
            time.sleep(wait_time)

        except Exception as e:
            last_error = e
            last_error_msg = str(e)
            logger.warning(f"第{attempt}次下载失败: {last_error_msg}")
            if attempt < max_retries:
                # 指数退避
                wait_time = 2 ** attempt
                logger.info(f"等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                break

    # 所有重试都失败
    raise RuntimeError(f"下载失败(已重试{max_retries}次): {last_error_msg}")


def excel_read_node(
    state: ExcelReadInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ExcelReadOutput:
    """
    title: Excel文件读取
    desc: 从定稿Excel中只读取人工审核列的英文内容,放弃原有翻译列
    integrations: 文件读取
    """
    ctx = runtime.context

    # 检查文件是否存在
    if state.finalized_excel is None:
        raise Exception("模式2需要提供定稿Excel文件,但finalized_excel为空")

    excel_url = state.finalized_excel.url
    logger.info(f"开始读取Excel文件: {excel_url}")

    # 第一步:下载Excel文件(带重试,使用平台FileOps处理签名URL/认证)
    try:
        local_path = _download_with_retry(state.finalized_excel, max_retries=3)
    except RuntimeError as e:
        err_msg = str(e)
        # 检测是否为预签名URL过期(403/401)，给出针对性修复建议
        if "预签名URL已过期" in err_msg or "403" in err_msg or "401" in err_msg:
            raise Exception(
                f"Excel文件预签名URL已过期，请重新上传Excel文件获取新的下载链接。\n"
                f"错误详情: {err_msg}"
            ) from e
        logger.error(f"Excel文件下载失败: {err_msg}")
        raise Exception(f"Excel文件下载失败: {err_msg}") from e
    except Exception as e:
        logger.error(f"Excel文件下载失败: {str(e)}")
        raise Exception(f"Excel文件下载失败: {str(e)}") from e

    # 第二步:验证文件有效性
    if not _is_valid_xlsx(local_path):
        file_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        raise Exception(
            f"下载的文件不是有效的Excel格式 (大小: {file_size} bytes)。"
            f"可能原因: 1)URL已过期(预签名URL有效期有限) 2)网络问题导致下载不完整 3)文件被损坏"
        )

    # 第三步:解析Excel内容
    try:
        df = pd.read_excel(local_path, engine='openpyxl')
        logger.info(f"读取到{len(df)}行数据,列名: {list(df.columns)}")
    except Exception as e:
        logger.error(f"Excel解析失败: {str(e)}")
        raise Exception(f"Excel文件解析失败: {str(e)}")

    # 第四步:识别列名
    chinese_col = None
    manual_col = None
    machine_col = None
    for col in df.columns:
        col_str = str(col).strip()
        if col_str in ("音频文字", "中文原文", "中文"):
            chinese_col = col
        elif col_str in ("人工审核", "审核", "final_translation", "Final Translation"):
            manual_col = col
        elif col_str in ("机器译文", "机器翻译", "译文", "machine_translation"):
            machine_col = col

    if manual_col is None:
        raise Exception(
            f"Excel中找不到【人工审核】列,当前列名: {list(df.columns)}。"
            f"支持的列名: 人工审核/审核/final_translation/Final Translation"
        )

    logger.info(f"识别列: 中文={chinese_col}, 人工审核={manual_col}, 机器译文={machine_col}")

    # 第五步:提取数据
    table_data: list[dict[str, Any]] = []
    manual_review_list: list[str] = []

    for idx, row in df.iterrows():
        row_dict: dict[str, Any] = {}

        # 提取中文原文(可选,用于辅助)
        if chinese_col is not None:
            chinese_val = row[chinese_col]
            chinese_str = "" if (chinese_val is None or str(chinese_val) in ("nan", "NaN")) else str(chinese_val).strip()
            row_dict["音频文字"] = chinese_str

        # 提取人工审核列(核心字段)
        manual_val = row[manual_col]
        manual_str = "" if (manual_val is None or str(manual_val) in ("nan", "NaN")) else str(manual_val).strip()
        row_dict["人工审核"] = manual_str

        # ⭐ 修复(本版本):先提取机器译文,再判断"两列都空才跳过"
        # 之前 bug:人工审核为空就 continue,导致机器译文永远不会被读取
        # 现在:人工审核为空时降级到机器译文,用户可只修改部分句子,其他沿用机器翻译
        if machine_col is not None:
            machine_val = row[machine_col]
            machine_str = "" if (machine_val is None or str(machine_val) in ("nan", "NaN")) else str(machine_val).strip()
            row_dict["机器译文"] = machine_str
        else:
            machine_str = ""

        # 跳过"两列都空"的行
        if not manual_str and not machine_str:
            idx_int: int = int(idx) if isinstance(idx, int) else 0
            logger.warning(f"第{idx_int + 1}行人工审核列和机器翻译列都为空,已跳过")
            continue

        # 保留原始行号
        row_index_int: int = int(idx) if isinstance(idx, int) else 0
        row_dict["_row_index"] = row_index_int

        table_data.append(row_dict)
        manual_review_list.append(manual_str)

    if not table_data:
        raise Exception("Excel中没有有效的人工审核数据(所有审核列都为空)")

    # 输出核对日志
    logger.info(f"=" * 60)
    logger.info(f"【人工审核列核对】共读取 {len(manual_review_list)} 条非空文本")
    logger.info(f"=" * 60)
    for i, text in enumerate(manual_review_list, 1):
        logger.info(f"  [{i}/{len(manual_review_list)}] {text}")
    logger.info(f"=" * 60)

    logger.info(f"Excel数据读取完成,共{len(table_data)}行(已过滤空审核行)")

    return ExcelReadOutput(table_data=table_data)
