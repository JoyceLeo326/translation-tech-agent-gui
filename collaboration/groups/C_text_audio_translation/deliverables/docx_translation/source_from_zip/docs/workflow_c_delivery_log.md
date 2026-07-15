# 工作流C — DOCX文档翻译通道 · 标准化项目交付日志

**交付日期**：2026-07-15  
**工作流编号**：工作流 C（DOCX 文档汉译英翻译通道）  
**平台**：扣子（Coze Coding）  
**编排框架**：LangGraph 1.0  
**核心语言**：Python 3.12  
**依赖管理**：uv（pyproject.toml + uv.lock）  
**维护人**：材料未注明  
**整理来源**：`工作日志.docx`、`workflow_af374b46.zip`

---

## 1. 基础信息

| 项目 | 内容 |
|---|---|
| 项目名称 | 工作流C — DOCX文档翻译通道 |
| 工作流编号 | C |
| 更新日期 | 2026-07-15 |
| 运行平台 | Coze Coding（LangGraph 1.0 编排引擎） |
| 核心语言 | Python 3.12 |
| 依赖管理 | uv |
| 主要输入 | 中文 DOCX、人工审核后的 Excel |
| 主要输出 | 三列翻译对照 Excel、英文 DOCX |

## 2. 项目目的

### 2.1 业务定位

工作流 C 是一套面向 DOCX 文档的双支路自动翻译工作流，用于将中文 DOCX 拆解成可人工审核的中英对照 Excel，并在审核完成后回填生成英文 DOCX。它重点解决长文档翻译中的行号对齐、表格文本遗漏、断行合并、样式保留和文件名英文化问题。

### 2.2 核心职责

| 维度 | 内容 |
|---|---|
| 输入侧 | 接收待翻译 DOCX，或接收人工审核完成的 Excel |
| 处理侧 | 文档解析、分句分片、逐行翻译、Excel 生成、XML 级文本回填 |
| 输出侧 | 输出三列对照 Excel，或输出保留版式的英文 DOCX |
| 质量目标 | 中英文逐行对齐，表格文本不遗漏，图片/表格/字体/加粗/斜体等格式尽量保留 |

### 2.3 实现功能

1. 自动路由：根据输入文件判断执行 DOCX→Excel 支路，或 Excel→英文 DOCX 支路。
2. DOCX 解析：按文档 body 顺序遍历段落和表格，提取正文、标题和表格文本。
3. 分句处理：正文按中文句号、问号、感叹号拆分，并合并异常断行中文。
4. 逐行分片翻译：每片 1 行，添加 `[行号]` 前缀，降低 LLM 合并、漏译、错位风险。
5. 对照 Excel 生成：输出 `中文原文 / 机器英文译文 / 人工审核` 三列表格。
6. 审核 Excel 读取：优先读取人工审核列，空值时回退到机器英文译文列。
7. XML 级 DOCX 回填：直接修改 DOCX ZIP 内的 Word XML，将英文按 run 比例写回，保留原始 run 样式。
8. 文件名翻译：使用 LLM 将原始中文文件名翻译为英文，作为输出 DOCX 文件名。

### 2.4 双支路业务目标

| 支路 | 输入 | 处理 | 输出 | 业务目标 |
|---|---|---|---|---|
| 支路一（预处理） | 中文 DOCX | 解析 → 分句 → 分片 → 翻译 → 合并 → Excel | `origin_excel` | 生成可人工校对的中英对照表 |
| 支路二（回填） | 审核 Excel + 原始 DOCX | 读取审核结果 → 中文英文映射 → XML 替换 → 覆盖报告 | `output_en_docx` + `docx_replace_report` | 生成保留原版式的英文 DOCX，并返回替换覆盖信息 |

## 3. 交互开发记录

### 3.1 需求沟通阶段

| # | 沟通事项 | 决策结果 |
|---|---|---|
| 1 | 需要搭建中文 DOCX 到英文 DOCX 的自动化翻译流程 | 采用双支路设计：先产出审核 Excel，再回填生成英文 DOCX |
| 2 | 长文档翻译容易漏句、合并行、错位 | 每片 1 行并使用 `[行号]` 约束 LLM 输出 |
| 3 | 文档包含表格、图片、复杂格式 | 解析阶段覆盖段落和表格，回填阶段直接操作 XML 以保留样式 |
| 4 | 输出文件名需要英文化 | 增加文件名翻译配置与 LLM 调用 |

