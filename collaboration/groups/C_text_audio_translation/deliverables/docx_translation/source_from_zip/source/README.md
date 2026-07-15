# 项目结构说明

DOCX 分层分句分批翻译 + 审核回填替换 DOCX 工作流。

## 输入输出

- 支路一：上传 `file_docx`，生成三列对照 Excel：中文原文 / 机器英文译文 / 人工审核。
- 支路二：同时上传 `review_excel` 和原始 `file_docx`，生成英文 DOCX，并返回 `docx_replace_report` 替换覆盖报告。

支路二不再使用样例 DOCX URL 兜底；缺少原始 DOCX 时会直接报错。

# 本地运行
## 运行流程
bash scripts/local_run.sh -m flow

## 运行节点
bash scripts/local_run.sh -m node -n node_name

# 启动HTTP服务
bash scripts/http_run.sh -m http -p 5000
