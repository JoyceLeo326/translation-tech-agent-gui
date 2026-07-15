# 工作流 B 运行日志 —— 目的 · 动作 · 产出 · 需求

> **项目名称**: 工作流 B - 音视频翻译通道（智能双模式自动分流）
> **文档用途**: 记录工作流中每个节点的运行目的、执行动作、产出数据、依赖需求,作为运维、调试、交接的标准化参考
> **更新策略**: 节点 / 配置 / 策略变更时同步更新本文件
> **关联文档**:
> - 项目结构索引: `AGENTS.md`
> - 用户使用指南: `docs/workflow_b_usage_guide.md`

---

## 一、整体工作流概览

### 1.1 双模式自动分流拓扑

```
                          ┌─────────────────────┐
                          │  auto_mode_judge    │  智能模式判断入口
                          │  (输入识别 + 分流)  │
                          └──────────┬──────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                │                                         │
        仅上传音频                                上传 Excel
        media_file                                finalized_excel
                │                                         │
                ▼                                         ▼
        ┌──────────────────┐                    ┌──────────────────┐
        │   模式一·预处理   │                    │   模式二·回填    │
        │  ASR → 翻译 →   │                    │  Excel → 校验 →  │
        │  生成审校 Excel  │                    │  TTS → 混音 →   │
        │                  │                    │  二维码          │
        └──────────────────┘                    └──────────────────┘
```

### 1.2 核心策略说明

| 维度 | 策略 |
|------|------|
| **双模式触发** | 仅上传音频 → 模式一(预处理,产Excel);上传Excel → 模式二(回填,产音视频+二维码) |
| **音频复用** | 模式一处理后,音频URL自动存入Supabase;模式二执行时,自动从Supabase查询并复用,无需用户重新上传 |
| **TTS 音色** | 统一使用扣子平台爽快思思/Skye 英文母语女声,language=en-US,speed_ratio=1.0 |
| **TTS 配额优化** | 每 3 段相邻文本合并为 1 次 TTS 调用,节省 67% 月度配额(应对 4036 月配额限制) |
| **语速规范化** | 全部 TTS 输出经 ffmpeg atempo 统一到 17.0 字符/秒,消除引擎内部语速差异 |
| **音频拼接** | 使用 ffmpeg `-c copy` 无损拼接,保留原始编码质量 |
| **错误处理** | TTS 限流 (code=4404/429) 自动重试 3 次,指数退避 2s/4s/8s;最大并发 3 |

---

## 二、模式一 · 预处理(产审校 Excel)

> **路径**: `auto_mode_judge → asr_recognition → data_table_construct → batch_translation → excel_generate → excel_data_fill → end_mode1 → END`
> **输入**: 仅音频文件(`media_file`)
> **产出**: 待人工审核的 Excel(列: 音频文字 / 机器译文 / 人工审核)

### 2.1 节点运行日志(目的 · 动作 · 产出 · 需求)