### 3.2 技术方案选择

- 编排框架：LangGraph 1.0 DAG 主图。
- 路由机制：`router_node` 根据 `review_excel` / `file_docx` 自动选择分支。
- 循环机制：`translate_loop_subgraph` 按分片循环调用 LLM。
- 文档处理：解析阶段使用 `python-docx` 读取文档结构，回填阶段使用 `zipfile` + Word XML 直接替换文本。
- 对齐机制：行号前缀 + 输出行号解析 + 缺失行回退填充。

### 3.3 核心功能迭代

| 序号 | 需求描述 | 实现方案 | 状态 |
|---|---|---|---|
| 1 | 双支路自动分流 | `router_node` 判断 `review_excel` 优先进入回填支路，否则根据 `file_docx` 进入预处理支路 | 完成 |
| 2 | DOCX 层级与表格解析 | `docx_parse_node` 顺序遍历 XML body 中段落与表格，提取标题、正文、表格文本 | 完成 |
| 3 | 防止 LLM 漏译/合并行 | `split_node` 每片 1 行，给每行增加全局行号 | 完成 |
| 4 | 分批翻译 | `translate_batch_node` 调用循环子图逐片翻译 | 完成 |
| 5 | 输出三列对照 Excel | `generate_excel_node` 使用 pandas/openpyxl 生成 Excel 并上传对象存储 | 完成 |
| 6 | 人工审核回填 | `read_excel_node` 提取中文原文与审核英文，人工审核为空时回退机器译文 | 完成 |
| 7 | 保留 DOCX 格式 | `generate_docx_node` 直接修改 Word XML 中 `<w:t>` 文本，保留 run 样式 | 完成 |
| 8 | 文件名英文化 | `filename_translate_cfg.json` + LLM 生成英文文件名 | 完成 |

### 3.4 关键问题与处理

| 问题 | 原因 | 处理方案 | 验证结果 |
|---|---|---|---|
| 表格内容遗漏 | 只读段落会跳过表格单元格 | 遍历 `document.xml` body 顺序，分别处理 `p` 与 `tbl` | 表格文本纳入翻译链路 |
| 翻译行错位 | LLM 可能合并多行或少输出行 | 每片 1 行 + `[行号]` 前缀 + 输出行号解析 | 中英文可按行号重建 |
| 长文档断行 | DOCX 中部分中文被拆成相邻短行 | 对未以句末标点结束的连续中文行做合并 | 减少碎片句 |
| 样式丢失 | `python-docx.save()` 可能重写结构 | 回填时直接修改 XML 文本节点 | 保留图片、表格、字体与 run 格式 |
| 人工审核列为空 | 审核流程可能只保留机器译文 | 读取 Excel 时人工审核优先，空值回退机器英文译文 | 可继续生成英文 DOCX |

## 4. 工作流执行动作

### 4.1 节点清单（主图 8 个节点 + 子图 1 个节点）

| 序号 | 节点 ID | 文件位置 | 类型 | 功能描述 |
|---|---|---|---|---|
| 1 | `router` | `src/graphs/nodes/router_node.py` | task | 判断输入参数，选择支路一、支路二或结束 |
| 2 | `docx_parse` | `src/graphs/nodes/docx_parse_node.py` | task | 解析 DOCX 段落和表格，生成分层分句文本 |
| 3 | `split` | `src/graphs/nodes/split_node.py` | task | 按 1 行/批分片，并添加 `[行号]` 前缀 |
| 4 | `translate_batch` | `src/graphs/nodes/translate_batch_node.py` | loopcond | 调用循环子图，逐片翻译 |
| 5 | `translate_one_batch` | `src/graphs/loop_graph.py` | agent | 调用 LLM 翻译单个分片，并按行号重建输出 |
| 6 | `merge` | `src/graphs/nodes/merge_node.py` | task | 合并全部中文和英文分片 |
| 7 | `generate_excel` | `src/graphs/nodes/generate_excel_node.py` | task | 生成三列对照 Excel 并上传对象存储 |
| 8 | `read_excel` | `src/graphs/nodes/read_excel_node.py` | task | 读取审核 Excel，生成中文到英文的对照映射 |
| 9 | `generate_docx` | `src/graphs/nodes/generate_docx_node.py` | task | XML 级替换 DOCX 文本并上传英文 DOCX |

