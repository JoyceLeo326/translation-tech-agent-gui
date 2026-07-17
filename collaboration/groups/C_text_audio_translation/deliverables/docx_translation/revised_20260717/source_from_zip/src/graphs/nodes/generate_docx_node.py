"""
生成DOCX节点 - 直接操作XML替换文本，100%保留每个run的格式（字体、加粗、斜体、颜色等）
不再依赖python-docx的save()，改用ZIP内直接修改word/document.xml的<w:t>文本节点
"""
import os
import re
import io
import json
import zipfile
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Set
from urllib.parse import urlparse, parse_qs, unquote
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from coze_coding_dev_sdk.s3 import S3SyncStorage
from langchain_core.messages import SystemMessage, HumanMessage
from graphs.state import GenerateDocxInput, GenerateDocxOutput
from utils.file.file import File


# Word XML 命名空间
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', W_NS)
CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')

def w(tag: str) -> str:
    """返回带命名空间的标签名"""
    return f'{{{W_NS}}}{tag}'


def normalize_text(text: str) -> str:
    """标准化文本，用于匹配（消除空格差异、标点差异）"""
    t = text.strip()
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'，', ',', t)
    t = re.sub(r'、', ',', t)
    t = re.sub(r'；', ';', t)
    t = re.sub(r'。', '.', t)
    t = re.sub(r'！', '!', t)
    t = re.sub(r'？', '?', t)
    t = re.sub(r'「', '"', t)
    t = re.sub(r'」', '"', t)
    t = re.sub(r'“', '"', t)
    t = re.sub(r'”', '"', t)
    t = re.sub(r'‘', "'", t)
    t = re.sub(r'’', "'", t)
    return t


def _invoke_llm(client: LLMClient, messages, llm_config: dict, defaults: dict):
    """按配置调用LLM；SDK不支持thinking参数时自动回退，避免运行时失败。"""
    kwargs = {
        "messages": messages,
        "model": llm_config.get("model", defaults["model"]),
        "temperature": llm_config.get("temperature", defaults["temperature"]),
        "top_p": llm_config.get("top_p", defaults["top_p"]),
        "max_completion_tokens": llm_config.get("max_completion_tokens", defaults["max_completion_tokens"]),
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


def extract_filename_from_url(url: str) -> str:
    """从URL中提取原始文件名"""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'file_path' in qs:
            raw = unquote(qs['file_path'][0])
            basename = os.path.basename(raw)
            if basename:
                return basename
        path = unquote(parsed.path)
        basename = os.path.basename(path)
        if basename:
            basename = basename.split('?')[0]
            return basename
    except Exception:
        pass
    return "document"


def translate_filename_to_english(filename: str, ctx) -> str:
    """使用LLM将中文文件名翻译为英文"""
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"), "config/filename_translate_cfg.json")
    try:
        with open(cfg_file, "r") as fd:
            _cfg = json.load(fd)
    except Exception:
        return filename

    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    llm_config = _cfg.get("config", {})

    name_without_ext = os.path.splitext(filename)[0]
    name_without_ext = re.sub(r'_\d{14,}$', '', name_without_ext)
    name_without_ext = re.sub(r'^[^-]+-', '', name_without_ext)

    if not name_without_ext.strip():
        return filename

    try:
        up_tpl = Template(up)
        user_prompt = up_tpl.render({"filename": name_without_ext})

        client = LLMClient(ctx=ctx)
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=user_prompt),
        ]
        response = _invoke_llm(
            client=client,
            messages=messages,
            llm_config=llm_config,
            defaults={
                "model": "doubao-seed-2-0-lite-260215",
                "temperature": 0.0,
                "top_p": 0.7,
                "max_completion_tokens": 256,
            },
        )

        resp_content = response.content
        if isinstance(resp_content, str):
            en_name = resp_content.strip()
        elif isinstance(resp_content, list):
            text_parts = []
            for item in resp_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            en_name = " ".join(text_parts).strip()
        else:
            en_name = str(resp_content).strip()

        en_name = en_name.strip('"\' \n\r\t')
        en_name = re.sub(r'\s+', ' ', en_name)

        if en_name:
            return en_name
    except Exception:
        pass

    return name_without_ext


