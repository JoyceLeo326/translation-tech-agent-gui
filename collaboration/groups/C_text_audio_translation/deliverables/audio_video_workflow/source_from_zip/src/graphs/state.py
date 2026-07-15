"""
工作流B - 音视频翻译通道 状态定义
"""
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 全局状态定义 ====================
class GlobalState(BaseModel):
    """全局状态定义"""
    # 模式判断（系统自动识别）
    run_mode: Optional[Literal["预处理・生成待审校Excel", "回填・生成成品音视频"]] = Field(
        None, description="运行模式（系统自动识别）"
    )
    
    # 模式1数据
    media_file: Optional[File] = Field(None, description="原始音视频文件(模式1)")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL(用于模式2复用)")
    asr_result: List[Dict[str, Any]] = Field(default=[], description="ASR识别结果")
    table_data: List[Dict[str, Any]] = Field(default=[], description="构造的表格数据")
    excel_url: Optional[str] = Field(None, description="生成的Excel文件URL")
    
    # 模式2数据
    finalized_excel: Optional[File] = Field(None, description="定稿Excel文件(模式2)")
    validated_data: List[Dict[str, Any]] = Field(default=[], description="校验后的有效数据")
    tts_audio_urls: List[str] = Field(default=[], description="TTS生成的音频URL列表(完整数组,按Excel顺序)")
    expected_audio_count: int = Field(default=0, description="Excel人工审核列有效句子行数(供校验TTS数量)")
    final_media_url: Optional[str] = Field(None, description="最终成品音视频URL")
    qr_code_url: Optional[str] = Field(None, description="二维码图片URL(扫码跳转播放页)")
    # ⭐ 修复:code=4036 配额耗尽降级时,把降级信息透传,让用户在最终消息里看到
    quota_exhausted: bool = Field(default=False, description="TTS月度配额是否已耗尽(code=4036)")
    tts_failed_segment_ids: List[str] = Field(default=[], description="TTS合成失败的 segment_id 列表(降级时填充)")
    tts_success_count: int = Field(default=0, description="TTS成功合成的批次数")
    tts_total_count: int = Field(default=0, description="TTS合成总批次数")
    tts_error_message: Optional[str] = Field(default=None, description="TTS降级错误信息(用户可见)")
    # ⭐ 本版本新增:每段独立音频 URL(一句一个),从 batch_tts_node 透传到 end_mode2_node,再到 GraphOutput
    # LangGraph 自动从 NodeOutput 合并到 GlobalState,所以必须在 GlobalState 中显式声明
    segment_audio_urls: List[str] = Field(default=[], description="每段独立 TTS 音频 URL 列表(一句一个文件,按 orig_idx 排序)")
    # ⭐ 本版本新增:模式二结束时自动生成的4列Excel输出URL(音频文字/机器译文/人工审核/音频下载地址)
    excel_output_url: Optional[str] = Field(None, description="模式二输出Excel文件URL(四列表格)")


# ==================== 图输入输出定义 ====================
class GraphInput(BaseModel):
    """工作流输入参数（智能模式识别）"""
    # 输入文件（系统自动判断运行模式）
    media_file: Optional[File] = Field(None, description="原始音视频文件（触发模式1）")
    finalized_excel: Optional[File] = Field(None, description="定稿Excel文件（触发模式2，需要提供original_audio_url）")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL（模式2专用：复用模式一生成的音频）")
    run_mode: Optional[Literal["预处理・生成待审校Excel", "回填・生成成品音视频"]] = Field(
        None, description="运行模式（可选，系统自动判断）"
    )


class GraphOutput(BaseModel):
    """工作流输出"""
    excel_url: Optional[str] = Field(None, description="生成的待审校Excel文件URL(模式1)")
    final_media_url: Optional[str] = Field(None, description="成品音视频URL(模式2)")
    qr_code_url: Optional[str] = Field(None, description="音频播放二维码图片URL(模式2)")
    excel_output_url: Optional[str] = Field(None, description="模式二输出Excel文件URL(四列表格:音频文字/机器译文/人工审核/音频下载地址)")
    message: str = Field(..., description="输出提示消息")
    # ⭐ 本版本新增:每段独立音频 URL(一句一个文件),用户可单独下载每段
    # 与 final_media_url(合并) 区别:final_media_url 是合并给二维码的,segment_audio_urls 是给用户"一句一个"下载的
    segment_audio_urls: List[str] = Field(default=[], description="每段独立 TTS 音频 URL 列表(一句一个文件,按 orig_idx 排序)")


# ==================== 条件分支节点 ====================
class ModeCheckInput(BaseModel):
    """模式判断节点输入"""
    run_mode: Literal["预处理・生成待审校Excel", "回填・生成成品音视频"] = Field(
        ..., description="运行模式"
    )


class AutoModeJudgeInput(BaseModel):
    """智能模式判断节点输入"""
    media_file: Optional[File] = Field(None, description="上传的音频文件")
    finalized_excel: Optional[File] = Field(None, description="上传的校对完成Excel文件")
    original_audio_url: Optional[str] = Field(None, description="系统中留存的上一次上传的原始音频URL")


