"""
DOCX分层分句分批翻译+审核回填替换DOCX工具 - 状态定义
两条独立支路：支路1 DOCX→Excel，支路2 Excel→DOCX
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from utils.file.file import File


# ============================================================
# 全局状态（工作流运行时内部流转用）
# ============================================================
class GlobalState(BaseModel):
    """工作流全局状态"""
    # 支路1输入
    file_docx: Optional[File] = Field(default=None, description="支路1输入：待翻译的DOCX文档")
    # 支路2输入
    review_excel: Optional[File] = Field(default=None, description="支路2输入：人工审核后的Excel文件")

    # 支路1 中间状态
    parsed_text: Optional[str] = Field(default=None, description="DOCX解析后的完整分层文本")
    text_batch_list: Optional[List[str]] = Field(default=None, description="分片后的文本列表")
    batch_count: Optional[int] = Field(default=None, description="总分片数")
    cn_text_parts: List[str] = Field(default=[], description="各分片的中文翻译结果")
    en_text_parts: List[str] = Field(default=[], description="各分片的英文翻译结果")
    cn_raw: Optional[str] = Field(default=None, description="合并后的完整中文文本")
    en_raw: Optional[str] = Field(default=None, description="合并后的完整英文文本")
    origin_excel: Optional[File] = Field(default=None, description="支路1输出：分层分句翻译对照Excel")

    # 支路2 中间状态
    final_full_en: Optional[str] = Field(default=None, description="支路2：定稿英文文本（含层级标记）")
    output_en_docx: Optional[File] = Field(default=None, description="支路2输出：替换完成的英文DOCX文档")
    docx_replace_report: Optional[str] = Field(default=None, description="支路2输出：DOCX替换覆盖报告")


# ============================================================
# 工作流输入/输出
# ============================================================
class GraphInput(BaseModel):
    """工作流输入 - 两条支路通过不同输入字段区分"""
    file_docx: Optional[File] = Field(
        default=None,
        description="支路1：上传待翻译的DOCX文档"
    )
    review_excel: Optional[File] = Field(
        default=None,
        description="支路2：上传人工审核翻译后的Excel文件"
    )


class GraphOutput(BaseModel):
    """工作流输出"""
    origin_excel: Optional[File] = Field(
        default=None,
        description="支路1输出：分层分句翻译对照Excel（含中文原文、机器英文译文、人工审核空白列）"
    )
    output_en_docx: Optional[File] = Field(
        default=None,
        description="支路2输出：替换完成的纯英文DOCX文档（保留原层级）"
    )
    docx_replace_report: Optional[str] = Field(
        default=None,
        description="支路2输出：DOCX替换覆盖报告（替换数、未命中项、中文残留等）"
    )


# ============================================================
# 路由节点 出入参
# ============================================================
class RouterInput(BaseModel):
    """路由节点输入"""
    file_docx: Optional[File] = Field(default=None, description="支路1输入")
    review_excel: Optional[File] = Field(default=None, description="支路2输入")


class RouterOutput(BaseModel):
    """路由节点输出"""
    branch: str = Field(..., description="路由结果：branch1 / branch2 / end")


# ============================================================
# 支路1 节点出入参
# ============================================================
class DocxParseInput(BaseModel):
    """DOCX解析节点输入"""
    file_docx: Optional[File] = Field(default=None, description="待解析的DOCX文件")


class DocxParseOutput(BaseModel):
    """DOCX解析节点输出"""
    parsed_text: str = Field(..., description="带层级标记的完整文本")


class SplitInput(BaseModel):
    """分片处理节点输入"""
    parsed_text: str = Field(..., description="带层级标记的完整文本")


class SplitOutput(BaseModel):
    """分片处理节点输出"""
    text_batch_list: List[str] = Field(..., description="分片后的文本列表")
    batch_count: int = Field(..., description="总分片数")


class TranslateBatchInput(BaseModel):
    """批量翻译节点输入（在主图中调用子图）"""
    text_batch_list: List[str] = Field(..., description="待翻译的分片列表")
    batch_count: int = Field(..., description="总分片数")


class TranslateBatchOutput(BaseModel):
    """批量翻译节点输出"""
    cn_text_parts: List[str] = Field(..., description="各分片中文翻译结果")
    en_text_parts: List[str] = Field(..., description="各分片英文翻译结果")


class MergeInput(BaseModel):
    """分批合并节点输入"""
    cn_text_parts: List[str] = Field(..., description="各分片中文翻译结果")
    en_text_parts: List[str] = Field(..., description="各分片英文翻译结果")


class MergeOutput(BaseModel):
    """分批合并节点输出"""
    cn_raw: str = Field(..., description="合并后的完整中文文本")
    en_raw: str = Field(..., description="合并后的完整英文文本")


class GenerateExcelInput(BaseModel):
    """生成Excel节点输入"""
    cn_raw: str = Field(..., description="完整中文文本")
    en_raw: str = Field(..., description="完整英文文本")


class GenerateExcelOutput(BaseModel):
    """生成Excel节点输出"""
    origin_excel: File = Field(..., description="生成的对照Excel文件")


# ============================================================
# 支路2 节点出入参
# ============================================================
class ReadExcelInput(BaseModel):
    """读取Excel节点输入"""
    review_excel: Optional[File] = Field(default=None, description="人工审核后的Excel文件")


class ReadExcelOutput(BaseModel):
    """读取Excel节点输出"""
    final_full_en: str = Field(..., description="拼接后的完整定稿英文文本")
    cn_en_pairs: List[tuple] = Field(default=[], description="中文→英文对照对列表，每项为(chinese, english)")


class GenerateDocxInput(BaseModel):
    """生成DOCX节点输入"""
    final_full_en: str = Field(..., description="定稿英文文本")
    cn_en_pairs: List[tuple] = Field(default=[], description="中文→英文对照对列表")
    file_docx: Optional[File] = Field(default=None, description="原始DOCX文件，用于回填替换")


class GenerateDocxOutput(BaseModel):
    """生成DOCX节点输出"""
    output_en_docx: File = Field(..., description="生成的英文DOCX文件")
    docx_replace_report: Optional[str] = Field(default=None, description="DOCX替换覆盖报告")


# ============================================================
# 循环子图 出入参
# ============================================================
class TranslateLoopState(BaseModel):
    """翻译循环子图内部状态"""
    text_batch_list: List[str] = Field(default=[], description="待翻译的分片列表")
    current_index: int = Field(default=0, description="当前处理的分片索引")
    cn_text_parts: List[str] = Field(default=[], description="已翻译的中文分片")
    en_text_parts: List[str] = Field(default=[], description="已翻译的英文分片")
    total_batches: int = Field(default=0, description="总分片数")


class TranslateLoopInput(BaseModel):
    """翻译循环子图输入"""
    text_batch_list: List[str] = Field(..., description="待翻译的分片列表")
    total_batches: int = Field(..., description="总分片数")


class TranslateLoopOutput(BaseModel):
    """翻译循环子图输出"""
    cn_text_parts: List[str] = Field(..., description="各分片中文翻译结果")
    en_text_parts: List[str] = Field(..., description="各分片英文翻译结果")


class TranslateOneBatchInput(BaseModel):
    """翻译单个分片的输入"""
    text_batch_list: List[str] = Field(..., description="待翻译的分片列表")
    current_index: int = Field(..., description="当前处理的分片索引")
    cn_text_parts: List[str] = Field(default=[], description="已翻译的中文分片")
    en_text_parts: List[str] = Field(default=[], description="已翻译的英文分片")
    total_batches: int = Field(..., description="总分片数")


class TranslateOneBatchOutput(BaseModel):
    """翻译单个分片的输出"""
    text_batch_list: List[str] = Field(..., description="待翻译的分片列表")
    current_index: int = Field(..., description="更新后的分片索引")
    cn_text_parts: List[str] = Field(..., description="更新后的中文分片列表")
    en_text_parts: List[str] = Field(..., description="更新后的英文分片列表")
    total_batches: int = Field(..., description="总分片数")


class CheckLoopInput(BaseModel):
    """循环条件检查输入"""
    current_index: int = Field(..., description="当前分片索引")
    total_batches: int = Field(..., description="总分片数")


class CheckLoopOutput(BaseModel):
    """循环条件检查输出"""
    decision: str = Field(..., description="continue 或 done")
