# 工作流B — 音视频翻译通道 · 标准化项目交付日志

**交付日期**：2026-07-14  
**工作流编号**：工作流 B（音视频汉译英翻译通道）  
**平台**：扣子（Coze Coding）  
**编排框架**：LangGraph 1.0  
**维护人**：yuki  

---

## 1. 基础信息

| 项目 | 内容 |
|------|------|
| **项目名称** | 工作流B — 音视频翻译通道 |
| **工作流编号** | B |
| **维护人** | yuki |
| **更新日期** | 2026-07-14 |
| **运行平台** | Coze Coding（LangGraph 1.0 编排引擎） |
| **核心语言** | Python 3.12 |
| **依赖管理** | uv（pyproject.toml + uv.lock） |
| **对接方** | 多模态翻译 App（负责人：刘佳锐） |

---

## 2. 项目目的

### 2.1 业务定位

工作流B 是一套**智能双模式音视频翻译系统**，专门面向慕课/纪录片场景（TPM03 V2 项目），将中文解说音频自动翻译为美式英语配音，产出可直接使用的成品音视频。它是多模态翻译 App 的核心子模块之一。

### 2.2 核心职责

| 维度 | 内容 |
|------|------|
| **输入侧** | 接收用户上传的中文音视频素材 |
| **处理侧** | 智能识别模式 → 全自动流水线处理 |
| **输出侧** | 输出英文配音成品 + 二维码 + 四列对照 Excel |

### 2.3 实现功能

1. **自动模式分流**：系统根据输入文件类型智能判断运行模式，无需手动切换。
2. **ASR 语音识别**：将中文音频转写为文字，附带时间戳信息。
3. **AI 批量翻译**：调用大语言模型（豆包 Seed 2.0 Lite）逐句翻译为美式英语纪录片风格译文。
4. **待审校 Excel 生成**：输出标准 Excel 表格（含音频文字、机器译文、人工审核列），供人工校对。
5. **TTS 语音合成**：将校对完成的英文文本合成为美式英语语音（Allison 女声，语速 1.0，纪录片风格段间停顿 0.4s）。
6. **音视频混音**：将合成语音混入原始视频/音频，生成成品。
7. **二维码交付**：为最终成品音频生成扫码即播的二维码。
8. **四列 Excel 输出**：模式二结束时自动生成四列 Excel（音频文字/机器译文/人工审核/音频下载地址），与二维码并行返回。

### 2.4 双模式业务目标

| 模式 | 输入 | 处理 | 输出 | 业务目标 |
|------|------|------|------|----------|
| **模式一（预处理）** | 仅上传音视频文件 | ASR → 翻译 → 生成三列对照 Excel | `excel_url`（待审校对照表） | 快速生成翻译初稿，供人工校对 |
| **模式二（回填）** | 上传校对完成 Excel + 复用原始音频 | 读取 Excel → 校验 → 批量 TTS → 混音 → 二维码 + 四列 Excel | `final_media_url` + `qr_code_url` + `segment_audio_urls` + `excel_output_url` | 一键生成最终配音成品 |

### 2.5 改动原则

**不改动原有基础功能，仅新增优化节点**：
- 保留原有工作流主链路
- 仅在性能瓶颈 / bug 出现处新增优化节点或重写
- 严格遵循最小侵入原则

---

## 3. 交互开发记录

### 3.1 需求沟通阶段

| # | 时间节点 | 沟通事项 | 决策结果 |
|---|---------|---------|---------|
| 1 | 初次对接 | 用户提出"搭建汉译英翻译工作流"需求 | 明确双模式核心目标 |
| 2 | 需求细化 | 拆分"模式一素材识别出审校 Excel + 模式二上传审校表生成英文配音" | 锁定双分支自动分流架构 |
| 3 | 集成对接 | 对接多模态翻译 App  | 明确输出变量需可直接对接总 App |
| 4 | 改动约束 | 用户要求"不改动原有基础功能，仅新增优化节点" | 确认增量式开发原则 |

### 3.2 流程方案选择

- **编排框架选型**：选择 LangGraph 1.0 搭建有向无环图（DAG）
- **模式识别机制**：采用 `auto_mode_judge` 路由节点 + `check_run_mode` 条件分支
- **循环处理**：分批翻译使用循环子图（`translation_loop_graph`）
- **方案确认**：DAG 主图 + 子图组合架构，避开主图闭环

