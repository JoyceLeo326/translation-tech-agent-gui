## 项目概述
- **名称**: 工作流B - 音视频翻译通道
- **功能**: 智能双模式音视频翻译系统,支持自动识别输入类型,智能分流执行预处理或回填流程

### 节点清单
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| auto_mode_judge | `nodes/auto_mode_judge_node.py` | task | 根据输入文件类型自动判断运行模式，实现双模式智能分流。只有音频文件时，执行分之一预处理，在上传excel表格之后，自动复用预处理时上传的音频，执行分支二回填 | - | - |
| asr_recognition | `nodes/asr_recognition_node.py` | task | ASR语音识别,提取文本和时间戳,保存原始音频URL | - | - |
| data_table_construct | `nodes/data_table_construct_node.py` | task | 构造标准Excel表格数据 | - | - |
| batch_translation | `nodes/batch_translation_node.py` | agent | 批量汉译英翻译(循环处理) | - | `config/translation_llm_cfg.json` |
| excel_generate | `nodes/excel_generate_node.py` | task | 生成待审校Excel文件(表头:音频文字,机器译文,人工审核)。**关键修复**:跳过 CSV 中转,直接构造 List[List[Any]] 传 create_xlsx_from_2d_list,避免 LLM 输出含 `"` 双引号时 CSV 解析错位(原 f-string 包裹未转义导致列错位) | - | - |
| excel_data_fill | `nodes/excel_data_fill_node.py` | task | 验证Excel数据填充,确认包含中文原文和译文 | - | - |
| excel_read | `nodes/excel_read_node.py` | task | 读取定稿Excel文件。**关键修复**:先提取机器译文列再判断"两列都空才跳过",让用户可只修改部分人工审核列,其他沿用机器翻译。**403预签名URL过期**:检测到HTTP 401/403立即终止重试并给出"请重新上传Excel"的明确指引，避免无意义等待 | - | - |
| data_validate | `nodes/data_validate_node.py` | task | 校验过滤有效译文数据。**关键修复**:"人工审核列优先,空则降级到机器翻译列,两列都空才跳过"。每行记录 `text_source`("人工审核" 或 "机器翻译(人工审核为空,降级)"),便于用户追踪;输出日志统计 "人工审核 X 条 + 机器翻译降级 Y 条" | - | - |
| batch_tts | `nodes/batch_tts_node.py` | task | **分句独立TTS** → ffmpeg atempo 语速规范化(17.0字/秒) → TPM03 V2 段间停顿(0.4s,纪录片风格) → ffmpeg -c copy 无损拼接为 1 段连续音频。算法:用 silenceremove 精准测有效语音,atempo 倍速=原有效语音/目标有效语音。**分句生成策略**:`MERGE_SEGMENTS_PER_BATCH = 1`(每段独立 TTS,生成阶段不合并;输出阶段拼接为 1 段连续音频,扫码后听完整音频)。**口音统一**:用 plain text 传参(避免 SSML 标签被 TTS 引擎当文本读),消除 Allison 音色的"中英混合"口音。**性能优化**:步骤 1 使用 ThreadPoolExecutor 并行调用,加速 4 倍。**降级处理**:code=4036 TTS 月度配额耗尽时改为"部分降级"返回 | **一句一个音频双输出**:除合并音频外,另外上传每段独立 .mp3 到 S3,`segment_audio_urls` 字段返回 N 段独立 URL(按 orig_idx 排序)。- | - |
| media_compile | `nodes/media_compile_node.py` | task | 音视频混音合成成品(支持视频+音频混音和纯音频处理),回填tts_audio_urls到全局变量 | - | - |
| end_mode1 | `nodes/end_mode1_node.py` | task | 模式1结束节点,输出Excel提示 | - | - |
| end_mode2 | `nodes/end_mode2_node.py` | task | 模式2结束节点,传递tts_audio_urls和final_media_url | - | - |
| qr_code_generation | `nodes/qr_code_generation_node.py` | task | 生成成品音视频的二维码,内容为直接audio URL(扫码即可播放);box_size=10+RGB模式+60px白边 | - | - |
| check_run_mode | `graphs/graph.py` | condition | 判断运行模式 | "预处理"→asr_recognition, "回填"→excel_read | - |

**类型说明**: task(task节点) / agent(大模型) / condition(条件分支) / looparray(列表循环)

## 子图清单
| 子图名 | 文件位置 | 功能描述 | 被调用节点 |
|-------|---------|------|---------|
| translation_loop_graph | `graphs/loop_graph.py` | 批量翻译循环处理 | batch_translation(内部实现) |
| tts_loop_graph | `graphs/loop_graph.py` | 批量TTS循环处理 | batch_tts(内部实现) |

