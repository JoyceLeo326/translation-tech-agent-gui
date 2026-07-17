# B 组交付物归档

## 目录

| 路径 | 内容 |
| --- | --- |
| `workflow_translation_draft_9476/archives/Workflow-Translation-draft-9476.zip` | B 组提交的 Coze 工作流原始压缩包。 |
| `workflow_translation_draft_9476/source_from_zip/` | 原始工作流展开目录，包含 `MANIFEST.yml` 和 `workflow/Translation-draft.yaml`。 |
| `workflow_translation_draft_9476/workflow_summary.json` | 从工作流 YAML 抽取的节点、边、模型、超时和重试配置摘要。 |
| `workflow_translation_draft_3045/` | 2026-07-17 二次交付，含新版原始压缩包、展开 YAML、工作流摘要和结构/代码验证记录；后续整合优先使用。 |
| `prd/B组工作流prd文档.docx` | B 组提交的原始 PRD。 |
| `prd/B组工作流prd文档.md` | 从 PRD DOCX 抽取的 Markdown 版本，便于检索。 |
| `prd/evidence_20260717/` | 从新版 PRD 中抽取的 3 张实际运行截图。 |
| `revisions/20260717/source_from_b/` | B 组原始修订术语表；保留外链公式，仅用于审计。 |
| `B_group_source_materials_checksums.json` | 原始材料和关键展开文件的 SHA-256 校验清单。 |
| `B_group_acceptance_snapshot.json` | 本次完整性检查快照。 |
| `notes/` | 聊天截图与 B 组需补充/返工反馈。 |

当前二次验收结论见 `notes/B组二次交付复核反馈_20260717.md`。除 Coze 最新修改尚需 B 组发布外，其余可处理问题已由整合侧闭环。

## 整合口径

聊天截图中老师建议采用“用智能体整合所有用到的工作流”的方案。本目录按该口径保留 B 组 Coze 工作流，并将可复用的术语库同步到 `../../shared/terminology/`，供总智能体、A/C 组适配器或 GUI 后续调用。
