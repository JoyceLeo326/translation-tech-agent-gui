# 工作流B — 音视频翻译通道 · 标准化项目交付日志

**交付对象**：刘佳锐  
**交付日期**：2026-07-14  
**工作流编号**：工作流 B（音视频汉译英翻译通道）  
**平台**：扣子（Coze Coding）  
**编排框架**：LangGraph 1.0  
**维护人**：yuki  
**代码仓库**：`/workspace/projects`

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
| **输出侧** | 输出英文配音 + 字幕 + 二维码等可消费产物 |
| **对接方** | 整合负责人刘佳锐的多模态翻译 App |

### 2.3 实现功能

1. **自动模式分流**：系统根据输入文件类型智能判断运行模式，无需手动切换。
2. **ASR 语音识别**：将中文音频转写为文字，附带时间戳信息。
3. **AI 批量翻译**：调用大语言模型（豆包 Seed 2.0 Lite）逐句翻译为美式英语纪录片风格译文。
4. **待审校 Excel 生成**：输出标准 Excel 表格（含音频文字、机器译文、人工审核列），供人工校对。
5. **TTS 语音合成**：将校对完成的英文文本合成为美式英语语音（Allison 女声，语速 1.0）。
6. **音视频混音**：将合成语音混入原始视频/音频，生成成品。
7. **二维码交付**：为最终成品音频生成扫码即播的二维码。

### 2.4 双模式业务目标

| 模式 | 输入 | 处理 | 输出 | 业务目标 |
|------|------|------|------|----------|
| **模式一（预处理）** | 仅上传音视频文件 | 提取中文 → 翻译 → 生成三列对照 Excel | `review_excel`（待审校对照表） | 快速生成翻译初稿，供人工校对 |
| **模式二（回填）** | 上传校对完成 Excel + 复用原始音频 | 批量 TTS → 混音 → 二维码 | `full_audio_array` + `final_video_url` + `resource_qrcode` | 一键生成最终配音成品 |

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
| 3 | 集成对接 | 对接多模态翻译 App 负责人刘佳锐 | 明确输出变量需可直接对接总 App |
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
| 7 | yuki | 模式二结束时自动生成四列 Excel 输出 | 新增 `excel_output_generate_node`，原始 Excel 前三列 + 分段独立 TTS 音频链接填入第四列，与二维码并行返回 | ✅ 完成 |

### 3.4 Excel 表格调试

- **故障 1**：Excel 列错位（中文/机器译文/人工编辑 错位）
  - 现象：3 段测试偶发错位
  - 成因：CSV 中转时 LLM 输出含特殊引号/换行未转义
  - 修复：跳过 CSV 中转，直接构造 2D list 给 `DocumentGenerationClient.create_xlsx`
  - 验证：3 段测试 0 错位
- **故障 2**：分句错位（英文与中文不对应）
  - 现象：英文句子与中文断行不对齐
  - 修复：按语义完整分句（按句号），合并断行中文文本，保护章节边界

### 3.5 TTS 语音合成优化

- **故障 1**：月配额超限（`code=4036`）
  - 现象：长素材 165 段 → 165 次 TTS 调用，超出月配额
  - 方案：段合并策略 `MERGE_SEGMENTS_PER_BATCH=3`，每 3 段文本用 `. ` 拼接合成 1 次
  - 效果：165 段 → 55 次（节省 67%）
- **故障 2**：QPS 限流（`code=4404`）
  - 现象：并发调用触发平台限流
  - 方案：TTS 并发数降为 3 + 指数退避 2/4/8s + 识别 4404/429/limit 错误码自动重试
  - 验证：15 段测试 0 失败
- **故障 3**：音色混乱/漏句
  - 现象：英文用中文音色合成，且部分句子漏掉
  - 修复：切换 Allison 美式女声，SSML `<speak>` 包裹 + `ssml` 参数传递
