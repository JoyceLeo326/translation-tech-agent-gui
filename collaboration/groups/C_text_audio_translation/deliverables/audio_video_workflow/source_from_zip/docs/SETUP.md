# SETUP.md —— 同学从零启动指南

> **目标读者**: 接手本项目的同学 / 协作开发者
> **前置条件**: Linux / macOS / WSL2 环境,能联网,能装 Python
> **预计耗时**: 10-15 分钟从零跑通

---

## 一、环境要求

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| **Python** | 3.12+ | 必须 3.12 或以上,3.11 / 3.13 也可 |
| **uv** | 最新版 | 包管理工具(比 pip 快 10 倍) |
| **ffmpeg** | 最新版 | TTS 音视频处理依赖 |
| **Git** | 最新版 | 拉取代码 |

### 1.1 Python 3.12 安装

```bash
# macOS
brew install python@3.12

# Ubuntu / Debian
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev

# CentOS / RHEL
sudo yum install python3.12 python3.12-devel

# 验证
python3.12 --version
```

### 1.2 uv 安装

```bash
# 一键安装(官方推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证
uv --version
```

### 1.3 ffmpeg 安装

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# 验证
ffmpeg -version
```

---

## 二、克隆项目

```bash
git clone <你的仓库地址>
cd <项目目录>
```

**项目结构**:
```
├── src/                     # 源代码
│   ├── graphs/             # 工作流编排
│   ├── tools/              # 工具集成
│   ├── agents/             # Agent 代码
│   ├── storage/            # 存储
│   ├── tests/              # 测试用例
│   ├── utils/              # 业务封装(无需修改)
│   └── main.py             # HTTP 服务入口
├── config/                  # LLM 配置文件
├── docs/                    # 文档
│   ├── workflow_b_usage_guide.md    # 使用指南
│   ├── workflow_operation_log.md    # 运行日志
│   ├── SETUP.md                    # 本文档
│   ├── API.md                      # 接口文档
│   └── CREDENTIALS.md              # 凭据清单
├── assets/                  # 测试数据 / 静态资源
├── pyproject.toml           # 依赖声明
├── uv.lock                  # 依赖锁定
├── AGENTS.md                # 项目结构索引
└── README.md                # 项目说明
```

---

## 三、安装依赖

```bash
# 同步依赖(首次需要 2-5 分钟)
uv sync

# 激活虚拟环境
source .venv/bin/activate

# 验证关键依赖
python -c "import langgraph; print('langgraph:', langgraph.__version__)"
python -c "import fastapi; print('fastapi:', fastapi.__version__)"
python -c "import ffmpeg; print('ffmpeg-python:', ffmpeg.__version__)" 2>/dev/null || echo "ffmpeg-python 未装(可选)"
ffmpeg -version | head -1
```

---

## 四、配置凭据

> **重要**: 本工作流依赖多个外部服务,所有凭据由**扣子平台**统一托管,**不需要本地配置 .env 文件**。
> 但你需要确保**沙箱环境已绑定正确的扣子账号**,否则调用 ASR / LLM / TTS 插件会报 401。

### 4.1 平台凭据确认

```bash
# 检查扣子身份
coze-coding-utils --version

# 如果没装,先装
uv add coze-coding-utils
```

### 4.2 第三方服务授权

需要在扣子平台后台授权以下服务(每项一次,长期有效):

| 服务 | 用途 | 申请地址 |
|------|------|----------|
| **ASR 语音识别** | 提取音频文本 | 扣子平台 → 资源库 → 插件 → 搜索"语音识别" |
| **大语言模型** | 翻译能力 | 扣子平台 → 资源库 → 模型 → 申请翻译模型 |
| **文档生成** | 生成 Excel | 扣子平台 → 资源库 → 插件 → 搜索"文档生成" |
| **语音合成 (speech_synthesis)** | TTS 合成 | 扣子平台 → 资源库 → 插件 → 搜索"语音合成" |
| **对象存储 (S3)** | 文件存储 | 扣子平台 → 资源库 → 存储 → 创建 bucket |
| **Supabase** | 音频 URL 持久化 | 扣子平台 → 资源库 → 数据库 → 创建 Supabase 实例 |

详见 `docs/CREDENTIALS.md`。

---

## 五、启动服务

```bash
# 启动 HTTP 服务(默认端口 5000)
python src/main.py -m http -p 5000

# 或开发模式(带热重载)
uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