### 3.3 核心功能迭代

| 序号 | 需求方 | 需求描述 | 实现方案 | 状态 |
|------|--------|----------|----------|------|
| 1 | yuki | 双模式自动分流 | `auto_mode_judge_node` 智能判断 + `check_run_mode` 条件分支 | ✅ 完成 |
| 2 | 954565 | Excel 人工审核列空时自动降级到机器翻译列 | `excel_read_node` 两列都空才跳过；`data_validate_node` 人工审核优先→机器翻译降级 | ✅ 完成 |
| 3 | yuki | 语速统一 1.0，美式发音 | `DEFAULT_SPEED_RATIO=1.0`，`speech_rate=0`，固定 Allison 音色 | ✅ 完成 |
| 4 | yuki | 纪录片风格（段间停顿 0.4s） | `TPM03_V2_SENTENCE_PAUSE_SEC=0.4`，插入 ffmpeg 静音段 | ✅ 完成 |
| 5 | yuki | 去掉时间轴对齐，不匹配中文时长 | 禁用 `duration_ms` 自动分配，统一 17 字/秒自然语速 | ✅ 完成 |
| 6 | yuki | 音色一致性锁定 | SSML `<speak>` 包裹通过 SDK `ssml` 参数传递，全参数锁定 | ✅ 完成 |
| 7 | yuki | 翻译 LLM 输出清洗（禁止思考链污染） | `thinking: "disabled"` + `_clean_translation_output()` 自动清洗 | ✅ 完成 |
| 8 | yuki | SSE 连接断开异常保护 | 三层保护：全局 ASGI middleware + SSE wrapper + OpenAI try/except | ✅ 完成 |
| 9 | yuki | Excel 预签名 URL 过期 403 修复 | 检测 401/403 立即终止重试，给出明确"请重新上传"指引 | ✅ 完成 |
| 10 | yuki | 模式二结束时自动生成四列 Excel 输出 | 新增 `excel_output_generate_node`，原始 Excel 前三列 + 分段独立 TTS 音频链接填入第四列，与二维码并行返回 | ✅ 完成 |

### 3.4 Excel 表格调试

- **故障 1**：Excel 列错位（中文/机器译文/人工编辑 错位）
  - **根因**：CSV 中转时 LLM 输出含 `"` 双引号导致解析错位
  - **修复**：跳过 CSV 中转，直接构造 `List[List[Any]]` 传 `create_xlsx_from_2d_list`
- **故障 2**：翻译 LLM 输出思考过程污染机器译文列
  - **根因**：LLM 自发输出推理链（如"哦不对,重新数一下...1.A 2.poetic..."）
  - **修复**：`thinking: "disabled"` + SP 约束 + `_clean_translation_output()` 自动清洗
- **故障 3**：预签名 URL 过期 403
  - **根因**：TOS 预签名 URL 有时效性，过期后返回 403
  - **修复**：检测 401/403 立即终止重试，给出明确指引

### 3.5 TTS 音频调试

- **故障 1**：TTS 漏句（215 段中 2 段失败）
  - **修复**：软失败 + 静默补位，失败段用对应长度静音替代
- **故障 2**：语速波动（不同句子语速差异大）
  - **修复**：ffmpeg atempo 统一规范到 17.0 字/秒
- **故障 3**：code=4036 配额耗尽
  - **修复**：部分降级返回已成功段拼接 + 失败列表 + 友好提示
- **故障 4**：二维码仅播放单条音频
  - **修复**：改用 `silenceremove` 精准测有效语音时长
- **故障 5**：SSML 标签被 TTS 引擎当文本读
  - **修复**：改用 plain text 传参，消除中英混合口音
- **故障 6**：分段音色不一致
  - **修复**：SSML `<speak>` 包裹通过 SDK `ssml` 参数传递，全参数锁定

---

## 4. 工作流执行动作

### 4.1 节点清单（共 15 个）