- **故障 4**：语速不统一
  - 现象：英文 TTS 输出语速波动 8%
  - 方案：atempo 滤镜规范化，`tempo_ratio = total_dur / target_dur` 计算加速比
  - 效果：差异从 8% → 4.3%（17 字/秒 ± 0.7）
- **故障 5**：SSML 标签被 TTS 引擎读成文本
  - 现象：`<speak>`、`<lang>` 等标签被当作朗读内容输出
  - 根因：SSML 通过 `text` 参数传递，引擎按纯文本处理
  - 修复：改为通过 SDK `ssml` 参数传递 `<speak>` 包裹
- **故障 6**：合并音频只播放第一条（0 字节停顿文件污染）
  - 现象：ffmpeg `-c copy concat` 遇到空文件报错只保留第一段
  - 修复：检测 0 字节跳过或 pause=0 时跳过停顿文件生成

### 3.6 翻译 LLM 输出污染

- **故障**：机器译文列出现 LLM 推理过程（"哦不对,重新数一下...1.A 2.poetic..."）
- **根因**：LLM 自发输出推理链，thinking 未禁用
- **修复**：
  - `config/translation_llm_cfg.json`：`"thinking": "disabled"`
  - SP 强化约束："严禁输出任何推理过程、思考链、单词计数、自我纠正"
  - `translation_node.py`：新增 `_clean_translation_output()` 自动清洗

### 3.7 二维码功能修复

- **故障**：二维码扫描后仅展示单条音频
  - 现象：原本应展示全部英文音频的汇总二维码，只显示其中一条
  - 修复：把 TTS 输出 `segment_audio_urls` 整合为完整音频数组，生成数组形式的汇总二维码
- **工具选型**：本地 `qrcode` 库 + `PIL` 库生成 → 上传对象存储返回 URL

### 3.8 全局素材回填

- **问题**：模式二要重新上传音视频素材
  - 现象：用户在模式一上传过的素材，模式二仍需再次上传
- **方案**：
  - 模式一执行时，把 `media_file` 上传到 Supabase 全局缓存
  - 模式二启动时自动从 Supabase 读取 `media_file`
  - 实现跨模式素材复用，无需二次上传
- **存储选型**：使用 Supabase 第三方数据库做会话级缓存

### 3.9 Excel 预签名 URL 过期处理

- **故障**：Excel 下载返回 403 Forbidden
- **根因**：预签名 URL 签名有效期有限，过期后无法访问
- **修复**：`excel_read_node` 检测 HTTP 403/401 立即终止重试，给出"请重新上传 Excel 文件"明确指引

### 3.10 Gitee 私有仓库交付

- **仓库创建**：`https://gitee.com/sweet-donuts/audio--video-workflow`（私有）
- **推送过程**：
  1. 第一次生成 `workflow-b.tar.gz`（223KB，73 个文件）→ 用 `cp` 改名为 `.zip` → Windows 解压报错"压缩文件夹无效"
  2. 改用 Python `zipfile` 模块重新生成真正的 ZIP 格式（476KB，54 个文件）→ 用户成功解压
  3. VSCode 图形化 Git 推送时，URL 漏冒号变成 `https-//` → 用终端 `git remote remove origin` + `git remote add origin https://...` 重新添加
  4. Git 代理 7890 端口连接失败 → `git config --global --unset http.proxy` + `unset https.proxy` 关闭代理
  5. 成功推送整个 `projects` 目录到 Gitee 仓库
- **最终方案**：Gitee 私有仓库 + 协作者机制（国内访问速度优于 GitHub）

### 3.11 扣子协作权限调试

- **问题**：用户进不去扣子个人空间，没有"添加协作者"选项
- **原因**：用户没有扣子团队/未升级团队版
- **最终方案**：同学需自己部署自己的实例，共享仓库代码 + 工作流链接即可

---

## 4. 工作流执行动作

### 4.1 节点清单（共 15 个节点）

