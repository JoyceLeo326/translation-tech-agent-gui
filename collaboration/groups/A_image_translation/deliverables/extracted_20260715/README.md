# A组：pic_trans_replace 修正版

## 内容

- `A组整改需求_20260715.md`：给 A 组的明确整改需求与验收标准。
- `pic_trans_replace_fixed_20260715.zip`：完整交付包，包含最终 Word、脚本、修正图片、恢复图片和清单。
- `翻译资源编写-中国文化知识百科_完整修正版.docx`：最终修正版 Word。
- `pic_trans_fixed.py`：修正版处理脚本。
- `translation_manifest_fixed.xlsx`：图片译文和覆盖区域清单。
- `translated_images_fixed_contact_sheet.jpg`：18 张修正图片总览。

## 处理结论

原小组提交的 Word 包内 `word/media` 没有 `.svg` 文件，因此无法从该 Word 内恢复 SVG。截图中提到的 3 张黑白矢量/插图，已从 PDF 原材料中抽取恢复，并补入最终 Word。

## 验证记录

- 最终 Word 可由 `python-docx` 正常打开。
- 最终 Word 包内媒体数量：18。
- 文档图片嵌入引用数量：19，二维码图被引用两次。
- SVG 媒体数量：0。
- `pic_trans_fixed.py` 已通过 `py_compile`。
