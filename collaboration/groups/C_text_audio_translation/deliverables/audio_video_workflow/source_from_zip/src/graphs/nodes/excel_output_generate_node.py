"""
模式二输出Excel生成节点 - 自动生成四列表格(音频文字/机器译文/人工审核/音频下载地址)
"""
import logging
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import DocumentGenerationClient
from graphs.state import ExcelOutputGenerateInput, ExcelOutputGenerateOutput

logger = logging.getLogger(__name__)


def excel_output_generate_node(
    state: ExcelOutputGenerateInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ExcelOutputGenerateOutput:
    """
    title: 输出Excel生成
    desc: 模式二结束后自动生成四列Excel(音频文字/机器译文/人工审核/音频下载地址),音频地址填入分段独立TTS音频链接(非合并音频)
    integrations: 无
    """
    ctx = runtime.context

    table_data: List[Dict[str, Any]] = state.table_data
    segment_audio_urls: List[str] = state.segment_audio_urls

    logger.info(f"开始生成输出Excel, 表格数据{len(table_data)}行, 音频URL{len(segment_audio_urls)}个")

    if len(table_data) == 0:
        logger.warning("table_data为空,返回空URL")
        return ExcelOutputGenerateOutput(excel_output_url="")

    # 构造四列表格(2D list), 每个cell独立写入, 避免CSV引号转义问题
    excel_data_2d: List[List[str]] = [['音频文字', '机器译文', '人工审核', '音频下载地址']]

    for idx, row in enumerate(table_data):
        chinese_text: str = str(row.get("音频文字", "")).strip()
        machine_translation: str = str(row.get("机器译文", "")).strip()
        manual_review: str = str(row.get("人工审核", "")).strip()

        # 按行一一匹配音频URL
        audio_url: str = ""
        if idx < len(segment_audio_urls):
            audio_url = segment_audio_urls[idx]

        excel_data_2d.append([chinese_text, machine_translation, manual_review, audio_url])

    data_rows: int = len(excel_data_2d) - 1
    logger.info(f"输出Excel: {data_rows}行数据(不含表头), 音频URL填充{min(len(segment_audio_urls), data_rows)}条")

    # 生成Excel文件并上传
    try:
        doc_client = DocumentGenerationClient()
        excel_output_url: str = doc_client.create_xlsx_from_2d_list(
            excel_data_2d,
            "翻译成品输出",
            "Sheet1"
        )
        logger.info(f"输出Excel已生成: {excel_output_url}")
    except Exception as e:
        logger.error(f"输出Excel生成失败: {str(e)}")
        raise Exception(f"输出Excel生成失败: {str(e)}") from e

    return ExcelOutputGenerateOutput(excel_output_url=excel_output_url)