| 序号 | 节点 ID | 节点名称 | 类型 | 功能描述 |
|------|---------|----------|------|----------|
| 1 | `auto_mode_judge` | 智能模式判断 | task | 根据输入文件类型自动判断运行模式，上传 Excel→模式二，只有音频→模式一。模式二自动从 Supabase 查询原始音频 URL 复用 |
| 2 | `check_run_mode` | 运行模式路由 | condition | 条件分支，根据 run_mode 字段路由到"模式一_预处理"或"模式二_回填" |
| 3 | `asr_recognition` | ASR 语音识别 | task | 调用 ASRClient 将中文音频转写为文字+时间戳 |
| 4 | `data_table_construct` | 数据表格构造 | task | 将 ASR 结果构造为标准表格数据（含 segment_id、chinese_text、duration_ms） |
| 5 | `batch_translation` | 批量翻译 | agent | 调用豆包 Seed 2.0 Lite 逐句翻译中文→美式英语，循环处理（子图 `translation_loop_graph`） |
| 6 | `excel_generate` | Excel 生成 | task | 生成待审校 Excel（表头：音频文字、机器译文、人工审核），跳过 CSV 中转避免双引号错位 |
| 7 | `excel_data_fill` | Excel 数据填充验证 | task | 验证 Excel 数据完整性，确认包含中文原文和译文 |
| 8 | `end_mode1` | 模式一结束 | task | 模式一终点，输出 Excel URL + 提示消息 |
| 9 | `excel_read` | Excel 文件读取 | task | 读取校对完成的 Excel，提取人工审核列 + 机器译文列，两列都空才跳过。403/401 立即终止重试 |
| 10 | `data_validate` | 数据校验 | task | 人工审核列优先→空则降级到机器翻译→两列都空跳过。记录 text_source，输出统计日志 |
| 11 | `batch_tts` | 批量 TTS 合成 | task | 分句独立 TTS→atempo 语速规范化(17字/秒)→段间停顿 0.4s→ffmpeg 无损拼接。一句一个音频 + 合并音频双输出 |
| 12 | `media_compile` | 音视频混音 | task | 将 TTS 音频混入原视频/音频音轨，生成成品 |
| 13 | `end_mode2` | 模式二结束 | task | 模式二终点，传递 final_media_url + segment_audio_urls + 降级信息 |
| 14 | `excel_output_generate` | 四列 Excel 输出 | task | 模式二结束后自动生成四列 Excel（音频文字/机器译文/人工审核/音频下载地址），与 qr_code_generation 并行执行 |
| 15 | `qr_code_generation` | 二维码生成 | task | 生成成品音频的二维码（box_size=10, RGB 模式, 60px 白边），扫码直接播放 |

**类型说明**：task（任务节点）/ agent（大模型节点）/ condition（条件分支）/ looparray（列表循环）/ loopcond（条件循环）

### 4.2 双模式完整执行链路

#### 模式一：预处理分支

```
auto_mode_judge → check_run_mode(→"模式一_预处理") → asr_recognition
→ data_table_construct → batch_translation → excel_generate
→ excel_data_fill → end_mode1 → END
```

**流程说明**：
1. `auto_mode_judge` 检测到仅上传音频文件 → 设置 run_mode = "预处理・生成待审校Excel"
2. `check_run_mode` 路由到"模式一_预处理"
3. `asr_recognition` 调用 ASR 引擎，将中文音频转写为文字 + 时间戳
4. `data_table_construct` 将 ASR 结果构造为标准表格数据
5. `batch_translation` 逐句调用豆包 Seed 2.0 Lite 翻译为美式英语（子图循环处理）
6. `excel_generate` 生成待审校 Excel（含音频文字、机器译文、人工审核列）
7. `excel_data_fill` 验证 Excel 数据完整性
8. `end_mode1` 输出 Excel URL，工作流结束

#### 模式二：回填分支

```
auto_mode_judge → check_run_mode(→"模式二_回填") → excel_read
→ data_validate → batch_tts → media_compile → end_mode2
→ qr_code_generation ─────────┐
→ excel_output_generate ──────┤→ END
```