### 4.2 支路一：DOCX → 对照 Excel

```text
router → docx_parse → split → translate_batch → merge → generate_excel → END
```

流程说明：
1. `router` 检测到上传 `file_docx`，进入支路一。
2. `docx_parse` 下载 DOCX，按 body 顺序提取段落和表格文本，正文按句号/问号/感叹号分句。
3. `split` 将每行文本拆成单独分片，并加全局行号。
4. `translate_batch` 调用循环子图，逐行翻译。
5. `merge` 合并所有中文和英文分片。
6. `generate_excel` 输出三列 Excel：中文原文、机器英文译文、人工审核。

### 4.3 支路二：审核 Excel → 英文 DOCX

```text
router → read_excel → generate_docx → END
```

流程说明：
1. `router` 检测到上传 `review_excel`，进入支路二。
2. `read_excel` 读取审核表，优先使用人工审核列，空值回退机器英文译文列。
3. `generate_docx` 根据中文→英文映射直接修改原始 DOCX 内的 XML 文本节点。
4. 输出英文 DOCX，文件名由原中文文件名翻译生成。

### 4.4 子图清单

| 子图名 | 文件位置 | 类型 | 功能 | 被调用节点 |
|---|---|---|---|---|
| `translate_loop_subgraph` | `src/graphs/loop_graph.py` | loopcond | 遍历分片列表，逐片调用 LLM 翻译 | `translate_batch` |

## 5. 变量规范

### 5.1 输入变量

| 变量名称 | 数据类型 | 是否必填 | 适用支路 | 字段说明 |
|---|---|---|---|---|
| `file_docx` | `File` | 条件必填 | 支路一 / 支路二 | 支路一为待翻译 DOCX；支路二为回填所需原始 DOCX |
| `review_excel` | `File` | 条件必填 | 支路二 | 人工审核后的 Excel，包含中文原文、机器英文译文、人工审核列 |

### 5.2 输出变量

| 变量名称 | 数据类型 | 所属支路 | 字段说明 |
|---|---|---|---|
| `origin_excel` | `File` | 支路一 | 三列翻译对照 Excel |
| `output_en_docx` | `File` | 支路二 | 替换完成的英文 DOCX |
| `docx_replace_report` | `str` | 支路二 | DOCX 替换覆盖报告（替换数、未命中项、中文残留片段等） |

### 5.3 业务变量 → 代码字段映射

| 业务变量 | 代码字段 |
|---|---|
| 待翻译 DOCX | `GraphInput.file_docx` |
| 审核 Excel | `GraphInput.review_excel` |
| 对照 Excel | `GraphOutput.origin_excel` |
| 英文 DOCX | `GraphOutput.output_en_docx` |

## 6. 依赖资源与配置清单

### 6.1 SDK 与工具调用

| 资源 | 使用节点 | 说明 |
|---|---|---|
| `coze_coding_dev_sdk.LLMClient` | `translate_one_batch`、`generate_docx` 文件名翻译 | 中文逐行翻译与文件名翻译 |
| `coze_coding_dev_sdk.s3.S3SyncStorage` | `generate_excel`、`generate_docx` | 上传 Excel / DOCX 并生成预签名 URL |
| `FileOps.save_to_local` | `docx_parse`、`read_excel` | 将上传文件保存到本地临时路径 |
| `python-docx` | `docx_parse` | 读取 DOCX 段落与表格 |
| `zipfile` + `ElementTree` | `generate_docx` | 直接修改 Word XML 文本节点 |
| `pandas` / `openpyxl` | `generate_excel`、`read_excel` | Excel 写入与读取 |
| `Jinja2` | LLM 节点 | 渲染提示词模板 |

### 6.2 大模型配置

| 配置文件 | 用途 | 关键配置 |
|---|---|---|
| `config/translate_llm_cfg.json` | 逐行中文到英文翻译 | `doubao-seed-2-0-lite-260215`，temperature 0.0，thinking disabled |
| `config/filename_translate_cfg.json` | 中文文件名翻译为英文 | `doubao-seed-2-0-lite-260215`，temperature 0.0，thinking disabled |

