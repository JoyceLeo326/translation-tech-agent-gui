# 总整合交付验收记录

验收日期：2026-07-18

## 结论

整合端可独立完成的仓库归档、共享术语、A/B/C 适配、Qt GUI、OpenAI 智能体、Coze API 客户端、Python 总工作流、Excel/CSV/Markdown 输出、Windows EXE 和公开 GitHub 构建均已进入可验收状态。

最新版 A/B/C 成果已经纳入整合。仍有 3 项只能由账号或内容责任人完成的外部确认：B 组需要发布 2026-07-17 修订版 Coze 工作流并补状态证据；A 组真实成员需要对 71 条清单署名终审；A 组账号所有者需要确认原泄露密钥已经吊销。整合端不能代替相关责任人点击发布、签署人工审校或操作第三方账号。

## 要求与证据

| 原始要求 | 当前实现 | 验收证据 |
| --- | --- | --- |
| Qt 桌面 GUI | PySide6 品牌化工作台，双字体、局部玻璃材质、页面微动效，支持 1100×720 起自适应布局 | `src/agent_gui_starter/app.py`、`assets/fonts/`、`docs/screenshots/` |
| 调用智能体 | 支持 OpenAI Responses API；无密钥时明确离线 | `src/agent_gui_starter/agent.py` |
| 调用扣子工作流 | 按 `input_text`、`input_title` 调用 `/v1/workflow/run` | `src/agent_gui_starter/coze.py`、`tests/test_coze.py` |
| A/B/C 共享与整合 | 分组区、共享区、总整合区和本地适配器 | `collaboration/`、`src/agent_gui_starter/integration.py` |
| 术语与风格控制 | 212 条共享术语，GUI/命令行检索，B 组 Coze 入口 | `collaboration/shared/terminology/` |
| 图文成果接手 | 7 月 17 日更新修正版 DOCX、71 条清单、10 个 SVG、17 页渲染证据 | A 组 `extracted_20260717_update/` |
| 文本、DOCX、音视频接手 | 5 套 DOCX 样例、测试/总音频、终版表格、二维码 | C 组 `revised_20260717/` |
| 人工审校数据回填 | 整合报告输出 Markdown、CSV、Excel | `collaboration/integration/final_outputs/generated/` |
| Windows EXE | PyInstaller onedir 构建，内置 Noto Sans SC 与协作快照 | `scripts/build_exe.ps1` |
| 公开开源 | MIT License，GitHub `main`，Windows CI 构建产物 | `https://github.com/JoyceLeo326/translation-tech-agent-gui` |

## 可重复验收

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv\Scripts\python.exe scripts\verify_delivery.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build_exe.ps1
.\scripts\verify_build.ps1
```

`verify_delivery.py` 当前检查 19 个交付条件，包括 A 组新版压缩包、71 条清单、DOCX 哈希与 17 页渲染，B 组工作流结构、共享术语数量、C 组样例和 GUI 在线通道文件。Coze 发布、A 组人工终审和账号密钥吊销作为 `[EXTERNAL]` 单独报告，不伪装为整合端已经完成的责任人确认。

当前源码测试共 15 项，覆盖 Coze 请求契约、协作扫描与输出、最新版 A 组适配路径、五个主页面渲染、1100×720 重排、交互状态和真实初始内容。

## 运行配置

开发版读取仓库根目录 `.env`；打包版读取 EXE 同目录 `.env`。配置模板会复制到成品目录：

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
COZE_API_TOKEN=
COZE_WORKFLOW_ID=7661678571702747178
COZE_API_BASE=https://api.coze.cn
COZE_TIMEOUT_SECONDS=300
```

任何密钥、Token、账号密码都不得提交到公开仓库。