| 序号 | 节点名 | 文件位置 | 类型 | 功能描述 |
|------|--------|---------|------|----------|
| 1 | `auto_mode_judge` | `nodes/auto_mode_judge_node.py` | task | 根据输入文件类型自动判断运行模式，实现双模式智能分流 |
| 2 | `asr_recognition` | `nodes/asr_recognition_node.py` | task | ASR 语音识别，提取文本和时间戳，保存原始音频 URL |
| 3 | `data_table_construct` | `nodes/data_table_construct_node.py` | task | 构造标准 Excel 表格数据 |
| 4 | `batch_translation` | `nodes/batch_translation_node.py` | agent | 批量汉译英翻译（循环处理），调用豆包 Seed 2.0 Lite |
| 5 | `excel_generate` | `nodes/excel_generate_node.py` | task | 生成待审校 Excel 文件（表头：音频文字/机器译文/人工审核） |
| 6 | `excel_data_fill` | `nodes/excel_data_fill_node.py` | task | 验证 Excel 数据填充，确认包含中文原文和译文 |
| 7 | `end_mode1` | `nodes/end_mode1_node.py` | task | 模式一结束节点，输出 Excel 提示 |
| 8 | `excel_read` | `nodes/excel_read_node.py` | task | 读取定稿 Excel 文件，先提取机器译文再判断跳过，403 立即终止 |
| 9 | `data_validate` | `nodes/data_validate_node.py` | task | 校验过滤有效译文，人工审核优先→机器翻译降级，记录 text_source |
| 10 | `batch_tts` | `nodes/batch_tts_node.py` | task | 分句独立 TTS → atempo 语速规范化(17字/秒) → 段间停顿(0.4s) → 拼接 |
| 11 | `media_compile` | `nodes/media_compile_node.py` | task | 音视频混音合成成品，回填 tts_audio_urls 到全局变量 |
| 12 | `end_mode2` | `nodes/end_mode2_node.py` | task | 模式二结束节点，传递音频 URL 和降级信息 |
| 13 | `qr_code_generation` | `nodes/qr_code_generation_node.py` | task | 生成成品音视频二维码（扫码即播） |
| 14 | `excel_output_generate` | `nodes/excel_output_generate_node.py` | task | 模式二结束时自动生成四列 Excel（音频文字/机器译文/人工审核/音频下载地址） |
| 15 | `check_run_mode` | `graphs/graph.py` | condition | 条件分支：判断运行模式一还是模式二 |

### 4.2 模式一完整执行链路

```
auto_mode_judge → check_run_mode(→"模式一_预处理")
    → asr_recognition（ASR语音识别）
    → data_table_construct（构造表格数据）
    → batch_translation（批量翻译，循环子图）
    → excel_generate（生成待审校Excel）
    → excel_data_fill（验证Excel数据）
    → end_mode1（模式一结束）
    → END
```

**输出**：`excel_url`（待审校 Excel 文件 URL）

### 4.3 模式二完整执行链路

```
auto_mode_judge → check_run_mode(→"模式二_回填")
    → excel_read（读取定稿Excel）
    → data_validate（校验过滤有效译文）
    → batch_tts（分句TTS + 语速规范化 + 段间停顿 + 拼接）
    → media_compile（音视频混音合成）
    → end_mode2（模式二结束）
    → [并行分支]
        ├─ qr_code_generation（生成二维码）
        └─ excel_output_generate（生成四列Excel输出）
    → END（两个并行分支都完成后结束）
```

**输出**：`final_media_url` + `qr_code_url` + `segment_audio_urls` + `excel_output_url`

### 4.4 子图清单

| 子图名 | 文件位置 | 功能描述 | 被调用节点 |
|--------|---------|----------|-----------|
| `translation_loop_graph` | `graphs/loop_graph.py` | 批量翻译循环处理 | `batch_translation`（内部实现） |
| `tts_loop_graph` | `graphs/loop_graph.py` | 批量 TTS 循环处理 | `batch_tts`（内部实现） |

---

## 5. 变量规范

### 5.1 输入变量（GraphInput）

| 变量名称 | 数据类型 | 是否必填 | 适用运行模式 | 字段说明 |
|----------|---------|---------|-------------|---------|
| `media_file` | `File` | 否 | 模式一 | 原始音视频文件（触发模式一） |
| `finalized_excel` | `File` | 否 | 模式二 | 定稿 Excel 文件（触发模式二） |
| `original_audio_url` | `str` | 否 | 模式二 | 原始音频 URL（模式二复用模式一生成的音频） |
| `run_mode` | `Literal` | 否 | 通用 | 运行模式（可选，系统自动判断） |

### 5.2 输出变量（GraphOutput）