**流程说明**：
1. `auto_mode_judge` 检测到上传 Excel 文件 → 设置 run_mode = "回填・生成成品音视频"，自动从 Supabase 查询原始音频 URL
2. `check_run_mode` 路由到"模式二_回填"
3. `excel_read` 读取校对完成的 Excel，提取人工审核列 + 机器译文列
4. `data_validate` 校验数据：人工审核列优先→空则降级到机器翻译→两列都空跳过
5. `batch_tts` 分句独立 TTS 合成（Allison 美式女声，语速 1.0，段间停顿 0.4s），atempo 规范化 17 字/秒，ffmpeg 无损拼接
6. `media_compile` 将 TTS 音频混入原始视频/音频音轨
7. `end_mode2` 传递 final_media_url + segment_audio_urls
8. `qr_code_generation` 与 `excel_output_generate` **并行执行**：
   - `qr_code_generation`：生成扫码即播的二维码
   - `excel_output_generate`：生成四列 Excel（音频文字/机器译文/人工审核/音频下载地址），前三列取自原始 Excel，第四列为每句独立 TTS 音频链接
9. 两者均完成后工作流结束

### 4.3 子图清单

| 子图名 | 文件位置 | 类型 | 功能 | 被调用节点 |
|--------|----------|------|------|-----------|
| `translation_loop_graph` | `graphs/loop_graph.py` | looparray | 逐句循环翻译中文→英文 | batch_translation |

### 4.4 全局素材回填逻辑

| 模式 | 素材来源 | 是否需要上传 | 数据流向 |
|------|---------|------------|---------|
| 模式一 | 用户直接上传 | 是 | `media_file` → Supabase 缓存 |
| 模式二 | Supabase 自动读取 | 否 | Supabase 缓存 → `original_audio_url` |

**缓存机制**：
1. **缓存写入点**：模式一完成时，把 `media_file` 上传到 Supabase `audio_session_storage` 表
2. **缓存读取点**：`auto_mode_judge` 节点检测到模式二时，从 Supabase 取出 `upload_audio_url`
3. **缓存失效**：任务完成后保留 24 小时（与对象存储 URL 有效期一致）

---

## 5. 变量规范

### 5.1 输入变量

| 变量名称 | 数据类型 | 是否必填 | 适用模式 | 字段说明 |
|----------|----------|----------|----------|----------|
| `media_file` | `File`（音频/视频） | 条件必填 | 模式一 | 原始音视频文件（触发模式一），全局存储，模式二自动复用无需重复上传 |
| `finalized_excel` | `File`（Excel） | 条件必填 | 模式二 | 校对完成的 Excel 文件（触发模式二） |
| `original_audio_url` | `str` | 可选 | 模式二 | 原始音频 URL（模式二专用，系统自动从 Supabase 查询复用） |
| `run_mode` | `Literal["预处理・生成待审校Excel", "回填・生成成品音视频"]` | 可选 | 通用 | 运行模式（系统自动判断，用户可指定） |

### 5.2 输出变量

| 变量名称 | 数据类型 | 所属模式 | 字段说明 |
|----------|----------|----------|----------|
| `excel_url` | `str` | 模式一 | 生成的待审校 Excel 文件 URL |
| `final_media_url` | `str` | 模式二 | 成品音视频 URL（混音后的合并音频） |
| `qr_code_url` | `str` | 模式二 | 音频播放二维码图片 URL |
| `segment_audio_urls` | `List[str]` | 模式二 | 每句独立 TTS 音频 URL 列表（按 orig_idx 排序，一句一个文件） |
| `excel_output_url` | `str` | 模式二 | 四列 Excel 输出 URL（音频文字/机器译文/人工审核/音频下载地址），前三列取自原始 Excel，第四列为分段独立 TTS 音频链接 |
| `message` | `str` | 通用 | 输出提示消息（含 TTS 降级/配额耗尽等用户可见信息） |

### 5.3 业务变量 → 代码字段映射

