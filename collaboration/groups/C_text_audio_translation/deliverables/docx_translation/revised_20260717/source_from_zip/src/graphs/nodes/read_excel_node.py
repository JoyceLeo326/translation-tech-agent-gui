"""
读取Excel节点 - 读取人工审核后的Excel，提取中文原文与人工审核英文对照对
"""
import os
import pandas as pd
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from utils.file.file import FileOps
from graphs.state import ReadExcelInput, ReadExcelOutput


def _normalize_col_name(col) -> str:
    """标准化列名，兼容中英文表头和空格/下划线差异。"""
    return str(col).strip().lower().replace(" ", "").replace("_", "")


def _find_column(col_names, aliases):
    """按别名优先级查找列名，找不到返回None。"""
    normalized = [(col, _normalize_col_name(col)) for col in col_names]
    for alias in aliases:
        alias_norm = _normalize_col_name(alias)
        for col, col_norm in normalized:
            if alias_norm and alias_norm in col_norm:
                return col
    return None


def _clean_cell(value) -> str:
    """把Excel单元格转成干净字符串，统一处理NaN/None。"""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def read_excel_node(state: ReadExcelInput, config: RunnableConfig, runtime: Runtime[Context]) -> ReadExcelOutput:
    """
    title: 读取审核Excel
    desc: 读取人工审核回填后的Excel，提取中文原文与人工审核英文的对照对，优先使用人工审核列，为空时自动沿用机器英文译文
    integrations: pandas, openpyxl
    """
    ctx = runtime.context

    # 确保文件已提供
    review_excel = state.review_excel
    if review_excel is None:
        raise ValueError("缺少必填参数：review_excel（人工审核后的Excel文件）")

    # 下载Excel文件到本地
    excel_path = FileOps.save_to_local(review_excel, "review_excel.xlsx")

    # 读取Excel
    df = pd.read_excel(excel_path, engine="openpyxl")

    # 自动识别列名：关键列缺失时直接报错，避免静默读错列。
    col_names = list(df.columns)
    cn_col = _find_column(col_names, [
        "中文原文", "书本文字", "音频文字", "原文", "source", "chinese", "cn"
    ])
    review_col = _find_column(col_names, [
        "人工审核", "人工审校", "人工校对", "审核译文", "审校译文", "final", "review", "manual", "human"
    ])
    machine_col = _find_column(col_names, [
        "机器英文译文", "机器英文", "机器译文", "机器翻译", "英文译文", "machine", "mt"
    ])

    if cn_col is None:
        raise ValueError(
            f"审核Excel缺少中文原文列。请使用列名：中文原文/书本文字/原文/source/chinese。当前列：{col_names}"
        )
    if review_col is None and machine_col is None:
        raise ValueError(
            f"审核Excel缺少可用英文译文列。请至少提供人工审核列或机器英文译文列。当前列：{col_names}"
        )

    cn_en_pairs = []
    lines = []
    for _, row in df.iterrows():
        cn_text = _clean_cell(row.get(cn_col, ""))
        if not cn_text:
            continue

        # 优先取人工审核列，为空时取机器英文译文
        en_text = _clean_cell(row.get(review_col, "")) if review_col else ""
        if not en_text and machine_col:
            en_text = _clean_cell(row.get(machine_col, ""))

        cn_en_pairs.append((cn_text, en_text))
        if en_text:
            lines.append(en_text)

    final_full_en = "\n".join(lines)

    # 清理临时文件
    try:
        os.remove(excel_path)
    except Exception:
        pass

    return ReadExcelOutput(
        final_full_en=final_full_en,
        cn_en_pairs=cn_en_pairs,
    )