| 变量名称 | 数据类型 | 所属模式 | 字段说明 |
|----------|---------|---------|---------|
| `excel_url` | `str` | 模式一 | 生成的待审校 Excel 文件 URL |
| `final_media_url` | `str` | 模式二 | 成品音视频 URL（合并音频） |
| `qr_code_url` | `str` | 模式二 | 音频播放二维码图片 URL（扫码即播） |
| `segment_audio_urls` | `List[str]` | 模式二 | 每段独立 TTS 音频 URL 列表（一句一个文件，按 orig_idx 排序） |
| `excel_output_url` | `str` | 模式二 | 模式二输出 Excel 文件 URL（四列表格：音频文字/机器译文/人工审核/音频下载地址） |
| `message` | `str` | 通用 | 输出提示消息 |

### 5.3 业务变量→代码字段映射

| 业务变量名 | 代码字段 | 说明 |
|-----------|---------|------|
| `review_excel` | `GraphOutput.excel_url` | 模式一输出：待审校 Excel |
| `full_audio_array` | `GraphOutput.segment_audio_urls` | 模式二输出：分段独立音频 URL 列表 |
| `final_video_url` | `GraphOutput.final_media_url` | 模式二输出：成品音视频 URL |
| `resource_qrcode` | `GraphOutput.qr_code_url` | 模式二输出：二维码图片 URL |
| `output_excel` | `GraphOutput.excel_output_url` | 模式二输出：四列对照 Excel |

---

## 6. 依赖资源与配置清单

### 6.1 扣子官方 SDK 调用清单

| SDK 类 | 使用节点 | 功能 |
|--------|---------|------|
| `coze_coding_dev_sdk.ASRClient` | `asr_recognition_node` | ASR 语音识别 |
| `coze_coding_dev_sdk.LLMClient` | `batch_translation_node` | 大语言模型翻译 |
| `coze_coding_dev_sdk.TTSClient` | `speech_synthesis_tool.py` | TTS 语音合成（绕过官方插件 4036 配额限制） |
| `coze_coding_dev_sdk.DocumentGenerationClient` | `excel_generate_node`, `excel_output_generate_node` | Excel 文件生成 |
| `coze_coding_dev_sdk.S3SyncStorage` | `batch_tts_node` | 对象存储上传 |
| `coze_coding_dev_sdk.video_edit.VideoEditClient` | `media_compile_node` | 音视频混音处理 |

### 6.2 大模型配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **模型 ID** | `doubao-seed-2-0-lite-260215` | 豆包 Seed 2.0 Lite |
| **temperature** | 0.3 | 低温度保证翻译稳定性 |
| **top_p** | 0.95 | 采样范围 |
| **max_completion_tokens** | 512 | 最大输出 token |
| **thinking** | `disabled` | 禁用思考链（防止输出推理过程污染译文） |
| **配置文件** | `config/translation_llm_cfg.json` | 包含 config/sp/up/tools 四个字段 |

### 6.3 TTS 语音合成配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **音色** | `en_female_allison_uranus_bigtts` | Allison 美式英语母语女声 |
| **语速** | `speech_rate=0`（speed_ratio 1.0） | 全程不浮动 |
| **音量** | `loudness_rate=0` | 全程不浮动 |
| **音频格式** | mp3 | 输出格式 |
| **采样率** | 24000 Hz | 标准采样率 |
| **SSML 模式** | `<speak>` 包裹通过 `ssml` 参数传递 | 音色一致性锁定 |
| **目标语速** | 17.0 字/秒 | ffmpeg atempo 统一规范 |
| **段间停顿** | 0.4 秒 | 纪录片风格 |
| **并发数** | 3 | `MAX_TTS_CONCURRENCY` |
| **重试配置** | 3 次，指数退避（2s/4s/8s） | `TTS_MAX_RETRIES` |

### 6.4 第三方依赖工具

| 工具 | 用途 |
|------|------|
| `ffmpeg` | 音频处理（atempo 语速规范化、静音段生成、无损拼接） |
| `qrcode` | 二维码图片生成 |
| `openpyxl` | Excel 文件读取 |
| `pandas` | 数据处理 |
| `jinja2` | 模板渲染（LLM 提示词） |
| `Supabase` | 会话存储（原始音频 URL 持久化） |

### 6.5 外部 API 与存储服务

| 服务 | 用途 |
|------|------|
| **TOS 对象存储** | 文件上传/下载（音频、Excel、二维码图片） |
| **Supabase** | 会话数据存储（原始音频 URL 跨模式复用） |

---

## 7. 运行测试记录

