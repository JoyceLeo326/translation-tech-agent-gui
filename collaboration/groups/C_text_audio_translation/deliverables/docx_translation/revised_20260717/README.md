# C组文字/DOCX工作流二次交付整理版

整理时间：2026-07-17

本目录来自 C 组二次提交的 `文字工作流.zip`，已做整合处理：

- `source_from_zip/`：从 `DOCXFan_Yi_Gong_Zuo_Liu_e0f1eb1d.zip` 解出的源码与 assets，并已补回整合所需修复。
- `test_cases/`：C 组提供的 5 组 DOCX/Excel/输出 DOCX 测试样例。
- `screenshots/`：C 组提供的平台截图。
- `logs/`：C 组提供的 Word 工作日志、文字解释日志和链接材料。

已由整合侧修复并入库：

- 支路二缺少 `file_docx` 时直接报错，不再使用样例 URL 兜底。
- 支路二输出 `docx_replace_report`，用于核对替换覆盖、未命中项和中文残留。
- Excel 列识别改为显式别名匹配，关键列缺失时直接报错。
- LLM 调用按配置尝试传入 `thinking`，SDK 不支持时自动回退。
- 文档中支路二 `file_docx` 已统一改为必填。

