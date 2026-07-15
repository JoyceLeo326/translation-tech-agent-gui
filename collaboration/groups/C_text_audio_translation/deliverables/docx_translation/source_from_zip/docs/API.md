# 工作流C API 说明

## GraphInput

| 字段 | 类型 | 说明 |
|---|---|---|
| `file_docx` | `File` | 支路一：待翻译 DOCX；支路二：原始 DOCX（支路二必填） |
| `review_excel` | `File` | 支路二：人工审核后的 Excel（支路二必填） |

## GraphOutput

| 字段 | 类型 | 说明 |
|---|---|---|
| `origin_excel` | `File` | 支路一输出的三列对照 Excel |
| `output_en_docx` | `File` | 支路二输出的英文 DOCX |
| `docx_replace_report` | `str` | 支路二输出的替换覆盖报告，包含替换数、未命中项、中文残留片段等 |

## 调用示例

### 支路一

```json
{
  "file_docx": {
    "url": "https://example.com/source.docx",
    "file_type": "document"
  }
}
```

### 支路二

```json
{
  "file_docx": {
    "url": "https://example.com/source.docx",
    "file_type": "document"
  },
  "review_excel": {
    "url": "https://example.com/review.xlsx",
    "file_type": "document"
  }
}
```

## 路由规则

`router_node` 优先判断 `review_excel`。只要存在 `review_excel`，即进入支路二；否则存在 `file_docx` 时进入支路一。

支路二必须同时传入 `review_excel` 和 `file_docx`。缺少原始 DOCX 时，`generate_docx` 会直接报错，不再使用样例 URL 兜底。