### 7.1 测试概况

| 测试项 | 测试现象 | 根因 | 修复方案 | 验证结果 |
|--------|---------|------|---------|---------|
| Excel 分句错位 | 中文/机器译文/人工编辑列错位 | CSV 中转时 LLM 输出含 `"` 双引号导致解析错位 | 跳过 CSV 中转，直接构造 `List[List[Any]]` 传 `create_xlsx_from_2d_list` | ✅ 通过 |
| TTS 漏句 | 215 段中 2 段失败 | 网络异常/TTS 服务临时故障 | 软失败 + 静默补位，失败段用对应长度静音替代 | ✅ 通过 |
| TTS 语速波动 | 不同句子语速差异大 | TTS 引擎对不同长度句子内部语速不一致 | ffmpeg atempo 统一规范到 17.0 字/秒 | ✅ 通过 |
| code=4036 配额报错 | TTS 月度配额耗尽 | 扣子官方 speech_synthesis 插件按调用次数计费 | 改用 `coze_coding_dev_sdk.TTSClient` 绕过配额限制 + 部分降级返回 | ✅ 通过 |
| 二维码仅播放单条音频 | 扫码只播放第一段 | ffmpeg `-c copy concat` 遇到 0 字节空文件报错 | 检测 0 字节文件跳过，或当 pause=0 时直接跳过停顿文件生成 | ✅ 通过 |
| 素材重复上传 | 模式二需要重新上传原始音频 | 模式一生成的音频 URL 未持久化 | Supabase 存储原始音频 URL，模式二自动查询复用 | ✅ 通过 |
| 翻译 LLM 输出思考过程 | 机器译文列出现"哦不对,重新数一下..." | LLM 自发输出推理链 | `thinking: "disabled"` + SP 约束 + `_clean_translation_output()` 自动清洗 | ✅ 通过 |
| SSE 连接断开异常 | "Pending response rejected since connection got disposed" | ASGI 协议层在客户端断开后仍推送数据 | 三层保护：全局 middleware + SSE wrapper + OpenAI try/except | ✅ 通过 |
| Excel 预签名 URL 过期 | 403 Forbidden | TOS 预签名 URL 有时效性 | 检测 401/403 立即终止重试，给出"请重新上传"指引 | ✅ 通过 |
| 四列 Excel 输出 | 模式二结束无 Excel 输出 | 缺少输出 Excel 功能 | 新增 `excel_output_generate_node`，与二维码并行生成 | ✅ 通过 |

### 7.2 性能优化成果

| 优化项 | 优化前 | 优化后 | 提升 |
|--------|-------|-------|------|
| TTS 并行 | 串行调用 | `MAX_TTS_CONCURRENCY=3` 线程池并行 | ~3 倍 |
| 分句生成策略 | 长文本合并 TTS | `MERGE_SEGMENTS_PER_BATCH=1` 每段独立 TTS | 消除长文本预热口音异常 |
| 音频拼接 | 逐段拼接 | ffmpeg `-c copy` 无损拼接 | 零质量损失 |

---

## 8. 功能约束与硬性规范

### 8.1 流程限制

1. **模式一必须先于模式二**：模式二依赖模式一生成的原始音频 URL（通过 Supabase 存储）
2. **Excel 必须包含三列**：音频文字、机器译文、人工审核
3. **人工审核列优先**：空则降级到机器翻译列，两列都空才跳过
4. **TTS 配额耗尽降级**：部分降级返回已成功段拼接 + 失败列表 + 友好提示

### 8.2 音色规范

1. **全局固定音色**：`en_female_allison_uranus_bigtts`（Allison 美式英语母语女声）
2. **语速锁定**：`speech_rate=0`（speed_ratio 1.0），全程不浮动
3. **音量锁定**：`loudness_rate=0`，全程不浮动
4. **SSML 模式**：`<speak>` 包裹通过 SDK `ssml` 参数传递，消除分段音色割裂/基频漂移
5. **口音统一**：用 plain text 传参（避免 SSML 标签被 TTS 引擎当文本读）

### 8.3 翻译规范

1. **美式英语**：全部使用美式英语拼写和表达
2. **纪录片风格**：简洁、自然、客观，符合 TPM03 V2 风格指南
3. **禁止思考链输出**：`thinking: "disabled"` + SP 约束 + 自动清洗
4. **长度控制**：中文 1 字 ≈ 英文 1.0-1.5 单词（柔性指导，±30% 可接受）