| 业务变量 | 代码字段 |
|----------|----------|
| `media_file` | `GraphInput.media_file: File` |
| `finalized_excel` / `audit_excel` | `GraphInput.finalized_excel: File` |
| `run_mode` | `GlobalState.run_mode: str` |
| `review_excel` | `GraphOutput.excel_url: str`（模式一产出） |
| `full_audio_array` | `GraphOutput.segment_audio_urls: List[str]` |
| `final_video_url` | `GraphOutput.final_media_url: str` |
| `resource_qrcode` | `GraphOutput.qr_code_url: str` |
| `output_excel` | `GraphOutput.excel_output_url: str`（模式二产出，四列成品 Excel） |

---

## 6. 依赖资源与配置清单

### 6.1 扣子平台 SDK 调用清单

| 资源 | SDK 类/方法 | 使用节点 | 说明 |
|------|------------|----------|------|
| ASR 语音识别 | `coze_coding_dev_sdk.ASRClient` | asr_recognition | 中文音频→文字+时间戳 |
| 大语言模型 | `coze_coding_dev_sdk.LLMClient` | batch_translation (translation_node) | 豆包 Seed 2.0 Lite 翻译 |
| TTS 语音合成 | `coze_coding_dev_sdk.TTSClient` | batch_tts | Allison 美式女声，speech_rate=0 |
| 文档生成 | `coze_coding_dev_sdk.DocumentGenerationClient` | excel_generate | 生成 Excel 文件 |
| 音视频处理 | `coze_coding_dev_sdk.video_edit.VideoEditClient` | media_compile | 音频混音/替换音轨 |
| 对象存储 | `coze_coding_dev_sdk.S3SyncStorage` | excel_generate, batch_tts, qr_code_generation | 文件上传 + 预签名 URL 生成 |
| 数据库 | Supabase（通过 coze_coding_utils） | auto_mode_judge | 存储/查询原始音频 URL |

### 6.2 大模型配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 模型 ID | `doubao-seed-2-0-lite-260215` | 豆包 Seed 2.0 Lite |
| Temperature | 0.3 | 低温度保证翻译一致性 |
| Top P | 0.95 | |
| Max Tokens | 512 | |
| Thinking | disabled | 禁止输出推理过程 |
| 配置文件 | `config/translation_llm_cfg.json` | SP/UP 均含 TPM03 V2 纪录片风格指南 |

### 6.3 TTS 语音合成配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 音色 ID | `en_female_allison_uranus_bigtts` | Allison 美式英语母语女声 |
| 语速 (speech_rate) | 0 | 对应 speed_ratio=1.0 |
| 音量 (loudness_rate) | 0 | 标准音量 |
| 输出格式 | mp3 | |
| 采样率 | 24000 Hz | |
| 音色锁定策略 | SSML `<speak>` 包裹，通过 SDK `ssml` 参数传递 | 确保分段合成音色 100% 统一 |
| 段间停顿 | 0.4 秒 | 纪录片风格自然停顿 |
| 语速规范化 | 17.0 字/秒 (atempo) | 统一所有分句播放速度 |
| TTS 并发数 | 3 | 避免触发平台 QPS 限流 |
| TTS 重试退避 | 指数退避 2s / 4s / 8s | 自动重试限流错误 |

### 6.4 第三方依赖工具

| 工具 | 用途 | 关联节点 |
|------|------|---------|
| ffmpeg | 音频拼接、atempo 语速调整、静音段生成 | batch_tts, media_compile |
| ffprobe | 音频时长检测 | batch_tts |
| qrcode | 二维码图片生成 | qr_code_generation |
| Pillow | 图像处理（二维码白边添加） | qr_code_generation |
| openpyxl | Excel 文件读写 | excel_read |
| Jinja2 | LLM 提示词模板渲染 | translation_node |
| pandas | 数据表格处理 | data_validate, batch_tts |

### 6.5 外部 API 与存储

| 服务 | 用途 |
|------|------|
| 对象存储（TOS/S3） | 存放所有音频文件、Excel 文件、二维码图片 |
| Supabase | 存储原始音频 URL，实现模式二自动复用 |

---