| # | 节点 | 目的 | 动作 | 产出 | 需求 |
|---|------|------|------|------|------|
| 1 | **auto_mode_judge** | 判断运行模式,实现双模式智能分流 | 1. 检查 `media_file` 与 `finalized_excel` 2. 优先级:Excel > 音频 3. 仅音频 → 模式一,并将音频URL存入Supabase 4. 仅Excel → 模式二,并从Supabase自动查询原始音频URL | `run_mode` 字符串 / 原始音频URL / 提示信息 | 输入文件(`media_file` 或 `finalized_excel`)至少有一个;Supabase 可用 |
| 2 | **asr_recognition** | 从音视频中提取文本与时间戳 | 1. 下载音视频文件到本地 2. 转 base64 编码 3. 调用 `ASRClient.recognize()` 4. 解析返回的句子级文本与时间轴 | 原始文本 / 句子时间戳列表 / 原始音频URL(供模式二复用) | `media_file.url` 必须可访问;支持 mp3/wav/mp4 等格式;`ASRClient` 凭据可用 |
| 3 | **data_table_construct** | 构造标准 Excel 表格数据结构 | 1. 接收 ASR 输出的句子列表 2. 为每条句子分配 segment_id 3. 封装为 `table_data` 字典列表 | `table_data`(List[Dict],每条含 segment_id / 中文原文 / 时间戳) | ASR 节点产出的句子列表非空 |
| 4 | **batch_translation** | 批量汉译英翻译(Agent 节点) | 1. 调用子图 `translation_loop_graph` 2. 按句号/问号/感叹号分句 3. 对每条调用 LLM 翻译 4. 强制 100% 原文完整性,中英一一对应 | `translation_results`(List[Dict],含 segment_id / 中文 / 英文) | `table_data` 非空;LLM 凭据可用;`config/translation_llm_cfg.json` 配置文件存在 |
| 5 | **excel_generate** | 生成待审校 Excel 文件 | 1. 遍历 `table_data` 2. 直接构造 2D 列表(避免 CSV 转义) 3. 调用 `DocumentGenerationClient.create_xlsx_from_2d_list()` 4. 上传至对象存储 | Excel 文件URL(列:音频文字/机器译文/人工审核) | `DocumentGenerationClient` 可用;对象存储可用;`table_data` 至少 1 行 |
| 6 | **excel_data_fill** | 验证 Excel 数据填充,确认包含中文原文和译文 | 1. 读取生成的 Excel 2. 校验三列内容完整性 3. 校验中英行数一一对应 | `is_validated`(bool)/ `validated_row_count`(int) / 验证日志 | Excel URL 可访问;`utils.file.file.FileOps` 可用 |
| 7 | **end_mode1** | 模式一结束节点,输出 Excel 提示 | 1. 汇总模式一执行结果 2. 输出 Excel URL 给用户 3. 提示用户审校后再次上传 | `message`(含 Excel URL 与下一步操作指引) | 所有上游节点均已成功 |

### 2.2 模式一关键依赖清单

| 依赖项 | 用途 | 配置位置 |
|--------|------|----------|
| 翻译 LLM 凭据 | 翻译能力 | `config/translation_llm_cfg.json` |
| 文档生成 Client | 生成 Excel | `coze_coding_dev_sdk.DocumentGenerationClient` |
| 对象存储 (S3) | Excel 存储 | 平台自动配置 |
| ASR Client | 语音识别 | `coze_coding_dev_sdk.ASRClient` |
| Supabase | 音频URL持久化 | `tools/audio_session_storage.py` |

---

## 三、模式二 · 回填(产成品音视频 + 二维码)

> **路径**: `auto_mode_judge → excel_read → data_validate → batch_tts → media_compile → end_mode2 → qr_code_generation → END`
> **输入**: 已审校 Excel + 原始音频URL(可从 Supabase 自动复用)
> **产出**: 成品音视频文件 + 二维码图片

### 3.1 节点运行日志(目的 · 动作 · 产出 · 需求)

