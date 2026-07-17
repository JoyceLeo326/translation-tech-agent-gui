# B 组 Coze 工作流二次交付

## 内容

| 路径 | 说明 |
| --- | --- |
| `archives/Workflow-Translation-draft-3045.zip` | B 组 2026-07-17 提交的原始导出包。 |
| `source_from_zip/Workflow-Translation-draft-3045/` | 原始导出包展开内容。 |
| `workflow_summary.json` | 节点、模型、知识库、插件、超时和错误处理配置摘要。 |
| `workflow_validation.json` | 图连通性、引用完整性和 3 个代码节点入参执行验证。 |

## 复核结果

- 工作流 ID：`7661678571702747178`。
- 节点/边：18/28。
- 知识库：`7662977203206176822`（`中国文化术语-改`）。
- 3 个代码节点已统一使用 `args.get('params', {})`，本地样例执行均通过。
- 当前整合优先使用本目录，而不是首次交付的 `workflow_translation_draft_9476/`。

Coze 平台仍需 B 组发布当前修改，详见 `../notes/B组二次交付复核反馈_20260717.md`。