## 7. 运行测试记录

### 7.1 测试概况

| 测试项 | 测试结果 | 说明 |
|--------|----------|------|
| 模式一完整链路 | ✅ 通过 | 音频→ASR→翻译→Excel 生成正常 |
| 模式二完整链路 | ✅ 通过 | Excel→TTS→混音→二维码生成正常 |
| 人工审核列空降级 | ✅ 通过 | 空则自动使用机器翻译列 |
| TTS 配额耗尽降级 | ✅ 通过 | code=4036 时部分降级，成功段继续拼接 |
| 段间停顿 0.4s | ✅ 通过 | 合并音频段间有明显自然停顿 |
| 音色一致性 | ✅ 通过 | SSML `<speak>` 包裹 + 参数锁定，分段音色统一 |
| 四列 Excel 输出 | ✅ 通过 | 模式二结束后自动生成，4 行 × 4 列，音频地址均为分段独立 URL |
| Excel 预签名 URL 过期 | ✅ 通过 | 403 立即终止重试并给出明确指引 |

### 7.2 关键故障与修复详情

| 故障 | 根因 | 修复方案 | 验证结果 |
|------|------|----------|----------|
| **Excel 分句错位** | CSV 中转时 f-string 未转义 `"` 导致列错位 | 跳过 CSV 中转，直接构造 `List[List[Any]]` 传 `create_xlsx_from_2d_list` | ✅ 3 段测试 0 错位 |
| **TTS 漏句** | data_validate 未正确处理空行 | excel_read 先提取两列再判断"两列都空才跳过" | ✅ 所有有效行均被合成 |
| **语速波动** | 未做 atempo 规范化 | 统一 17.0 字/秒，ffmpeg atempo 逐段调整 | ✅ 语速差异 < 5% |
| **4036 配额报错** | 无降级机制，全部失败 | "部分降级"：成功段继续拼接，失败段静音补位 | ✅ 降级后工作流不崩溃 |
| **二维码仅播放单条** | 只编码了合并音频 URL | 改为编码完整 audioList（所有分句 URL） | ✅ 扫码可播放完整音频 |
| **素材重复上传** | 每次运行生成新文件名上传 | Supabase 跨模式缓存 + 覆盖策略 | ✅ 无重复文件 |
| **SSML 标签读成文本** | 通过 `text` 参数传递 SSML | 改为 SDK `ssml` 参数传递 `<speak>` 包裹 | ✅ 4 段测试正常 |
| **翻译 LLM 输出思考链** | thinking 未禁用 + SP 未约束 | thinking=disabled + `_clean_translation_output()` | ✅ Excel 译文清洁 |
| **预签名 URL 403** | 签名过期 | 403/401 立即终止重试，明确指引重新上传 | ✅ 错误信息清晰 |
| **Gitee ZIP 解压失败** | `cp` 改名 tar.gz→zip | Python `zipfile` 模块生成真正 ZIP | ✅ Windows 正常解压 |

### 7.3 性能优化成果

| 指标 | 优化前 | 优化后 | 提升幅度 |
|------|--------|--------|---------|
| **TTS 月配额** | 165 次 | 55 次（段合并） | 节省 67% |
| **限流重试成功率** | 0% | 100% | 从不可用到完全可用 |
| **Excel 列错位** | 偶发 | 0 | 完全修复 |
| **atempo 语速差异** | 8% | 4.3% | 差异减少 46% |
| **素材复用** | 重复上传 | 自动复用 | 流程优化 |

---

## 8. 功能约束与硬性规范

### 8.1 流程限制

1. **运行模式自动判断**：系统根据输入文件类型自动分流，用户无需手动选择模式。
2. **模式一仅输出 Excel**：不生成音频，需人工校对后通过模式二回填。
3. **模式二依赖原始音频**：必须提供 `original_audio_url`（可从 Supabase 自动查询复用）。
4. **单次处理上限**：取决于 TTS 月度配额和 ASR 单次时长限制。

### 8.2 音色约束