## 性能特性
- **TTS 并行**:`MAX_TTS_CONCURRENCY = 3` (speech_synthesis 插件限流安全值)
- **TTS 重试**:`TTS_MAX_RETRIES = 3`,遇到 `code=4404/429` 限流错误时指数退避 (2s/4s/8s)
- **分句生成 + TTS 并行**:`MERGE_SEGMENTS_PER_BATCH = 1`(关闭段合并,实现"分句来,整段出"——每段独立 TTS 规避长文本预热口音异常,输出阶段拼成 1 段连续音频), `MAX_TTS_CONCURRENCY = 3`, `TTS_MAX_RETRIES = 3` 限流指数退避
- **软失败 + 静默补位**(本版本):任何 TTS 错误(网络异常/服务故障)不再抛整体异常,改为"部分降级"——`other_failed_segment_ids` 记录失败 segment_id,已成功段继续走 atempo 规范化,缺失位置在拼接阶段用对应长度静音段补位(时长来源 ASR 原句时长),`tts_error_message` 透传到最终 message 提示用户"X 段 TTS 失败,已用静音补位"
- **段间停顿**:`TPM03_V2_SENTENCE_PAUSE_SEC = 0.4` 秒(纪录片风格,段间自然停顿);ffmpeg 生成 0.4s 静音段插入拼接列表
- **ffmpeg 速度规范化**:`TARGET_SPEECH_SPEED = 17.0 字/秒`,实测 3 段差异 4.3%
- **口音统一**:用 plain text 传参(避免 SSML 标签被 TTS 引擎当文本读)(消除 Allison 音色的中英混读);记录风格用语贴合 TPM03 V2 风格指南
- **TTS 配额耗尽降级**(2024-XX-XX):code=4036 月度配额耗尽时,不再让整个工作流崩溃,而是降级返回"已成功部分的拼接音频"+ 失败 segment_id 列表 + 友好提示;若全部批次都失败,仍抛友好异常并保留原始错误的解决方式说明
- **翻译输出自动清洗**(本版本):LLM 翻译模型有时会输出推理过程/思考链(如"哦不对,重新数一下...1.A 2.poetic...")污染"机器译文"列,`_clean_translation_output()` 函数通过模式匹配识别中文自问自答标记和数字编号列表,自动提取纯英文译文;同时 `translation_llm_cfg.json` 显式设置 `thinking: "disabled"` 并强化 SP 约束
- **人工审核列空时降级到机器翻译列**(本版本):`excel_read_node` 先把"人工审核"和"机器译文"两列都读到 `row_dict`,再判断"两列都空才跳过"行;`data_validate_node` 优先使用 `人工审核`,空则降级到 `机器译文`,并记录 `text_source`。**用户场景**:可只对部分句子做人工修改,未修改的自动沿用机器翻译生成音频;两列都空的行直接跳过
- **时间轴对齐已禁用**(本版本):用户要求"不需要让生成的英文音频和原来的中文音频时长一样",`data_validate_node` 不再自动分配 `duration_ms`,batch_tts 统一用 17 字/秒自然语速,不做 atempo 时长匹配
- **音色一致性锁定**(本版本):所有分段独立 TTS 调用复用同一套音色+声学参数(Allison + speech_rate=0 + loudness_rate=0)，通过 SDK 专用 `ssml` 参数传递 `<speak>` 包裹的纯文本，消除分段音色割裂/基频漂移。策略文档内嵌在 `speech_synthesis_tool.py` 模块头部

## 技能使用
- **ASR语音识别**: `asr_recognition_node` 使用 `coze_coding_dev_sdk.ASRClient`
- **大语言模型**: `translation_node` 使用 `coze_coding_dev_sdk.LLMClient` 进行翻译
- **文档生成**: `excel_generate_node` 使用 `coze_coding_dev_sdk.DocumentGenerationClient` 生成Excel
- **文件读取**: `excel_read_node` 使用 `utils.file.file.FileOps` 读取Excel
- **TTS语音合成**: `tts_synthesis_node` 使用平台级 `coze_coding_dev_sdk.TTSClient`,统一参数:`en_female_allison_uranus_bigtts` (Allison 美式英语母语女声) + `speech_rate=0` (speed_ratio 1.0) + `loudness_rate=0`。**音色一致性策略**:SSML `<speak>` 包裹通过 SDK `ssml` 参数传递(非 `text` 参数)，全程锁定音色+声学参数，消除分段音色割裂/基频漂移。封装在 `tools/speech_synthesis_tool.py`
- **音视频处理**: `media_compile_node` 使用 `coze_coding_dev_sdk.video_edit.VideoEditClient`
- **二维码生成**: `qr_code_generation_node` 使用 `qrcode` 库生成PNG二维码,上传到对象存储
- **会话存储**: `auto_mode_judge_node` 使用 Supabase 存储原始音频URL,实现模式二自动复用

## 工作流分支说明
工作流B支持智能双模式自动分流:

### 智能模式判断机制
**入口节点**: auto_mode_judge_node
- **输入识别**: 自动判断输入文件类型
- **模式一触发**: 仅上传音频文件(media_file) → 自动执行预处理流程
- **模式二触发**: 上传Excel文件(finalized_excel) + 原始音频URL(original_audio_url) → 自动执行回填流程
- **智能分流**: 系统自动识别并路由到对应的执行分支

### 模式1: 预处理分支
**路径**: auto_mode_judge → [智能判断] → asr_recognition → data_table_construct → batch_translation → excel_generate → excel_data_fill → end_mode1 → END

**功能**: 音频上传 → ASR识别 → 构造数据 → 批量翻译 → 生成Excel → 验证数据 → 结束

**输出**: Excel文件(包含音频文字、机器译文、人工审核列)

### 模式2: 回填分支
**路径**: auto_mode_judge → [智能判断] → excel_read → data_validate → batch_tts → media_compile → end_mode2 → qr_code_generation → END

**功能**: Excel读取 → 数据校验(人工审核优先,空则降级到机器翻译) → 批量TTS(平台 TTSClient + Allison 美式女声 + 语速1.0 + 0.4s 段间停顿纪录片风格 + 分句生成拼成 1 段连续音频,不匹配原中文时长) → 音视频混音 → 二维码生成 → 结束

**输入**: Excel文件(已审校) + 原始音频URL(可选,优先从Supabase自动查询)

**输出**: 成品音视频文件 + 二维码图片URL

## 配置文件清单
| 配置文件 | 用途 | 使用节点 |
|---------|------|---------|
| `config/translation_llm_cfg.json` | 翻译模型配置 | translation_node |

## 使用文档
详细使用说明请参考: `docs/workflow_b_usage_guide.md`