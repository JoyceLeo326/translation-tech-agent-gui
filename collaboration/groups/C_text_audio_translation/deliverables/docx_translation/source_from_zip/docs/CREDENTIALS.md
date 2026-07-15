# 工作流C 凭据与外部资源清单

| 资源 | 用途 | 相关节点 |
|---|---|---|
| Coze LLM 服务 | 文本翻译、文件名翻译 | `translate_one_batch`、`generate_docx` |
| S3/TOS 对象存储 | 上传 Excel 和 DOCX，生成预签名 URL | `generate_excel`、`generate_docx` |
| Coze 文件运行上下文 | 下载上传文件到本地临时路径 | `docx_parse`、`read_excel` |

## 环境变量

源码中涉及的典型环境变量包括：

- `COZE_WORKSPACE_PATH`
- `COZE_BUCKET_ENDPOINT_URL`
- `COZE_BUCKET_NAME`

实际部署时应由扣子/Coze Coding 运行环境或项目密钥系统提供，不建议写入仓库。
