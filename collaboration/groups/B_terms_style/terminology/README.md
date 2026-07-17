# B 组术语库

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `中华文化术语对照表.xlsx` | 可移植正式版：212 条静态值，已移除外部工作簿公式和本机路径。 |
| `zhonghua_culture_terms.normalized.csv` | 从原始 Excel 生成的 UTF-8 CSV，英文译名中的弯引号已规范为直引号，便于程序检索。 |
| `zhonghua_culture_terms.normalized.json` | 与 CSV 同源的 JSON 版本，字段保留原表头并增加 `source_row`。 |

## 验收快照

- 原始表共 212 条术语。
- 表头为：术语、拼音、英文翻译、出处页码、上下文片段。
- 空行：0。
- 五个原始字段缺失值：0。
- 重复术语：0。
- PDF 抽取文本中命中术语：212/212。
- B 组修订版已修正第 28、38、105 行英文弯引号。
- B 组修订源文件含 612 个指向其本机 `文化术语库.xlsx` 的外链公式；正式版已固化缓存结果，公式 0、外部链接 0。
- B 组原始修订文件保存在 `../deliverables/revisions/20260717/source_from_b/`，用于审计，不作为整合输入。

详细结果见 `../deliverables/B_group_acceptance_snapshot.json`。