| # | 节点 | 目的 | 动作 | 产出 | 需求 |
|---|------|------|------|------|------|
| 1 | **auto_mode_judge** | 同模式一 | 1. 检测到 `finalized_excel` 存在 2. 调用 `get_latest_audio_url()` 从 Supabase 查询 3. 优先级:用户传入 `original_audio_url` > Supabase 缓存 4. 设置 `run_mode = "回填"` | 同模式一 | 同模式一,且 `finalized_excel` 必须存在 |
| 2 | **excel_read** | 读取定稿 Excel 文件 | 1. 下载 Excel 2. 调用 `FileOps.extract_text()` 解析表格 3. 提取"人工审核"列(若空则回退"机器译文"列) | `excel_data`(List[Dict],每行含 segment_id / 英文) | Excel URL 可访问;必须含"音频文字"或"机器译文"列 |
| 3 | **data_validate** | 校验并过滤有效译文数据,提取时间轴信息 | 1. 遍历 `excel_data` 2. 过滤空文本/纯标点/重复段 3. 合并短句(可选) 4. 提取时间戳 | `validated_data`(List[Dict],含 segment_id / final_translation / 时间戳) | `excel_data` 非空 |
| 4 | **batch_tts** | 批量 TTS 合成 + 语速规范化 + 拼接 | 1. **段合并**: 每 3 段合并为 1 次 TTS 调用(节省 67% 月度配额) 2. **并行 TTS**: `ThreadPoolExecutor` 最大并发 3,调用 `speech_synthesis` 插件(爽快思思/Skye + en-US) 3. **限流重试**: code=4404/429 自动重试 3 次,指数退避 2s/4s/8s 4. **下载到本地**: 从 TTS 返回 URL 下载到 /tmp 5. **atempo 规范化**: ffmpeg atempo 倍速 = 原有效语音/目标有效语音(目标 17.0 字/秒) 6. **-c copy 拼接**: 合并所有段为 1 段连续音频 7. **上传对象存储**: 拼接后音频上传至 S3 | `tts_audio_urls`(List[str],每段音频 URL) | `validated_data` 非空;speech_synthesis 插件**月度配额充足**;ffmpeg 已安装;对象存储可用 |
| 5 | **media_compile** | 音视频混音合成成品 | 1. 判断原始文件类型(视频/音频) 2. 若是视频: `VideoEditClient` 替换音轨 3. 若是纯音频: 直接返回 TTS 拼接结果(或 `concat_videos` 合并多段) 4. 输出最终成品 URL | `final_media_url`(成品音视频 URL) | `tts_audio_urls` 非空;`original_audio_url` 可访问(可选);`VideoEditClient` 可用 |
| 6 | **end_mode2** | 模式二结束节点,传递关键变量 | 1. 汇总模式二执行结果 2. 透传 `tts_audio_urls` 与 `final_media_url` 给下游 | `tts_audio_urls` / `final_media_url` / `message` | batch_tts 与 media_compile 均成功 |
| 7 | **qr_code_generation** | 生成成品音视频的二维码 | 1. QR 内容 = 直接 audio URL(扫码即播) 2. `qrcode` 库生成 PNG,`box_size=10`, L 级纠错 3. **关键**: 显式 `convert('RGB')` 避免 mode=1 位图 4. 加 60px 白色 padding(解决微信扫码识别失败) 5. 上传至对象存储 | `qr_code_url`(二维码图片 URL) | `final_media_url` 有效;`qrcode` 与 `PIL` 已安装;对象存储可用 |

### 3.2 模式二关键依赖清单

| 依赖项 | 用途 | 配置位置 |
|--------|------|----------|
| 语音合成插件 | TTS 合成 | 扣子官方 `speech_synthesis` 插件 (plugin_id=7426655854067351562) |
| TTS 插件月度配额 | 配额计数 | 扣子平台账号(本月配额需 ≥ 实际调用次数) |
| ffmpeg | atempo 语速规范化 + -c copy 拼接 | 系统已预装 |
| VideoEditClient | 视频混音 | `coze_coding_dev_sdk.video_edit.VideoEditClient` |
| qrcode 库 | 二维码生成 | `qrcode` + `PIL` |
| 对象存储 (S3) | 音频/二维码存储 | 平台自动配置 |

---

## 四、关键节点深度说明

### 4.1 auto_mode_judge(智能模式判断)

**核心价值**: 用户无需手动选择模式,系统根据输入自动判断。

**判断优先级**:
1. `finalized_excel` 存在 → 模式二(回填)
2. 仅 `media_file` 存在 → 模式一(预处理),**自动保存音频URL到Supabase**
3. 都不存在 → 报错

**音频复用机制**:
- 模式一执行时,生成的 `session_id` 与 `audio_url` 写入 Supabase 表 `audio_sessions`
- 模式二执行时,自动查询 Supabase 中最新一条记录,获取 `audio_url` 用于 `media_compile`
- **优先级**: 用户手动传入的 `original_audio_url` > Supabase 缓存

**Supabase 表结构**:
```
表名: audio_sessions
字段: session_id (PK) | audio_url | created_at
```

### 4.2 batch_tts(批量 TTS · 性能核心)

**核心策略**: **段合并 + 并行合成 + 限流重试 + 语速规范化 + 无损拼接**

