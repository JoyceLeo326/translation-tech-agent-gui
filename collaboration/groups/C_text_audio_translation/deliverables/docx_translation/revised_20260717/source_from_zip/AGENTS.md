## 项目概述
- **名称**: DOCX分层分句分批翻译+审核回填替换DOCX工具
- **功能**: 两条独立支路工作流
  - 支路1：上传DOCX，正文按句号问号感叹号拆分为单句，超长文本逐行分片分批翻译，最终输出三列对照Excel（中文原文、机器英文译文、人工审核空白列）
  - 支路2：**同时上传**校对完的Excel + 原始DOCX，读取第三列人工审核内容，直接操作XML回填替换，输出保留原格式的英文DOCX（不自动复用支路1的DOCX）
  - **页眉页脚支持**：支路1自动提取页眉页脚文本（加[页眉]/[页脚]标记），支路2自动识别标记并回填到对应位置

### 节点清单
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| router | `nodes/router_node.py` | task | 路由判断：根据输入选择支路1或支路2 | file_docx→branch1, review_excel→branch2, 无→end | - |
| docx_parse | `nodes/docx_parse_node.py` | task | 解析DOCX（段落+表格+页眉+页脚），识别Heading 1/Heading 2/Normal，正文按。！？拆分为单句，页眉页脚加[页眉]/[页脚]标记 | - | - |
| split | `nodes/split_node.py` | task | 逐行添加[行号]前缀，每片1行确保LLM逐行完整翻译 | - | - |
| translate_batch | `nodes/translate_batch_node.py` | task | 调用循环子图，遍历所有分片调用大模型翻译 | - | `config/translate_llm_cfg.json` |
| merge | `nodes/merge_node.py` | task | 按分片顺序拼接全部中文和英文内容 | - | - |
| generate_excel | `nodes/generate_excel_node.py` | task | 按行号对齐中英文，生成三列对照Excel（中文原文、机器英文译文、人工审核）并上传S3 | - | - |
| read_excel | `nodes/read_excel_node.py` | task | 读取审核Excel，优先取人工审核列，为空时取机器英文译文列 | - | - |
| generate_docx | `nodes/generate_docx_node.py` | task | 直接操作XML替换文本（非python-docx），遍历document/header/footer的XML，按比例分配英文到各run保留原始格式，识别[页眉]/[页脚]标记并回填到对应位置，匹配方式：精确匹配→子串匹配→反向匹配，提取原始文件名→LLM翻译为英文作为输出文件名 | - | `config/filename_translate_cfg.json` |

**类型说明**: task(task节点) / agent(大模型) / condition(条件分支) / loopcond(条件循环) / looparray(列表循环)

## 子图清单
| 子图名 | 文件位置 | 功能描述 | 被调用节点 | 类型 |
|-------|---------|------|---------|------|
| translate_loop_subgraph | `graphs/loop_graph.py` | 条件循环遍历所有分片，逐片调用大模型翻译，LLM输出行数不足时用原文填充 | translate_batch | loopcond |

## 配置文件
| 文件名 | 用途 |
|-------|------|
| `config/translate_llm_cfg.json` | 翻译大模型配置（豆包lite，逐行翻译） |
| `config/filename_translate_cfg.json` | 文件名翻译大模型配置（将中文文件名译为英文） |

## 技能使用
- `translate_batch`节点（及子图内`translate_one_batch`节点）使用大语言模型技能，调用豆包模型进行中译英翻译
- `generate_excel`节点使用S3对象存储技能上传Excel文件
- `generate_docx`节点使用S3对象存储技能上传DOCX文件，使用大语言模型技能将原始文件名翻译为英文，使用直接XML操作替换文本（非python-docx）

## 关键实现细节
- **文本替换方式**：`generate_docx_node`使用直接XML操作（`zipfile`+`xml.etree.ElementTree`），不依赖python-docx，避免save()时格式丢失
- **格式保留策略**：按原始中文文本各run长度比例，将英文翻译分配到每个run的`<w:t>`中，保留`<w:rPr>`中的全部格式属性（font、bold、italic、color等）
- **匹配策略**：精确匹配 → 子串匹配 → 反向匹配，支持合并文本的匹配
- **页眉页脚处理**：
  - 支路1：`docx_parse_node`解析DOCX后，额外遍历`word/header*.xml`和`word/footer*.xml`，提取文本并加`[页眉]`/`[页脚]`标记（便于Excel中区分）
  - 支路2：`generate_docx_node`处理页眉页脚XML时，同时尝试匹配带标记和不带标记的版本，找到匹配后自动去除翻译结果中的`[Header]`/`[Footer]`/`[页眉]`/`[页脚]`标记，只回填纯文本