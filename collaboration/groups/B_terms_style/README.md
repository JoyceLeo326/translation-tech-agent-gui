# B 组：术语库与儿童文学风格控制

## 负责范围

- 从中国文化相关图书、文献和网络资料中抽取文化术语。
- 整理中英对照术语库，供全项目统一使用。
- 为儿童文学文本翻译设计风格控制提示词。
- 用大模型交叉验证译文风格，降低成人化、生硬化表达。

## 推荐提交位置

- 术语库 Excel 与机器可读导出：`terminology/`。
- 参考资料和来源说明：`references/`。
- 风格控制提示词：`prompts/`。
- 稳定交付压缩包、PRD、验收记录：`deliverables/`。

## 与整合区的关系

成熟术语库需要复制到 `../../shared/terminology/`，供 A/C 组和最终 GUI 调用。

## 当前已归档材料

- `terminology/中华文化术语对照表.xlsx`：已移除本机外链公式的可移植正式术语库。
- `terminology/zhonghua_culture_terms.normalized.csv`：从原始 Excel 生成的规范化 CSV。
- `terminology/zhonghua_culture_terms.normalized.json`：从原始 Excel 生成的规范化 JSON。
- `references/翻译资源编写-中国文化知识百科（图文有声版）.pdf`：B 组自编术语来源 PDF。
- `references/翻译资源编写-中国文化知识百科（图文有声版）.extracted.txt`：PDF 文本抽取结果，用于检索和核验。
- `deliverables/workflow_translation_draft_9476/`：首次交付的 Coze 工作流归档。
- `deliverables/workflow_translation_draft_3045/`：2026-07-17 二次交付；后续整合优先使用。
- `deliverables/prd/`：B 组新版工作流 PRD、抽取版 Markdown 和实际运行截图。
- `deliverables/notes/`：聊天截图、验收反馈和需 B 组补充事项。