**完整流程图**:
```
validated_data (N 段)
       │
       ▼
【段合并】每 3 段 → 1 次 TTS 调用
   N 段 → ⌈N/3⌉ 次调用
       │
       ▼
【并行 TTS】ThreadPoolExecutor, max_workers=3
   每次调用: speech_synthesis 插件
   限流时: 指数退避重试 3 次
       │
       ▼
【下载到本地】从 TTS 返回 URL 下载 MP3 到 /tmp
       │
       ▼
【atempo 规范化】ffmpeg -filter:a "atempo=R"
   R = 原有效语音 / 目标有效语音
   目标 = 17.0 字/秒
       │
       ▼
【-c copy 拼接】ffmpeg -c copy 合并所有段
       │
       ▼
【上传 S3】拼接后音频上传至对象存储
       │
       ▼
tts_audio_urls (合并段数 = ⌈N/3⌉ 个 URL)
```

**关键常量**(`src/graphs/nodes/batch_tts_node.py`):
```python
TARGET_SPEECH_SPEED = 17.0        # 目标语速(字符/秒)
GLOBAL_TTS_SPEAKER = "爽快思思/Skye"  # 统一英文母语音色
MAX_TTS_CONCURRENCY = 3           # TTS 并发数(防 4404 限流)
TTS_MAX_RETRIES = 3               # 限流重试次数
TTS_RETRY_BASE_DELAY = 2.0        # 首次重试延迟(秒)
TTS_RETRY_MAX_DELAY = 8.0         # 单次重试最大延迟(秒)
MERGE_SEGMENTS_PER_BATCH = 3      # 段合并数(节省 67% 月度配额)
```

**性能实测**:
| 段数 | 优化前总耗时 | 优化后总耗时 | 加速比 |
|------|------------|------------|--------|
| 3 段 | 12s | **5s** | 2.4x |
| 15 段 | ~50s | ~28s | 1.8x |
| 165 段 | ~600s | ~280s | 2.1x |

**配额消耗**:
| 段数 | 不合并 TTS 调用 | 合并后 TTS 调用 | 节省 |
|------|----------------|----------------|------|
| 6 段 | 6 | **2** | 67% |
| 15 段 | 15 | **5** | 67% |
| 165 段 | 165 | **55** | 67% |

### 4.3 excel_generate(Excel 生成 · 列错位修复)

**历史 Bug**: LLM 翻译输出含英文双引号 `"` 时(古诗、术语),f-string 手工拼接 CSV 未做 `""` 转义,导致解析时把第二列内容错切到第三列。

**修复方案**: 跳过 CSV 中转,直接构造 `List[List[Any]]` 传给 `create_xlsx_from_2d_list`,每个 cell 独立无歧义。

**Excel 结构**:
| 列 | 名称 | 内容来源 |
|----|------|----------|
| 1 | 音频文字 | ASR 识别原始中文 |
| 2 | 机器译文 | LLM 翻译英文 |
| 3 | 人工审核 | (留空,用户审校后填写) |

### 4.4 qr_code_generation(二维码生成 · 微信扫码优化)

**核心修复**:
1. **mode=1 → RGB**: qrcode 默认输出 1 位位图,微信/部分扫码APP不识别,显式 `convert('RGB')`
2. **60px 白边 padding**: QR 标准 quiet zone 4 模块,部分 APP 需要更宽白边,额外加 60px 解决
3. **直接 audio URL**: 不再依赖播放页(避免 NXDOMAIN),扫码即用浏览器/微信内嵌播放器打开

**关键参数**:
```python
box_size = 10           # 标准模块尺寸(手机相机最佳识别)
error_correction = 0    # L 级(7%, 容量最大)
border = 4              # QR 标准 quiet zone
extra_padding = 60      # 额外白边(微信兼容)
```

---

## 五、配置与性能速查表

### 5.1 LLM 配置

| 配置文件 | 模型 | 用途 | 温度 |
|---------|------|------|------|
| `config/translation_llm_cfg.json` | 翻译专用模型 | 中译英 | 见配置 |

### 5.2 性能与稳定性配置