### 6.3 第三方依赖

核心依赖由 `pyproject.toml` 管理，包括：`langgraph`、`langchain`、`coze-coding-dev-sdk`、`coze-coding-utils`、`python-docx`、`openpyxl`、`pandas`、`Jinja2`、`boto3` 等。

## 7. 运行测试记录

### 7.1 材料记录中的测试结果

| 测试项 | 结果 | 说明 |
|---|---|---|
| 支路一 DOCX→Excel | 通过 | 生成 133 行对照 Excel，记录为 100% 英文覆盖、0 重复 |
| 支路二 Excel→DOCX | 通过 | 记录为 78 段全部替换为英文、0 中文残留、格式保留 |
| 表格文本解析 | 通过 | 表格单元格文本被纳入解析与翻译 |
| 文件名英文化 | 通过 | 原始中文文件名翻译为英文作为输出名 |

### 7.2 本次整理验证

| 验证项 | 结果 |
|---|---|
| 从 `workflow_af374b46.zip` 提取源码 | 已完成，排除 `.venv/` 与 `.codegraph/` |
| 源码文件数 | 43 个工程文件 |
| 标准化交付日志 | 已生成 Markdown 与 DOCX |
| 清理后交付包 | 已生成轻量 zip |
| 语法检查 | 已对 `source/src` 执行 `compileall` |

## 8. 功能约束与硬性规范

1. 支路一必须提供 `file_docx`，用于生成待审核 Excel。
2. 支路二正式使用时必须同时提供 `review_excel` 和原始 `file_docx`，缺少原始 DOCX 时直接报错。
3. Excel 建议固定三列表头：`中文原文`、`机器英文译文`、`人工审核`。
4. `人工审核` 列优先级最高；为空时使用 `机器英文译文`。
5. LLM 输出必须保留 `[行号]`，否则节点会按顺序回退对齐。
6. XML 回填依赖中文原文匹配；若人工修改了中文原文列，可能影响替换命中率。
7. 输出 DOCX 主要保留 run 级样式；复杂域代码、文本框、批注、脚注等结构未在材料中确认覆盖。
8. 预签名 URL 有有效期，过期后需重新生成或重新运行节点。

## 9. 最终交付产出清单

| 类别 | 名称 | 位置 |
|---|---|---|
| 工作流源码 | C 组 DOCX 翻译工作流源码 | `source/` |
| 原始日志 | 工作日志 docx 备份 | `source_materials/工作日志.docx` |
| 标准交付日志 | Markdown 版 | `docs/workflow_c_delivery_log.md` |
| 标准交付日志 | Word 版 | `docs/工作流C — DOCX文档翻译通道 · 标准化项目交付日志.docx` |
| 使用说明 | 工作流运行指南 | `docs/workflow_c_usage_guide.md` |
| 接口说明 | 输入输出变量与调用示例 | `docs/API.md` |
| 部署说明 | 环境与启动说明 | `docs/SETUP.md` |
| 凭据说明 | 所需外部服务清单 | `docs/CREDENTIALS.md` |
| 操作日志 | 本次整理记录 | `docs/workflow_operation_log.md` |
| 交付包 | 清理后的轻量 ZIP | `workflow_c_docx_translation_20260715.zip` |

## 附录 A：建议后续修正

| 优先级 | 建议 | 原因 |
|---|---|---|
| 已处理 | 支路二缺少 `file_docx` 时直接报错，不再回退到样例 URL | 避免正式交付时误替换样例文档 |
| 已处理 | 将 `thinking` 参数按配置尝试传入 LLM 调用，SDK 不支持时自动回退 | 保持配置与调用行为尽量一致，同时避免运行时崩溃 |
| 已处理 | 增加中文残留自动扫描和替换覆盖报告 | 便于交付前确认 DOCX 替换覆盖率 |
| 中 | 扩展标题样式识别到中文 Word 样式名（如“标题 1”） | 兼容中文 Office 模板 |
| 低 | 增加脚注、页眉页脚、文本框覆盖测试 | 当前 XML 处理会遍历部分 Word XML，但材料未列出完整验证 |
