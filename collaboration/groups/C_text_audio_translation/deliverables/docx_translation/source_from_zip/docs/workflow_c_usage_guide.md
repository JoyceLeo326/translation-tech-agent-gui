# 工作流C 使用说明

## 支路一：中文 DOCX 生成对照 Excel

输入：`file_docx` 上传待翻译中文 DOCX。  
输出：`origin_excel`，三列为 `中文原文 / 机器英文译文 / 人工审核`。

执行链路：

```text
router → docx_parse → split → translate_batch → merge → generate_excel → END
```

操作步骤：

1. 上传中文 DOCX 到 `file_docx`。
2. 等待工作流生成 `origin_excel`。
3. 下载 Excel，在 `人工审核` 列中填写最终英文译文。

## 支路二：审核 Excel 回填生成英文 DOCX

输入：`review_excel` 上传审核完成的 Excel，同时提供原始 `file_docx`。  
输出：`output_en_docx`，保留原版式的英文 DOCX；同时输出 `docx_replace_report`，用于检查替换覆盖和中文残留。

执行链路：

```text
router → read_excel → generate_docx → END
```

操作步骤：

1. 上传审核后的 Excel 到 `review_excel`。
2. 同时上传支路一使用过的原始 DOCX 到 `file_docx`。
3. 工作流读取人工审核列；为空时回退到机器英文译文列。
4. 工作流生成英文 DOCX，并将中文文件名翻译为英文输出名。

## 使用注意

- 不要修改 Excel 的中文原文列，否则 DOCX 回填匹配率会下降。
- 建议人工审核只编辑第三列 `人工审核`。
- 支路二正式使用必须提供原始 DOCX；缺少 `file_docx` 时会直接报错。
- 预签名 URL 过期后需要重新运行或重新生成 URL。
