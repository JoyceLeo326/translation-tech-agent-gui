# 共享术语库

这里放跨组可复用的术语资源。目前同步自 B 组。

| 文件 | 说明 |
| --- | --- |
| `中华文化术语对照表.xlsx` | B 组提交的原始术语库，保留不改。 |
| `zhonghua_culture_terms.normalized.csv` | 规范化 CSV，供程序检索、GUI 或跨组适配器读取。 |
| `zhonghua_culture_terms.normalized.json` | 规范化 JSON，字段保留原始表头并增加 `source_row`。 |

规范化导出只处理机器检索兼容性问题，例如把英文译名中的弯引号改为直引号；原始 Excel 不在共享目录内直接改写。
