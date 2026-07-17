# A组图文翻译更新完整修正版

本目录是对 A 组 `pic_trans(2).zip` 的独立修正与可复现交付。原始更新包的 SHA-256 为：

`63FBB91B0E42864CC9ECD6F0C57838B4ECBD6E8D4DD5C1AF14474E2CEB6BEDED`

原包包含可用的真实 SVG 输入，但同时包含明文翻译服务凭据、过期工作目录图片、OCR 误识别、漏译和明显机器翻译问题，因此未原样上传 GitHub。

## 最终交付

- `final_outputs/翻译资源编写-中国文化知识百科_A组更新完整修正版.docx`：最终 Word。
- `manifests/translation_manifest_reviewed.xlsx`：71 个有效图中文字项的独立审校清单。
- `../archives/pic_trans_update_fixed_20260717.zip` 内的 `translated_images/`：与源 Word 内 31 个媒体一一对应的译后媒体，其中 10 个保持 SVG。为避免与 DOCX、预览图重复占用仓库空间，展开快照不再单独复制这一目录。
- `previews/translated_images_contact_sheet.jpg`：栅格媒体预览。
- `previews/final_docx_pages_contact_sheet.jpg`：17 页 Word 渲染预览。
- `validation/rendered_pages/`：由 Microsoft Word 16.0 导出结果渲染出的 17 页逐页预览。
- `validation/final_render_preview.pdf`：由上述逐页预览合成的便携验证 PDF。
- `validation/validation_report.json`：结构、哈希、媒体数量及 SVG 负向测试结果。

## 复现方法

运行环境：Python 3.11 或更高版本、Microsoft Windows。安装依赖后执行：

```powershell
python -m pip install -r requirements.txt
python scripts/pic_trans_update_fixed.py
```

脚本使用 `source/翻译资源编写-中国文化知识百科.docx` 作为唯一输入，每次从干净工作目录提取 Word 媒体，不读取 A 组提交的残留 `all_pictures` 目录，也不调用任何在线翻译接口。

可通过 `PIC_TRANS_FONT_REGULAR` 和 `PIC_TRANS_FONT_BOLD` 指定英文字体。Windows 默认使用 Arial；字体文件不存在时会回退到 Pillow 默认字体。

页面级复核需要使用 Microsoft Word 打开最终 DOCX 并导出为 `validation/final_render.pdf`，然后执行 `python scripts/render_pdf_pages.py`。仓库内已保留本次使用 Word 16.0 成功导出后生成的 17 页预览和合成预览 PDF。

## 处理边界

本交付只处理 A 组负责的图片内文字。Word 正文仍为中文，正文翻译属于其他小组的整合范围。