class AutoModeJudgeOutput(BaseModel):
    """智能模式判断节点输出"""
    run_mode: str = Field(..., description="自动检测的运行模式")
    media_file: Optional[File] = Field(None, description="音频文件（模式一：新上传；模式二：复用原始）")
    finalized_excel: Optional[File] = Field(None, description="校对完成的Excel文件")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL，用于模式二复用")
    message: str = Field(..., description="判断结果提示消息")


# ==================== 模式1节点定义 ====================
class ASRInput(BaseModel):
    """ASR语音识别节点输入"""
    media_file: Optional[File] = Field(None, description="原始音视频文件")


class ASROutput(BaseModel):
    """ASR语音识别节点输出"""
    asr_result: List[Dict[str, Any]] = Field(..., description="ASR识别结果数组")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL,用于模式二复用")


class DataTableConstructInput(BaseModel):
    """数据构造节点输入"""
    asr_result: List[Dict[str, Any]] = Field(..., description="ASR识别结果")


class DataTableConstructOutput(BaseModel):
    """数据构造节点输出"""
    table_data: List[Dict[str, Any]] = Field(..., description="构造的表格数据")


class TranslationInput(BaseModel):
    """单条翻译节点输入"""
    chinese_text: str = Field(..., description="中文原文")
    segment_id: str = Field(..., description="片段ID")
    # 修复:TPM03 V2 长度控制 - 原句时长(毫秒),用于控制译文长度
    original_duration_ms: int = Field(default=0, description="原句时长(毫秒),用于控制译文长度适配原句时长")


class TranslationOutput(BaseModel):
    """单条翻译节点输出"""
    english_text: str = Field(..., description="英文译文")
    segment_id: str = Field(..., description="片段ID")


class TranslationBatchInput(BaseModel):
    """批量翻译节点输入"""
    table_data: List[Dict[str, Any]] = Field(..., description="待翻译的表格数据")


class TranslationBatchOutput(BaseModel):
    """批量翻译节点输出"""
    table_data: List[Dict[str, Any]] = Field(..., description="翻译后的表格数据")


class ExcelGenerateInput(BaseModel):
    """Excel生成节点输入"""
    table_data: List[Dict[str, Any]] = Field(..., description="表格数据")


class ExcelGenerateOutput(BaseModel):
    """Excel生成节点输出"""
    excel_url: str = Field(..., description="Excel文件URL")


class ExcelDataFillInput(BaseModel):
    """Excel数据填充验证节点输入"""
    excel_url: str = Field(..., description="Excel文件URL")


class ExcelDataFillOutput(BaseModel):
    """Excel数据填充验证节点输出"""
    excel_url: str = Field(..., description="验证后的Excel文件URL")


# ==================== 模式2节点定义 ====================
class ExcelReadInput(BaseModel):
    """Excel读取节点输入"""
    finalized_excel: Optional[File] = Field(None, description="定稿Excel文件")


class ExcelReadOutput(BaseModel):
    """Excel读取节点输出"""
    table_data: List[Dict[str, Any]] = Field(..., description="读取的表格数据")


class DataValidateInput(BaseModel):
    """数据校验节点输入"""
    table_data: List[Dict[str, Any]] = Field(..., description="读取的表格数据")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL（从模式一复用）")


class DataValidateOutput(BaseModel):
    """数据校验节点输出"""
    validated_data: List[Dict[str, Any]] = Field(..., description="校验后的有效数据")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL（传递给后续节点）")
    expected_audio_count: int = Field(default=0, description="Excel人工审核列句子行数(供后续节点校验音频数量)")


class BatchTTSInput(BaseModel):
    """批量TTS节点输入"""
    validated_data: List[Dict[str, Any]] = Field(default=[], description="校验后的有效数据")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL（从模式一复用）")


class TTSInput(BaseModel):
    """TTS语音合成节点输入"""
    english_text: str = Field(..., description="英文文本")
    segment_id: str = Field(..., description="片段ID")


class TTSOutput(BaseModel):
    """TTS语音合成节点输出"""
    audio_url: str = Field(..., description="生成的音频URL")
    segment_id: str = Field(..., description="片段ID")


