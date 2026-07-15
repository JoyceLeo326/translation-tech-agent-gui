import os
import re
import json
import pandas as pd
from io import BytesIO
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import GenerateExcelInput, GenerateExcelOutput
from utils.file.file import File, FileOps
from coze_coding_dev_sdk.s3 import S3SyncStorage


def generate_excel_node(state: GenerateExcelInput, config: RunnableConfig, runtime: Runtime[Context]) -> GenerateExcelOutput:
    """
    title: 生成Excel
    desc: 将完整分层分句的中英文内容对齐输出为三列对照Excel（中文原文、机器英文译文、人工审核空白列）
    integrations: pandas, openpyxl, S3对象存储
    """
    ctx = runtime.context

    cn_raw = state.cn_raw
    en_raw = state.en_raw

    # 解析带行号的文本，提取[行号] 内容
    def parse_numbered_text(text):
        """解析带行号的文本，返回按行号排序的 (行号, 内容) 列表"""
        lines = text.split("\n")
        result = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r'\[(\d+)\]\s*(.*)', line)
            if m:
                line_num = int(m.group(1))
                content = m.group(2).strip()
                result.append((line_num, content))
        return result

    # 解析中文和英文
    cn_items = parse_numbered_text(cn_raw)
    en_items = parse_numbered_text(en_raw)

    # 按行号构建字典
    cn_map = {num: content for num, content in cn_items}
    en_map = {num: content for num, content in en_items}

    # 合并所有行号
    all_nums = sorted(set(cn_map.keys()) | set(en_map.keys()))

    # 构建对齐的中英文行列表（每行直接对应，不再额外拆分句子）
    cn_lines = []
    en_lines = []

    for num in all_nums:
        cn_content = cn_map.get(num, "")
        en_content = en_map.get(num, "")
        cn_lines.append(cn_content)
        en_lines.append(en_content if en_content else "")

    # 行数对齐
    max_len = max(len(cn_lines), len(en_lines))
    cn_lines += [""] * (max_len - len(cn_lines))
    en_lines += [""] * (max_len - len(en_lines))

    df = pd.DataFrame({
        "中文原文": cn_lines,
        "机器英文译文": en_lines,
        "人工审核": [""] * max_len
    })

    # 保存到临时文件
    local_path = "/tmp/translation_result.xlsx"
    df.to_excel(local_path, index=False, engine="openpyxl")

    # 上传到对象存储
    storage = S3SyncStorage()
    with open(local_path, "rb") as f:
        key = storage.upload_file(file_content=f.read(), file_name=f"translation_excel_{ctx.run_id}.xlsx")

    # 生成预签名URL
    file_url = storage.generate_presigned_url(key=key, expire_time=86400)

    # 清理临时文件
    if os.path.exists(local_path):
        os.remove(local_path)

    return GenerateExcelOutput(
        origin_excel=File(url=file_url, file_type="document")
    )