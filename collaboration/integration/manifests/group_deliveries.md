# ABC 组交付清单

更新时间：2026-07-17

## A 组：图文翻译与回填

| 类型 | 路径 | 状态 | 备注 |
| --- | --- | --- | --- |
| 交付压缩包 | `collaboration/groups/A_image_translation/deliverables/archives/pic_trans_replace_fixed_20260715.zip` | 已归档 | 图文翻译修正版 |
| 需求说明 | `collaboration/groups/A_image_translation/deliverables/notes/A组整改需求_20260715.md` | 已归档 | 整改需求 |
| 独立复核记录 | `collaboration/groups/A_image_translation/deliverables/notes/A组独立复核记录_20260717.md` | 已归档 | 复核结果与需 A 组补充事项 |
| 展开材料 | `collaboration/groups/A_image_translation/deliverables/extracted_20260715/` | 已归档 | 脚本、翻译清单、预览图、最终 DOCX |

## B 组：术语库与儿童文学风格控制

| 类型 | 路径 | 状态 | 备注 |
| --- | --- | --- | --- |
| 术语库 | `collaboration/groups/B_terms_style/terminology/中华文化术语对照表.xlsx` | 已归档 | B 组原始 Excel |
| 术语库机器可读版 | `collaboration/groups/B_terms_style/terminology/zhonghua_culture_terms.normalized.csv` | 已生成 | 同步 JSON 版本 |
| 共享术语库 | `collaboration/shared/terminology/` | 已同步 | 供 A/C 组和总整合调用 |
| 来源 PDF | `collaboration/groups/B_terms_style/references/翻译资源编写-中国文化知识百科（图文有声版）.pdf` | 已归档 | B 组自编知识库来源 |
| PRD | `collaboration/groups/B_terms_style/deliverables/prd/B组工作流prd文档.docx` | 已归档 | 已抽取 Markdown |
| Coze 工作流压缩包 | `collaboration/groups/B_terms_style/deliverables/workflow_translation_draft_9476/archives/Workflow-Translation-draft-9476.zip` | 已归档 | 原始导出包 |
| Coze 工作流展开 | `collaboration/groups/B_terms_style/deliverables/workflow_translation_draft_9476/source_from_zip/` | 已归档 | 已生成 `workflow_summary.json` |
| 风格提示词 | `collaboration/groups/B_terms_style/prompts/workflow_b_prompts_from_yaml.md` | 已抽取 | 从实际 Coze YAML 提取，便于审阅 |
| 验收反馈 | `collaboration/groups/B_terms_style/deliverables/notes/B组交付物验收反馈_20260715.md` | 已归档 | 含需 B 组补充事项 |

## C 组：文本、DOCX 与音频翻译

| 类型 | 路径 | 状态 | 备注 |
| --- | --- | --- | --- |
| DOCX 交付压缩包 | `collaboration/groups/C_text_audio_translation/deliverables/docx_translation/workflow_c_docx_translation_20260715.zip` | 已归档 | C 组 DOCX 翻译通道 |
| DOCX 源码展开 | `collaboration/groups/C_text_audio_translation/deliverables/docx_translation/source_from_zip/` | 已归档 | C 组 DOCX 源码、文档和源材料 |
| 文字/DOCX 二次交付 | `collaboration/groups/C_text_audio_translation/deliverables/docx_translation/revised_20260717/` | 已整理 | 含修正后源码、5 组测试样例、截图和日志；整合优先使用 |
| 音视频交付压缩包 | `collaboration/groups/C_text_audio_translation/deliverables/audio_video_workflow/音视频翻译工作流.zip` | 已归档 | 按任务归入 C 组音视频通道 |
| 音视频源码展开 | `collaboration/groups/C_text_audio_translation/deliverables/audio_video_workflow/source_from_zip/` | 已归档 | 供后续整合分析 |
| 交付日志 | `collaboration/groups/C_text_audio_translation/deliverables/audio_video_workflow/工作流B — 音视频翻译通道 · 标准化项目交付日志.docx` | 已归档 | 原始日志 |
| 音视频二次交付 | `collaboration/groups/C_text_audio_translation/deliverables/audio_video_workflow/revised_20260717/` | 已整理 | 含新版源码、补充测试音频、模式二输出音频、四列表格、二维码和截图 |
| 二次验收反馈 | `collaboration/groups/C_text_audio_translation/deliverables/notes/C组二次交付验收反馈_20260717.md` | 已归档 | 平台侧仍需确认文字流画布同步、API Token 安全交付、运行日志追溯 |

## 总整合待办

- 统一 Excel 字段规范。
- 将 B 组共享术语库接入总智能体、GUI 或 A/C 组适配器。
- 为 A/C 组成果编写适配器。
- 在主 GUI 中增加分通道入口和整合状态面板。