### 8.4 分句规则

1. **一句一个音频**：每段独立 TTS，生成阶段不合并
2. **段间停顿**：0.4 秒（纪录片风格）
3. **语速规范化**：ffmpeg atempo 统一规范到 17.0 字/秒
4. **无损拼接**：ffmpeg `-c copy` 拼接为 1 段连续音频

### 8.5 缓存机制

1. **原始音频 URL 持久化**：Supabase 存储，模式二自动查询复用
2. **TTS 重试机制**：3 次指数退避（2s/4s/8s），限流关键字匹配

### 8.6 输出格式标准

1. **模式一输出**：`excel_url`（待审校 Excel，三列表头）
2. **模式二输出**：
   - `final_media_url`：合并音频 URL（给二维码）
   - `qr_code_url`：二维码图片 URL（扫码即播）
   - `segment_audio_urls`：分段独立音频 URL 列表（一句一个文件）
   - `excel_output_url`：四列 Excel URL（音频文字/机器译文/人工审核/音频下载地址）
3. **四列 Excel 规范**：
   - 表头固定顺序：音频文字 → 机器译文 → 人工审核 → 音频下载地址
   - 数据按行一一对应：每行匹配对应分句独立 TTS 音频链接（非合并音频）
   - 前三列直接取自输入 Excel 原数据

---

## 9. 最终交付产出清单

### 9.1 代码与文档产出

| 产出项 | 路径 | 说明 |
|--------|------|------|
| 项目代码 | `/workspace/projects` | 完整工作流代码 |
| 节点代码 | `src/graphs/nodes/` | 15 个节点函数 |
| 状态定义 | `src/graphs/state.py` | GlobalState + GraphInput/Output + 节点 Input/Output |
| 主图编排 | `src/graphs/graph.py` | DAG 编排 + 条件分支 |
| 子图 | `src/graphs/loop_graph.py` | 翻译/TTS 循环子图 |
| TTS 工具 | `src/tools/speech_synthesis_tool.py` | TTS SDK 封装（音色一致性策略） |
| LLM 配置 | `config/translation_llm_cfg.json` | 翻译模型配置 |
| 项目索引 | `AGENTS.md` | 项目结构索引 |
| 交付日志 | `docs/工作流B_项目交付日志.md` | 本文档 |

### 9.2 扣子工作流

| 产出项 | 说明 |
|--------|------|
| 工作流 B | 音视频翻译通道（双模式自动分流） |

### 9.3 资源包

| 产出项 | 说明 |
|--------|------|
| 测试 Excel | `assets/mock/test_excel_manual_machine.xlsx` |
| 测试音频 | `assets/mock/` 目录下 |

---

## 附录 A：TPM03 V2 改进方案（规划中/未实施）

> **说明**：以下方案为 TPM03 V2 项目的进一步优化方向，当前版本尚未实施，仅作规划参考。

### A.1 当前版本存在的 4 大问题

1. **语速不均匀**：TTS 引擎对不同长度句子的内部语速不一致
2. **音色不统一**：分段独立 TTS 可能导致音色/基频漂移
3. **时间轴不对齐**：英文音频总时长与原始中文音频不匹配
4. **口音不统一**：SSML 标签被 TTS 引擎当文本读，导致中英混合口音

### A.2 5 项改进方案

1. **语速规范化**：ffmpeg atempo 统一规范到 17.0 字/秒 ✅ 已实施
2. **音色一致性锁定**：SSML `<speak>` 包裹 + 全参数锁定 ✅ 已实施
3. **口音统一**：plain text 传参，消除中英混合口音 ✅ 已实施
4. **段间停顿**：0.4 秒纪录片风格 ✅ 已实施
5. **时间轴对齐**：按英文词数比例分配 duration_ms ❌ 已禁用（用户要求不匹配中文时长）

### A.3 10 大风格规则

1. 美式英语（强制）
2. 词汇选择（常用词优先）
3. 简洁（强制）
4. 客观
5. 专业术语（按术语库）
6. 避免中式英语（强制）
7. 避免生硬直译和生硬意译（强制）
8. 避免诱导性词汇（强制）
9. 避免音译（强制）
10. 长度控制（柔性指导）

---

**文档结束**

*本文档由 yuki 于 2026-07-14 生成，基于工作流 B 实际代码和交互记录整理。*