| 参数 | 当前值 | 作用 | 调整影响 |
|------|--------|------|----------|
| `MAX_TTS_CONCURRENCY` | 3 | TTS 并发数 | 调大可能触发 4404 限流 |
| `TTS_MAX_RETRIES` | 3 | 限流重试次数 | 调小可能在 4404 时直接失败 |
| `TTS_RETRY_BASE_DELAY` | 2.0s | 首次重试延迟 | 调小可能持续触发限流 |
| `MERGE_SEGMENTS_PER_BATCH` | 3 | 段合并数 | 调大省配额但前几句口音可能略差 |
| `TARGET_SPEECH_SPEED` | 17.0 字/秒 | 目标语速 | 调小整体语速变慢,调大变快 |

### 5.3 已知限制

| 限制 | 原因 | 应对 |
|------|------|------|
| speech_synthesis 月度配额(4036) | 扣子平台 plan 限制 | 段合并(已实施)/ 升级 plan / 等下月刷新 |
| TTS QPS 限流(4404/429) | 平台瞬时并发限制 | 限流重试(已实施) |
| ASR 音频大小限制 | 平台 API 限制 | 暂未遇瓶颈 |
| 二维码内容长度 | QR 容量限制 | 当前直接 audio URL 无问题 |

---

## 六、运行监控与日志关键字

### 6.1 关键日志关键字(用于 grep 定位)

| 关键字 | 含义 | 出现位置 |
|--------|------|----------|
| `【智能模式判断节点】` | 模式判断开始 | auto_mode_judge |
| `【批量TTS启动】` | TTS 流程开始 | batch_tts |
| `【段合并】` | 段合并执行 | batch_tts |
| `【步骤1/3: 并行TTS合成】` | TTS 并行阶段 | batch_tts |
| `【步骤2/3: atempo语速规范化】` | atempo 阶段 | batch_tts |
| `【步骤3/3: 拼接+上传】` | 拼接阶段 | batch_tts |
| `[atempo]` | atempo 单次执行 | _normalize_speech_speed |
| `[ffmpeg -c copy 拼接]` | 拼接执行 | _concat_audio_files |
| `code=4404` | TTS 限流(可重试) | _synthesize_one |
| `code=4036` | TTS 月配额耗尽(不可重试) | _synthesize_one |
| `【合成前文本核对】` | TTS 文本预览 | batch_tts |
| `识别结果:` | ASR 完成 | asr_recognition |
| `规则2验证` | Excel 数据校验 | excel_generate |

### 6.2 异常码对照表

| 异常码 | 含义 | 自动处理 | 需人工介入 |
|--------|------|---------|-----------|
| 4404 | TTS QPS 限流 | ✅ 指数退避重试 3 次 | ❌ |
| 429 | TTS 限流(同类) | ✅ 指数退避重试 3 次 | ❌ |
| 4036 | TTS 月配额耗尽 | ❌ 直接失败 | ✅ 等下月/升级 plan |
| 5000+ | 平台通用错误 | ❌ 直接失败 | ✅ 查平台状态 |

---

## 七、变更历史

| 日期 | 变更内容 | 影响节点 |
|------|----------|----------|
| 初始版本 | 模式一+模式二双流程搭建 | 全部 |
| 智能分流 | 增加 `auto_mode_judge` 自动判断 | auto_mode_judge |
| 音频复用 | Supabase 存储原始音频URL | auto_mode_judge + media_compile |
| 切换TTS插件 | 从中文 TTS 技能切换到扣子 `speech_synthesis` 插件(爽快思思/Skye 英文母语) | tts_synthesis_node |
| atempo 规范化 | 引入 ffmpeg atempo 统一语速到 17.0 字/秒 | batch_tts |
| TTS 性能优化 | ThreadPoolExecutor 并行 + 去除复测 | batch_tts |
| Excel 列错位修复 | 跳过 CSV 中转,直接 2D 列表 | excel_generate |
| TTS 限流修复 | 限流重试 3 次(指数退避) | batch_tts |
| TTS 月配额优化 | 段合并(MERGE_SEGMENTS_PER_BATCH=3)节省 67% 配额 | batch_tts |
| 二维码微信兼容 | mode=1→RGB + 60px 白边 + 直接 audio URL | qr_code_generation |

---

> **维护说明**: 本文档由工作流搭建专家维护,任何节点 / 配置 / 策略变更后必须同步更新本文件相应章节。