1. **统一音色**：仅使用标准美式原生英文音色（`en_female_allison_uranus_bigtts` / Allison）
2. **不可切换**：工作流全程音色固定，禁止自动切换其他音色
3. **语速统一**：全局语速 17 字/秒，`speech_rate=0`（speed_ratio=1.0）
4. **语言强制**：美式英语（en-US），禁止 fallback 到中文音色
5. **音色一致性**：SSML `<speak>` 包裹通过 SDK `ssml` 参数传递，所有分段复用同一套参数
6. **禁止音效/背景音乐**：仅保留朗读正文

### 8.3 翻译规范（TPM03 V2 纪录片风格）

1. 美式英语拼写（color/realize/analyze）
2. 常用词优先，避免晦涩词汇
3. 简洁明了，避免冗长
4. 客观中立，纪录片解说风格
5. 避免中式英语/诱导性词汇/音译
6. 译文长度参考：中文 1 字 ≈ 英文 1.0-1.5 单词（柔性指导，±30% 可接受）

### 8.4 分句规则

1. ASR 按自然停顿分句
2. 每句独立 TTS 合成
3. 段间插入 0.4 秒停顿（纪录片风格）
4. 合并时 ffmpeg `-c copy` 无损拼接

### 8.5 素材复用约束

1. **跨模式复用**：模式二自动读取 Supabase 全局缓存的 `media_file`
2. **禁止重复上传**：用户在模式一已上传的素材，模式二无需再次上传
3. **缓存有效期**：与对象存储 URL 有效期一致（24h）

### 8.6 格式标准化约束

1. **Excel 格式（模式一产出）**：三列对照（音频文字 / 机器译文 / 人工审核）
2. **Excel 格式（模式二产出）**：四列对照（音频文字 / 机器译文 / 人工审核 / 音频下载地址），前三列取自输入原始 Excel，第四列为每句独立 TTS 音频链接（非合并音频），数据按行一一对应
3. **TTS 输出**：一句一个音频 + 合并音频双输出
4. **音频格式**：MP3，24000 Hz
5. **二维码格式**：PNG，RGB 模式，box_size=10，60px 白边

### 8.7 私有仓库交付规范

1. **仓库类型**：Gitee 私有仓库（国内访问速度优于 GitHub）
2. **不公开**：仓库设为私有，禁止 Fork 到公开仓库
3. **协作者机制**：同学通过 Gitee 协作者机制访问，无需公开链接
4. **凭据独立**：每个部署实例需独立申请扣子/Supabase 凭据

### 8.8 改动原则

1. **不改动原有基础功能**：保留工作流主链路
2. **仅新增优化节点**：仅在性能瓶颈/bug 出现处新增或重写
3. **最小侵入**：严格遵循最小侵入原则

---

## 9. 最终交付产出清单

### 9.1 代码与文档产出

| 类别 | 名称 | 位置/数量 |
|------|------|----------|
| **工作流源码** | 15 个核心节点 + 状态定义 + 主图编排 + 循环子图 | `src/graphs/` |
| **TTS 工具封装** | 含音色一致性策略文档 | `src/tools/speech_synthesis_tool.py` |
| **核心配置** | 翻译 LLM 配置 | `config/translation_llm_cfg.json` |
| **项目结构索引** | AGENTS.md | 项目根目录 |
| **使用文档** | workflow_b_usage_guide.md | `docs/` |
| **接口文档** | API.md（9 个 HTTP 接口完整对接示例） | `docs/` |
| **凭据清单** | CREDENTIALS.md（外部服务凭据申请清单） | `docs/` |
| **启动指南** | SETUP.md | `docs/` |
| **运行日志** | workflow_operation_log.md | `docs/` |
| **交付日志（本文档）** | workflow_b_delivery_log.md | `docs/` |
| **同学交付包** | workflow-b.zip（476KB，54 个文件） | `assets/` |

### 9.2 仓库与平台交付