def replace_in_xml_paragraphs(
    xml_root: ET.Element,
    sorted_keys: list,
    cn_to_en: dict,
    matched_keys: Optional[Set[str]] = None,
    is_header_footer: bool = False,
) -> int:
    """
    在XML树中遍历所有<w:p>段落，按比例将英文分配到各个<w:t>，保留每个run的原始格式
    is_header_footer: 是否为页眉页脚文件（需要处理标记去除）
    返回替换的段落数
    """
    replaced_count = 0
    p_tag = w('p')
    t_tag = w('t')

    for p_elem in xml_root.iter(p_tag):
        # 找到该段落内所有<w:t>元素
        t_elems = list(p_elem.iter(t_tag))
        if not t_elems:
            continue

        # 构建完整段落文本
        full_text = ''.join(t.text or '' for t in t_elems)
        if not full_text.strip():
            continue

        # 如果是页眉页脚文件，检查是否有页码字段，如果有则移除数字
        if is_header_footer:
            # 检查段落中是否有页码字段（fldChar）
            has_page_field = False
            for elem in p_elem.iter():
                if elem.tag == f'{{{W_NS}}}fldChar':
                    has_page_field = True
                    break
            # 如果有页码字段，移除数字（与提取时保持一致）
            if has_page_field:
                full_text = re.sub(r'\d+', '', full_text).strip()

        norm_para = normalize_text(full_text)

        # 查找匹配的英文翻译
        best_match = None
        current_matched_keys = []

        # 如果是页眉页脚文件，同时尝试匹配带标记和不带标记的版本
        search_texts = [norm_para]
        if is_header_footer:
            # 尝试添加[页眉]或[页脚]标记
            search_texts.append(normalize_text(f"[页眉]{full_text}"))
            search_texts.append(normalize_text(f"[页脚]{full_text}"))

        for search_text in search_texts:
            # 1. 精确匹配
            for key in sorted_keys:
                if search_text == key:
                    best_match = cn_to_en[key]
                    current_matched_keys = [key]
                    break
            
            if best_match:
                break

            # 2. 子串匹配（key在段落中）
            replacements = []
            for key in sorted_keys:
                if key in search_text:
                    replacements.append((key, cn_to_en[key]))
            if replacements:
                replacements.sort(key=lambda x: search_text.find(x[0]))
                combined_en = " ".join(en for _, en in replacements)
                total_key_len = sum(len(k) for k, _ in replacements)
                if total_key_len > len(search_text) * 0.3:
                    best_match = combined_en
                    current_matched_keys = [k for k, _ in replacements]
                    break

            # 3. 反向匹配（段落是key的子串）
            for key in sorted_keys:
                if search_text in key:
                    best_match = cn_to_en[key]
                    current_matched_keys = [key]
                    break
            
            if best_match:
                break

        # 如果是页眉页脚文件，去除翻译结果中的标记
        if best_match and is_header_footer:
            # 去除可能的标记（中英文）
            markers = ['[Header]', '[Footer]', '[页眉]', '[页脚]', '[HEADER]', '[FOOTER]']
            for marker in markers:
                best_match = best_match.replace(marker, '').strip()
            # 去除开头可能的空格和标点
            best_match = re.sub(r'^[\s\-\—\:：]+', '', best_match)

        if best_match:
            if matched_keys is not None:
                matched_keys.update(current_matched_keys)
            total_chars = len(full_text)
            en_text = best_match

            # 如果是页眉页脚且有页码字段，只替换非页码的<w:t>元素
            if is_header_footer and has_page_field:
                # 找到页码字段所在的<w:r>元素，排除其<w:t>
                page_field_runs = set()
                for r_elem in p_elem.iter(f'{{{W_NS}}}r'):
                    for fld_elem in r_elem.iter(f'{{{W_NS}}}fldChar'):
                        page_field_runs.add(r_elem)
                
                # 只替换非页码run中的<w:t>
                non_page_t_elems = []
                for t_elem in t_elems:
                    # 检查<w:t>是否在页码run中
                    is_in_page_run = False
                    for r_elem in p_elem.iter(f'{{{W_NS}}}r'):
                        if r_elem in page_field_runs:
                            for child_t in r_elem.iter(f'{{{W_NS}}}t'):
                                if child_t is t_elem:
                                    is_in_page_run = True
                                    break
                        if is_in_page_run:
                            break
                    if not is_in_page_run:
                        non_page_t_elems.append(t_elem)
                
                if non_page_t_elems:
                    # 计算非页码run的总字符数
                    non_page_total = sum(len(t.text or '') for t in non_page_t_elems)
                    if non_page_total > 0:
                        # 按比例分配英文到非页码run
                        run_ratios = []
                        current_pos = 0
                        for t_elem in non_page_t_elems:
                            run_len = len(t_elem.text or '')
                            start_ratio = current_pos / non_page_total
                            end_ratio = (current_pos + run_len) / non_page_total
                            run_ratios.append((start_ratio, end_ratio))
                            current_pos += run_len
                        
                        en_len = len(en_text)
                        for i, t_elem in enumerate(non_page_t_elems):
                            s_ratio, e_ratio = run_ratios[i]
                            en_start = int(round(s_ratio * en_len))
                            en_end = int(round(e_ratio * en_len))
                            en_start = max(0, min(en_start, en_len))
                            en_end = max(en_start, min(en_end, en_len))
                            t_elem.text = en_text[en_start:en_end]
                            t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                    else:
                        # 非页码run为空，直接替换第一个非页码run
                        non_page_t_elems[0].text = en_text
                        non_page_t_elems[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            elif total_chars > 0 and len(t_elems) > 1:
                # 按比例分配英文到各个run
                # 先计算每个run的起始位置比例
                run_ratios = []
                current_pos = 0
                for t_elem in t_elems:
                    run_len = len(t_elem.text or '')
                    if current_pos + run_len > total_chars:
                        run_len = total_chars - current_pos
                    if run_len < 0:
                        run_len = 0
                    start_ratio = current_pos / total_chars if total_chars > 0 else 0
                    end_ratio = (current_pos + run_len) / total_chars if total_chars > 0 else 1
                    run_ratios.append((start_ratio, end_ratio))
                    current_pos += run_len

                en_len = len(en_text)
                for i, t_elem in enumerate(t_elems):
                    s_ratio, e_ratio = run_ratios[i]
                    en_start = int(round(s_ratio * en_len))
                    en_end = int(round(e_ratio * en_len))
                    # 边界保护
                    en_start = max(0, min(en_start, en_len))
                    en_end = max(en_start, min(en_end, en_len))
                    t_elem.text = en_text[en_start:en_end]
                    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            else:
                # 单run段落，直接替换
                t_elems[0].text = en_text
                t_elems[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                for t_elem in t_elems[1:]:
                    t_elem.text = ''

            replaced_count += 1

    return replaced_count


def _collect_chinese_residue(xml_root: ET.Element, limit: int = 30) -> list:
    """收集XML中仍含中文的文本片段，用于生成替换报告。"""
    snippets = []
    seen = set()
    t_tag = w('t')
    for t_elem in xml_root.iter(t_tag):
        text = (t_elem.text or "").strip()
        if not text or not CHINESE_RE.search(text):
            continue
        snippet = text[:120]
        if snippet in seen:
            continue
        seen.add(snippet)
        snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets


def process_xml_file(
    zin: zipfile.ZipFile,
    xml_path: str,
    sorted_keys: list,
    cn_to_en: dict,
    matched_keys: Set[str],
    is_header_footer: bool = False,
):
    """处理单个XML文件，返回修改后的XML bytes、替换段落数、中文残留片段。"""
    raw_xml = zin.read(xml_path)
    root = ET.fromstring(raw_xml)
    replaced_count = replace_in_xml_paragraphs(root, sorted_keys, cn_to_en, matched_keys, is_header_footer)
    residue = _collect_chinese_residue(root)
    return ET.tostring(root, xml_declaration=True, encoding='UTF-8'), replaced_count, residue


def _build_replace_report(
    total_items: int,
    replaced_xml_blocks: int,
    matched_keys: Set[str],
    key_to_original: dict,
    failed_xml_files: list,
    residue_snippets: list,
    output_url: str,
) -> str:
    """生成用户可见的DOCX替换覆盖报告。"""
    unmatched = [key_to_original[key] for key in key_to_original if key not in matched_keys]
    lines = [
        "DOCX替换覆盖报告",
        f"- 原始对照条目数：{total_items}",
        f"- 已命中文本条目数：{len(matched_keys)}",
        f"- 替换XML段落/块数：{replaced_xml_blocks}",
        f"- 未命中文本条目数：{len(unmatched)}",
        f"- 处理失败XML文件数：{len(failed_xml_files)}",
        f"- 中文残留片段数（最多统计30条）：{len(residue_snippets)}",
        f"- 输出文件：{output_url}",
    ]
    if unmatched:
        lines.append("")
        lines.append("未命中文本（前20条）：")
        lines.extend(f"{idx + 1}. {text[:160]}" for idx, text in enumerate(unmatched[:20]))
    if failed_xml_files:
        lines.append("")
        lines.append("处理失败XML文件：")
        lines.extend(f"- {name}" for name in failed_xml_files[:20])
    if residue_snippets:
        lines.append("")
        lines.append("中文残留片段（前30条）：")
        lines.extend(f"{idx + 1}. {text}" for idx, text in enumerate(residue_snippets[:30]))
    return "\n".join(lines)


def generate_docx_node(state: GenerateDocxInput, config: RunnableConfig, runtime: Runtime[Context]) -> GenerateDocxOutput:
    """
    title: 替换生成英文DOCX（XML级操作）
    desc: 下载原始DOCX，直接修改word/document.xml中的<w:t>文本节点，保留所有run的原始格式
    integrations: S3对象存储
    """
    ctx = runtime.context

    # 获取原始DOCX文件
    file_docx = state.file_docx
    cn_en_pairs = state.cn_en_pairs
    if not cn_en_pairs:
        raise ValueError("缺少中文→英文对照对数据")

    if file_docx is None or not file_docx.url:
        raise ValueError("支路二需要同时上传审核Excel和原始DOCX文件，请补充file_docx后重新运行。")

    docx_path_or_url = file_docx.url

    original_path = "/tmp/original_docx.docx"
    if docx_path_or_url.startswith("http://") or docx_path_or_url.startswith("https://"):
        resp = requests.get(docx_path_or_url, timeout=60)
        if resp.status_code != 200:
            raise ValueError(f"下载原始DOCX失败，状态码: {resp.status_code}")
        with open(original_path, "wb") as f:
            f.write(resp.content)
    else:
        import shutil
        shutil.copy2(docx_path_or_url, original_path)

    # 构建中文→英文映射
    cn_to_en = {}
    key_to_original = {}
    for cn_text, en_text in cn_en_pairs:
        if not en_text:
            continue
        norm_cn = normalize_text(cn_text)
        if norm_cn and norm_cn not in cn_to_en:
            cn_to_en[norm_cn] = en_text
            key_to_original[norm_cn] = cn_text

    if not cn_to_en:
        raise ValueError("审核Excel中没有可用于回填的英文译文，请补充人工审核列或机器英文译文列。")

    sorted_keys = sorted(cn_to_en.keys(), key=len, reverse=True)

    # 直接操作ZIP内的XML文件
    output_path = "/tmp/output_en_docx_final.docx"
    # 只处理包含文本内容的XML文件（跳过fontTable/settings/styles/_rels/theme）
    skip_prefixes = ('word/_rels/', 'word/theme/', 'word/fontTable', 'word/settings', 'word/styles')

    total_replaced_blocks = 0
    matched_keys: Set[str] = set()
    failed_xml_files = []
    residue_snippets = []

    with zipfile.ZipFile(original_path, 'r') as zin:
        # 获取所有文件列表
        all_files = set(zin.namelist())

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                fname = item.filename

                # 判断是否需要处理文本替换
                should_process = (fname.startswith('word/') and
                                  fname.endswith('.xml') and
                                  not fname.startswith(skip_prefixes))

                if should_process and fname in all_files:
                    # 判断是否为页眉页脚文件
                    is_header_footer = bool(re.match(r'word/(header|footer)\d+\.xml$', fname))
                    
                    # 处理该XML文件（替换文本）
                    try:
                        modified_xml, replaced_count, residue = process_xml_file(
                            zin, fname, sorted_keys, cn_to_en, matched_keys, is_header_footer
                        )
                        total_replaced_blocks += replaced_count
                        for snippet in residue:
                            if snippet not in residue_snippets:
                                residue_snippets.append(snippet)
                        zout.writestr(item, modified_xml)
                    except Exception as e:
                        # 如果处理失败，回退到原始内容
                        failed_xml_files.append(fname)
                        zout.writestr(item, zin.read(fname))
                else:
                    # 直接复制原始内容
                    zout.writestr(item, zin.read(fname))

    # 提取原始文件名并翻译为英文
    original_filename = extract_filename_from_url(docx_path_or_url)
    en_filename = translate_filename_to_english(original_filename, ctx)
    if not en_filename.lower().endswith('.docx'):
        en_filename += '.docx'
    output_docx_name = en_filename

    # 上传到对象存储
    storage = S3SyncStorage(
        endpoint_url=os.getenv("COZE_BUCKET_ENDPOINT_URL"),
        access_key="",
        secret_key="",
        bucket_name=os.getenv("COZE_BUCKET_NAME"),
        region="cn-beijing",
    )

    with open(output_path, "rb") as f:
        file_content = f.read()

    file_key = storage.upload_file(
        file_content=file_content,
        file_name=output_docx_name,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    file_url = storage.generate_presigned_url(
        key=file_key,
        expire_time=86400
    )

    replace_report = _build_replace_report(
        total_items=len(cn_to_en),
        replaced_xml_blocks=total_replaced_blocks,
        matched_keys=matched_keys,
        key_to_original=key_to_original,
        failed_xml_files=failed_xml_files,
        residue_snippets=residue_snippets,
        output_url=file_url,
    )

    # 清理临时文件
    for path in [original_path, output_path]:
        try:
            os.remove(path)
        except Exception:
            pass

    return GenerateDocxOutput(
        output_en_docx=File(url=file_url, file_type="document"),
        docx_replace_report=replace_report,
    )