class TTSBatchOutput(BaseModel):
    """批量TTS节点输出
    ⭐ 修复:code=4036 月度配额耗尽时不再整体崩溃,采用"部分降级"返回:
    - tts_audio_urls: 成功合成的所有批次拼接后的音频URL(0或1个,1=有部分成功,0=全部失败)
    - tts_failed_segment_ids: 失败的 segment_id 列表(供用户/前端参考)
    - quota_exhausted: True 表示 TTS 月度配额已耗尽(用户需升级套餐或等下月重置)
    - tts_error_message: 降级场景下的错误详情
    """
    validated_data: List[Dict[str, Any]] = Field(..., description="校验后的数据")
    tts_audio_urls: List[str] = Field(default=[], description="TTS音频URL列表(降级时可能为空)")
    original_audio_url: Optional[str] = Field(None, description="原始音频URL（从模式一复用）")
    tts_failed_segment_ids: List[str] = Field(default=[], description="TTS合成失败的 segment_id 列表(降级时填充)")
    quota_exhausted: bool = Field(default=False, description="TTS月度配额是否已耗尽(code=4036)")
    tts_success_count: int = Field(default=0, description="TTS成功合成的批次数")
    tts_total_count: int = Field(default=0, description="TTS合成总批次数")
    tts_error_message: Optional[str] = Field(default=None, description="TTS合成错误信息(降级时填充)")
    # ⭐ 本版本新增:每段独立音频 URL(一句一个),从 batch_tts_node 合并到 GlobalState
    # 长度=N(Excel 行数),按 orig_idx 排序(0,1,2...,N-1)
    segment_audio_urls: List[str] = Field(default=[], description="每段独立 TTS 音频 URL 列表(一句一个文件,按 orig_idx 排序)")


class MediaCompileInput(BaseModel):
    """音视频混音节点输入"""
    tts_audio_urls: List[str] = Field(default=[], description="TTS音频URL列表")
    original_audio_url: Optional[str] = Field(default=None, description="原始音频URL(模式二复用)")


class MediaCompileOutput(BaseModel):
    """音视频混音节点输出"""
    final_media_url: str = Field(..., description="成品音视频URL")
    tts_audio_urls: List[str] = Field(default=[], description="TTS音频URL列表(用于二维码生成)")


# ==================== 结束节点定义 ====================
class EndMode1Input(BaseModel):
    """模式1结束节点输入"""
    excel_url: str = Field(..., description="Excel文件URL")


class EndMode1Output(BaseModel):
    """模式1结束节点输出"""
    message: str = Field(..., description="提示消息")


class EndMode2Input(BaseModel):
    """模式2结束节点输入"""
    final_media_url: str = Field(..., description="成品音视频URL")
    tts_audio_urls: List[str] = Field(default=[], description="TTS音频URL列表")
    expected_audio_count: int = Field(default=0, description="Excel人工审核列句子行数")
    # ⭐ 修复:code=4036 配额耗尽降级时,把降级信息透传到结束节点,让用户在最终消息里看到
    quota_exhausted: bool = Field(default=False, description="TTS月度配额是否已耗尽")
    tts_failed_segment_ids: List[str] = Field(default=[], description="TTS合成失败的 segment_id 列表")
    tts_success_count: int = Field(default=0, description="TTS合成成功的批次数")
    tts_total_count: int = Field(default=0, description="TTS合成总批次数")
    tts_error_message: Optional[str] = Field(default=None, description="TTS降级错误信息")
    # ⭐ 本版本新增:每段独立音频 URL(一句一个),从 batch_tts_node 透传过来,让用户能单独下载每段
    segment_audio_urls: List[str] = Field(default=[], description="每段独立 TTS 音频 URL 列表(一句一个文件,按 orig_idx 排序)")


class EndMode2Output(BaseModel):
    """模式2结束节点输出"""
    message: str = Field(..., description="提示消息")
    # ⭐ 本版本新增:每段独立音频 URL(一句一个),透传到 GraphOutput.segment_audio_urls
    segment_audio_urls: List[str] = Field(default=[], description="每段独立 TTS 音频 URL 列表(一句一个文件,按 orig_idx 排序)")


class QRCodeGenerationInput(BaseModel):
    """二维码生成节点输入"""
    final_media_url: Optional[str] = Field(None, description="成品音视频URL")
    tts_audio_urls: List[str] = Field(default=[], description="TTS音频URL列表(完整数组,不截取)")
    expected_audio_count: int = Field(default=0, description="Excel人工审核列句子行数(用于校验)")


class QRCodeGenerationOutput(BaseModel):
    """二维码生成节点输出"""
    qr_code_url: str = Field(..., description="二维码图片URL")
    qr_content: str = Field(..., description="二维码编码的播放页面完整地址(含audioList参数)")
    audio_list_count: int = Field(..., description="二维码中编码的音频URL数量")
    expected_audio_count: int = Field(..., description="Excel人工审核列句子行数")


# ==================== Excel输出生成节点（模式二新增） ====================
class ExcelOutputGenerateInput(BaseModel):
    """模式二输出Excel生成节点输入"""
    table_data: List[Dict[str, Any]] = Field(..., description="原始Excel表格数据(含音频文字/机器译文/人工审核三列)")
    segment_audio_urls: List[str] = Field(default=[], description="每段独立TTS音频URL列表(按orig_idx排序,一句一个文件)")


class ExcelOutputGenerateOutput(BaseModel):
    """模式二输出Excel生成节点输出"""
    excel_output_url: str = Field(..., description="四列输出Excel文件URL(音频文字/机器译文/人工审核/音频下载地址)")