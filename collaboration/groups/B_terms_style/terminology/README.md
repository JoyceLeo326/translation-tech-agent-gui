# B 组术语库

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `中华文化术语对照表.xlsx` | B 组提交的原始术语库，保留不改。 |
| `zhonghua_culture_terms.normalized.csv` | 从原始 Excel 生成的 UTF-8 CSV，英文译名中的弯引号已规范为直引号，便于程序检索。 |
| `zhonghua_culture_terms.normalized.json` | 与 CSV 同源的 JSON 版本，字段保留原表头并增加 `source_row`。 |

## 验收快照

- 原始表共 212 条术语。
- 表头为：术语、拼音、英文翻译、出处页码、上下文片段。
- 空行：0。
- 五个原始字段缺失值：0。
- 重复术语：0。
- PDF 抽取文本中命中术语：212/212。
- 原始 Excel 中第 28、38、105 行英文译名含弯引号；规范化 CSV/JSON 已处理，原始 XLSX 未改。

详细结果见 `../deliverables/B_group_acceptance_snapshot.json`。
