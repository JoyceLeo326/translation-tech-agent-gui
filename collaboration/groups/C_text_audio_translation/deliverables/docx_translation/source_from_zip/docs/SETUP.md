# 工作流C 部署与启动说明

## 环境

- Python 3.12
- uv
- Coze Coding 运行环境

## 安装依赖

```bash
uv sync
```

## 本地运行

运行完整流程：

```bash
bash scripts/local_run.sh -m flow
```

运行单个节点：

```bash
bash scripts/local_run.sh -m node -n node_name
```

启动 HTTP 服务：

```bash
bash scripts/http_run.sh -m http -p 5000
```

## 配置文件

| 文件 | 说明 |
|---|---|
| `config/translate_llm_cfg.json` | 文档逐行翻译模型配置 |
| `config/filename_translate_cfg.json` | 文件名翻译模型配置 |

## 交付前检查

```bash
python -m compileall src
```

当前代码已移除 `generate_docx_node.py` 中的样例 URL fallback。正式部署时，支路二必须同时提供审核 Excel 和原始 DOCX。