| 类别 | 内容 |
|------|------|
| **Gitee 私有仓库** | `https://gitee.com/sweet-donuts/audio--video-workflow` |
| **扣子工作流链接** | 用户从扣子平台复制 |
| **测试数据** | `assets/mock/` 目录下测试用 Excel 文件 |

### 9.3 项目依赖清单

由 `pyproject.toml` 管理（uv 包管理器），核心依赖包括：
- `langgraph` >= 1.0
- `langchain-core` >= 1.0
- `coze-coding-dev-sdk`
- `coze-coding-utils`
- `pandas`、`openpyxl`、`qrcode`、`Pillow`、`Jinja2`

---

## 附录 A：TPM03 V2 改进方案（规划中 · 未实施）

> **状态**：⚠️ 规划中，**未实施**  
> **触发**：用户上传 TPM03 风格指南 V2 文档（237 段），指出现有工作流的 4 大核心问题  
> **影响范围**：5 个核心节点改造 + 1 个新节点新增  
> **约束**："其他功能不变"——保留现有所有功能，仅新增/优化

### A.1 四大核心问题

| # | 问题 | 具体表现 | 后果 |
|---|------|---------|------|
| 1 | 整体长音频直接合成 | 整段一次性翻译+配音，原始语速/停顿与新配音时长不一致 | 音视频错帧、时长匹配失衡 |
| 2 | 缺少逐句切分流程 | 没有按句子做时间轴（时间戳），无法逐句校对/对齐时长 | 整体合成后同步信息丢失 |
| 3 | Excel 字段不明确 | 不清楚最终定稿译文应该填入哪一列 | 精准回填困难 |
| 4 | 配音风格不统一 | 未严格对照 TPM03 风格指南 V2 | 纪录片语速、用词风格不达标 |

### A.2 五项改进方案

| # | 改进 | 方案 | 涉及节点 |
|---|------|------|---------|
| 1 | 音频按句子切分+时间戳 | 长音频→按静音/语义切分→导出逐句时间戳（start/end） | **新增** `audio_sentence_split_node` |
| 2 | 翻译载入术语库+风格模板 | 载入 TPM03 术语表+10 大翻译规则，逐句翻译，控制译文长度 | **改造** `batch_translation_node` |
| 3 | 逐句配音+匹配原句时长 | 逐句 TTS 合成，atempo 匹配原句时间轴 | **改造** `batch_tts_node` |
| 4 | Excel 存档字段完整化 | 增加时间戳、原句时长、TTS URL、TTS 实际时长等字段 | **改造** `excel_generate_node` + `excel_read_node` |
| 5 | 风格指南统一融入 | TPM03 V2 风格规则写入 LLM 翻译 prompt | **改造** `batch_translation_node` 配置 |

### A.3 TPM03 V2 风格指南核心规则

| # | 规则 | 示例 |
|---|------|------|
| 1 | **使用美式英语** | color（不用 colour）/ organize（不用 organise） |
| 2 | **第一二人称体现互动性** | "if you climb to the top, going downhill comes next" |
| 3 | **准确/灵活/简洁/自然** | 用 "we suggest that you arrive at..." 不用 "it is recommended that..." |
| 4 | **专业词汇用术语表** | Hydrargyrum（不是 Mercury）/ Uterus（不是 Womb） |
| 5 | **常用词优先** | about（不用 approximately）/ use（不用 utilize） |
| 6 | **简洁短语表达** | as（不用 in view of the fact that）/ so（不用 accordingly） |
| 7 | **避免情绪语气** | 用 "I wonder if you had such an experience" |
| 8 | **回译名言用公认翻译** | Leibniz: "No two leaves are alike." |
| 9 | **古诗词自行翻译** | 不照搬任何人的翻译，可改写 |
| 10 | **数字用阿拉伯数字** | "10,000"（不是 ten thousand） |

### A.4 实施前置条件

- ⚠️ 配额消耗会增加 5-10 倍（与 TPM03 月配额冲突，需先升级套餐）
- ⚠️ 需人工校对每句的时间戳边界
- ⚠️ 需提供 TPM03 术语表文件
