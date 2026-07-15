# CREDENTIALS.md —— 凭据清单

> **目标读者**: 接手项目的同学
> **重要**: 本清单只列**需要申请的服务清单**和**申请路径**,**不包含任何真实 Key / Token / 密码**。
> 所有凭据由**扣子平台统一托管**,本地不需要 `.env` 文件。

---

## 一、平台账号

| 凭据 | 用途 | 申请地址 | 备注 |
|------|------|----------|------|
| 扣子平台账号 | 所有集成的基础 | [www.coze.cn](https://www.coze.cn) | 工作流运行的基础账号 |
| 团队 / 工作空间 | 多人协作 | 平台 → 团队空间 | 建议创建独立团队,不要用个人空间 |

---

## 二、外部服务授权清单

工作流 B 依赖以下外部服务,每项需要在扣子平台**资源库**中授权一次。授权后调用时自动使用平台凭据,无需在代码里传 Key。

### 2.1 ASR 语音识别

| 项目 | 内容 |
|------|------|
| **用途** | 从原始音视频提取文本和时间戳 |
| **使用节点** | `asr_recognition_node` |
| **SDK 调用** | `coze_coding_dev_sdk.ASRClient(ctx=ctx)` |
| **申请路径** | 扣子平台 → 资源库 → 插件 → 搜索"语音识别" / "ASR" |
| **是否需要付费** | 取决于 ASR 插件,部分插件有免费额度 |
| **权限要求** | 通常需要工作空间管理员授权 |

### 2.2 大语言模型(翻译)

| 项目 | 内容 |
|------|------|
| **用途** | 中译英翻译 |
| **使用节点** | `batch_translation_node` (循环调用 `translation_node`) |
| **配置文件** | `config/translation_llm_cfg.json` |
| **申请路径** | 扣子平台 → 资源库 → 模型 → 申请翻译专用模型 |
| **配置项** | `model`、`temperature`、`top_p`、`max_completion_tokens` |
| **是否需要付费** | 按 token 计费,具体看模型定价 |

**示例配置结构(同学需要按自己申请的模型填写)**:
```json
{
  "config": {
    "model": "<同学自己申请的 model_id>",
    "temperature": 0.3,
    "top_p": 0.9,
    "max_completion_tokens": 2000,
    "thinking": "disabled"
  },
  "sp": "<系统提示词,见 config/translation_llm_cfg.json>",
  "up": "<用户提示词,见 config/translation_llm_cfg.json>",
  "tools": []
}
```

### 2.3 文档生成(Excel)

| 项目 | 内容 |
|------|------|
| **用途** | 生成待审校 Excel 文件 |
| **使用节点** | `excel_generate_node` |
| **SDK 调用** | `coze_coding_dev_sdk.DocumentGenerationClient` |
| **申请路径** | 扣子平台 → 资源库 → 插件 → 搜索"文档生成" |
| **支持格式** | Excel (.xlsx) / PDF / DOCX |

### 2.4 语音合成(TTS)

| 项目 | 内容 |
|------|------|
| **用途** | 英文 TTS 合成 |
| **使用节点** | `tts_synthesis_node` (被 `batch_tts_node` 调用) |
| **插件** | 扣子官方"语音合成 (speech_synthesis)" |
| **plugin_id** | `7426655854067351562` |
| **tool_name** | `speech_synthesis` |
| **音色** | 爽快思思/Skye(英文母语女声) |
| **申请路径** | 扣子平台 → 资源库 → 插件 → 搜索"speech_synthesis" 或 "语音合成" |
| **重要** | ⚠️ **此插件按调用次数计费,有月度配额限制** |
| **月度配额** | 取决于 plan 等级,详见 § 三 |

**支持的音色**:
| speaker_id | 描述 | 语言 |
|------------|------|------|
| `爽快思思/Skye` | 英文母语女声(当前使用) | en-US |
| `温暖阿虎/Alvin` | 英文母语男声(备选) | en-US |
| `zh_*` 系列 | 中文音色(不推荐用于英文) | zh-CN |

**注意**: 经过实测,**只有爽快思思/Skye 和温暖阿虎/Alvin 两个英文音色能正确合成英文**,其他 `zh_*` 音色合成英文会有严重口音问题。

### 2.5 对象存储(S3)

| 项目 | 内容 |
|------|------|
| **用途** | 存储生成的 Excel / 音视频 / 二维码 |
| **使用节点** | `excel_generate_node` / `batch_tts_node` / `qr_code_generation_node` |
| **SDK 调用** | `coze_coding_dev_sdk.S3SyncStorage` |
| **申请路径** | 扣子平台 → 资源库 → 存储 → 创建 bucket |
| **Bucket 名** | 同学自定(如 `my-workflow-bucket`) |
| **访问权限** | 公开读(用于 URL 直接访问) / 私有读(配合签名 URL) |
| **URL 有效期** | 默认 24 小时,可在 SDK 调用时调整 |

### 2.6 Supabase(会话存储)

| 项目 | 内容 |
|------|------|
| **用途** | 持久化"模式一处理的原始音频URL",供模式二自动复用 |
| **使用节点** | `auto_mode_judge_node` (通过 `tools/audio_session_storage.py`) |
| **数据库表** | `audio_sessions` (字段:`session_id`, `audio_url`, `created_at`) |
| **申请路径** | 扣子平台 → 资源库 → 数据库 → 创建 Supabase 实例 |
| **是否需要付费** | Supabase 免费层够用,超额按用量计费 |

**建表 SQL**(部署到 Supabase 后执行):
```sql
CREATE TABLE audio_sessions (
    session_id TEXT PRIMARY KEY,
    audio_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audio_sessions_created_at ON audio_sessions(created_at DESC);
```

### 2.7 视频处理(Video Edit)

| 项目 | 内容 |
|------|------|
| **用途** | 音视频混音(模式二合成成品) |
| **使用节点** | `media_compile_node` |
| **SDK 调用** | `coze_coding_dev_sdk.video_edit.VideoEditClient` |
| **申请路径** | 扣子平台 → 资源库 → 插件 → 搜索"视频编辑" |
| **功能** | 视频+音频混音 / 视频拼接 / 音频拼接 |

### 2.8 二维码生成(本地库,无需授权)

| 项目 | 内容 |
|------|------|
| **用途** | 生成成品音视频的二维码 |
| **使用节点** | `qr_code_generation_node` |
| **依赖** | `qrcode[pil]` (已包含在 pyproject.toml) |
| **是否需要授权** | ❌ 不需要,纯本地 Python 库 |

---

## 三、TTS 插件配额说明(重要)

### 3.1 配额机制

`speech_synthesis` 插件按**调用次数**计费,每调用 1 次 = 合成 1 段音频 = 计 1 次。

| 套餐 | 月配额(示例) | 价格(示例) |
|------|------------|-----------|
| 免费版 | 100 次 | 0 元 |
| 基础版 | 1000 次 | 几十元 |
| 专业版 | 10000 次 | 几百元 |
| 企业版 | 不限 | 几千起 |

> 具体档位以扣子平台实际显示为准。

### 3.2 配额消耗实测

| 输入段数 | 合并前 TTS 调用 | 合并后 TTS 调用(MERGE_SEGMENTS_PER_BATCH=3) | 节省 |
|---------|----------------|----------------------------------------|------|
| 6 段 | 6 | 2 | 67% |
| 15 段 | 15 | 5 | 67% |
| 165 段 | 165 | 55 | 67% |

### 3.3 配额耗尽错误

```
code=4036
msg=The monthly cumulative number of calls of plugin has reached the plan limit.
    If you need to continue making calls, please upgrade your plan.
```

**应对方案**:
1. **等下月 1 号** — 配额自动刷新
2. **升级 plan** — 平台 → 订单管理 / 账户中心
3. **调大段合并** — 把 `MERGE_SEGMENTS_PER_BATCH` 改为 5 或 10
   - 位置: `src/graphs/nodes/batch_tts_node.py` 第 48 行
   - 副作用: 合并块大,前几句口音可能略差

### 3.4 限流错误(QPS,不是月配额)

```
code=4404
msg=API Request limit
```

**应对**: 已实施自动重试 + 限流并发,无需手动处理
- `MAX_TTS_CONCURRENCY = 3`(并发 3,防触发限流)
- `TTS_MAX_RETRIES = 3`(限流时重试 3 次)
- 指数退避 2s / 4s / 8s

---

## 四、环境变量清单(本地开发可选)

> **重要**: 生产环境凭据由扣子平台托管,**不需要本地 .env 文件**。
> 仅本地开发 / 调试时,以下变量可能有用(全部留空也能跑):

```bash
# .env.example (不要提交真实凭据)
COZE_API_KEY=<留空,由沙箱注入>
COZE_BOT_ID=<留空>
COZE_WORKSPACE_ID=<留空>

# Supabase(如果不用平台托管)
SUPABASE_URL=<留空>
SUPABASE_KEY=<留空>

# S3 对象存储(如果不用平台托管)
S3_BUCKET=<留空>
S3_ACCESS_KEY=<留空>
S3_SECRET_KEY=<留空>
S3_ENDPOINT=<留空>
```

---

## 五、安全建议

### 5.1 凭据管理红线

| ✅ 应该 | ❌ 不应该 |
|--------|----------|
| 用扣子平台托管凭据 | 把 API Key 写在代码里 |
| 凭据用环境变量 | 把 `.env` 提交到 git |
| 定期轮换 Key | 多个服务共用同一个 Key |
| 监控异常调用 | 给所有接口开完全公开权限 |

### 5.2 Git 忽略配置

`.gitignore` 必须包含(确保凭据不泄露):
```gitignore
.env
.env.local
*.key
*.pem
secrets/
config/local/
```

### 5.3 团队协作凭据分发

- 不要把真实 Key 发到群里
- 用 1Password / Bitwarden 等密码管理器共享
- 给每个协作者申请**独立的子 Key**(便于审计和撤销)

---

## 六、凭据检查清单

**部署前请确认**以下服务均已授权:

- [ ] 扣子平台账号已登录
- [ ] ASR 插件已授权
- [ ] LLM 翻译模型已申请
- [ ] 文档生成插件已授权
- [ ] 语音合成 (speech_synthesis) 插件已授权
- [ ] 对象存储 Bucket 已创建
- [ ] Supabase 实例已创建 + `audio_sessions` 表已建
- [ ] 视频编辑插件已授权(模式二用)
- [ ] TTS 插件月度配额充足(预估任务量 × 合并系数)

**快速验证脚本**(部署后跑一次):
```bash
# 1. 健康检查
curl http://localhost:5000/health

# 2. 拉取图参数
curl http://localhost:5000/graph_parameter

# 3. 提交最小测试任务(用 1 段音频,看是否能跑通 ASR → 翻译 → Excel)
# 见 SETUP.md § 六
```

---

## 七、联系平台支持

遇到**授权问题**或**配额问题**:
- 扣子平台右下角 → 在线客服
- 提交工单: 平台 → 帮助中心 → 提交工单
- 紧急情况: 平台 → 联系商务(企业用户)

---

> **最后提醒**: 本文档**不包含任何真实凭据**。所有 Key / Token 在扣子平台 → 个人中心 → 凭据管理 申请和管理。
