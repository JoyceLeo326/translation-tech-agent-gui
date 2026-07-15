# C组 DOCX 文档翻译工作流交付说明

本目录为 C 组资料整理后的交付包，来源于 `workflow_af374b46.zip` 与 `工作日志.docx`。

## 目录结构

| 路径 | 说明 |
|---|---|
| `source/` | C 组工作流源码，已排除 `.venv/` 虚拟环境和 `.codegraph/` 本地缓存 |
| `docs/` | 标准化交付文档、使用说明、接口说明、运行日志 |
| `source_materials/` | 原始工作日志 docx 备份 |
| `manifest.json` | 本次整理的来源、排除项和文件清单 |

## 交付重点

- 工作流编号：C
- 业务方向：DOCX 文档汉译英翻译通道
- 主流程：中文 DOCX 生成三列对照 Excel，人工审核后回填生成英文 DOCX
- 编排框架：LangGraph 1.0
- 核心语言：Python 3.12
- 依赖管理：uv（`pyproject.toml` + `uv.lock`）

## 注意事项

支路 2 生成英文 DOCX 时必须同时提供 `review_excel` 和原始 `file_docx`。当前源码已移除样例 URL 兜底逻辑，缺少原始 DOCX 时会直接报错，避免误用样例文件。