**启动成功标志**:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5000
```

### 健康检查

```bash
curl http://localhost:5000/health
# 预期: {"status":"ok","message":"Service is running"}
```

---

## 六、第一次跑通

### 6.1 模式一(上传音频,生成审校 Excel)

```bash
# 准备一个测试音频(可以用 assets/ 下的示例)
curl -X POST http://localhost:5000/async_run \
  -H "Content-Type: application/json" \
  -d '{
    "media_file": {
      "url": "https://example.com/test.mp3",
      "file_type": "audio"
    }
  }'
```

返回示例:
```json
{
  "task_id": "abc123...",
  "status": "pending"
}
```

### 6.2 查询任务状态

```bash
curl http://localhost:5000/task/abc123...
```

### 6.3 模式二(上传 Excel,生成音视频)

```bash
curl -X POST http://localhost:5000/async_run \
  -H "Content-Type: application/json" \
  -d '{
    "finalized_excel": {
      "url": "https://example.com/finalized.xlsx",
      "file_type": "document"
    },
    "original_audio_url": "https://example.com/original.mp3"
  }'
```

### 6.4 同步调用(简单场景)

```bash
curl -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -d '{
    "media_file": {
      "url": "https://example.com/test.mp3",
      "file_type": "audio"
    }
  }'
```

> 同步接口会**阻塞等待**任务完成,适合测试,不适合生产。
> 生产环境用 `/async_run` + `/task/{id}` 轮询。

---

## 七、运行测试

```bash
# 运行所有测试
uv run pytest src/tests/

# 运行单个测试
uv run pytest src/tests/test_xxx.py

# 查看测试覆盖率
uv run pytest --cov=src src/tests/
```

---

## 八、常见问题排查

### Q1: 启动报 `ModuleNotFoundError: No module named 'langgraph'`

**原因**: 没装依赖
```bash
uv sync
```

### Q2: 启动报 `ffmpeg: command not found`

**原因**: 没装 ffmpeg
```bash
# macOS
brew install ffmpeg
# Ubuntu
sudo apt install ffmpeg
```

### Q3: TTS 报 `code=4036 月度配额用尽`

**原因**: 扣子平台 TTS 插件月度配额已用完
**方案**:
- 等下月 1 号自动刷新
- 在扣子平台升级 plan(走"订单管理"或"账户中心")
- 代码层已实施 `MERGE_SEGMENTS_PER_BATCH=3` 段合并(节省 67%)

### Q4: TTS 报 `code=4404 API Request limit`

**原因**: TTS 并发过高
**方案**: 已实施限流重试 + 限流并发,无需手动处理
- 重试配置: `TTS_MAX_RETRIES=3`,指数退避 2s/4s/8s
- 并发配置: `MAX_TTS_CONCURRENCY=3`

### Q5: 二维码扫码识别不出来

**原因**: 微信 / 部分扫码 APP 对白边敏感
**方案**: 已修复 `qr_code_generation_node.py`:
- 显式 `convert('RGB')` 避免 mode=1 位图
- 额外加 60px 白色 padding

### Q6: Excel 导出第三列错位

**原因**: 历史 bug,LLM 输出含英文双引号 `"` 时 CSV 解析错位
**方案**: 已修复 `excel_generate_node.py`:
- 跳过 CSV 中转
- 直接构造 2D 列表传给 `create_xlsx_from_2d_list`

---

## 九、调试技巧

### 9.1 查看运行日志

```bash
# 实时跟踪日志
tail -f logs/app.log

# 只看错误
grep -i "error\|exception" logs/app.log | tail -20
```

### 9.2 节点单独调试

```bash
# 测试单个节点(以 ASR 为例)
python src/main.py -m node -n asr_recognition \
  -i '{"media_file": {"url": "https://example.com/test.mp3", "file_type": "audio"}}'
```

### 9.3 关闭 checkpoint 数据库

为了避免单测时频繁写 checkpoint,可以在 `src/main.py` 启动时设置环境变量:
```bash
export COZE_DISABLE_CHECKPOINT=1
python src/main.py -m http
```

---

## 十、下一步

- 跑通后,看 `docs/API.md` 学习怎么在前端调用
- 看 `docs/workflow_operation_log.md` 了解每个节点的运行细节
- 看 `docs/CREDENTIALS.md` 确认所有服务已授权
- 看 `AGENTS.md` 了解项目结构

---

## 十一、联系原作者

遇到本文档**未覆盖**的问题:
1. 先看 `docs/workflow_operation_log.md` 的"异常码对照表"
2. 再 grep `logs/app.log` 关键字
3. 实在搞不定 → 联系原作者
