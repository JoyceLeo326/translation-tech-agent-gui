# A组图文翻译更新完整修正版

本目录是对 A 组 `pic_trans(2).zip` 的独立修正与可复现交付。原始更新包的 SHA-256 为：

`63FBB91B0E42864CC9ECD6F0C57838B4ECBD6E8D4DD5C1AF14474E2CEB6BEDED`

原包包含可用的真实 SVG 输入，但同时包含明文翻译服务凭据、过期工作目录图片、OCR 误识别、漏译和明显机器翻译问题，因此未原样上传 GitHub。本版本已由 Codex 完成独立技术与语言终审，A 组无需再承担技术实现。

## 最终交付

- `final_outputs/翻译资源编写-中国文化知识百科_A组更新完整修正版.docx`：最终 Word。
- `manifests/translation_manifest_reviewed.xlsx`：71 个有效图中文字项的独立技术与语言终审清单。
- 完整 ZIP 内的 `translated_images/`：与源 Word 内 31 个媒体一一对应的译后媒体，其中 10 个保持 SVG。GitHub 展开快照不重复存放该目录，以避免与 DOCX、预览图和完整 ZIP 重复占用空间。
- `previews/translated_images_contact_sheet.jpg`：31 个媒体的完整预览，包含 20 个栅格媒体、10 个 SVG 和 1 个原样保留的二维码。
- `previews/final_docx_pages_contact_sheet.jpg`：17 页 Word 渲染预览。
- `validation/rendered_pages/`：由 Microsoft Word 16.0 导出结果渲染出的 17 页逐页预览。
- `validation/final_render.pdf`、`validation/final_render_preview.pdf`：Microsoft Word 16.0 的真实导出及便携副本。
- `validation/validation_report.json`：结构、哈希、媒体数量、离线 OCR、SVG 渲染及无文字节点 SVG 回填测试结果。

## 复现方法

运行环境：Python 3.11 或更高版本、Microsoft Windows。安装依赖后执行：

```powershell
python -m pip install -r requirements.txt
python scripts/pic_trans_update_fixed.py
python scripts/export_word_pdf.py
python scripts/render_pdf_pages.py
```

脚本使用 `source/翻译资源编写-中国文化知识百科.docx` 作为唯一输入，每次从干净工作目录提取 Word 媒体，不读取 A 组提交的残留 `all_pictures` 目录，也不调用任何在线翻译接口。可编辑 SVG 按 XML 文字节点处理；无可编辑文字节点的 SVG 使用本地 `resvg_py` 渲染、RapidOCR 离线识别和审校映射回填。

可通过 `PIC_TRANS_FONT_REGULAR` 和 `PIC_TRANS_FONT_BOLD` 指定英文字体。Windows 默认使用 Arial；字体文件不存在时会回退到 Pillow 默认字体。

`export_word_pdf.py` 使用本机 Microsoft Word 自动导出 `validation/final_render.pdf`，`render_pdf_pages.py` 生成 17 页逐页预览、页面总览和便携预览 PDF。仓库内已保留本次 Word 16.0 的真实导出与验证结果。

## 处理边界

本交付只处理 A 组负责的图片内文字。Word 正文仍为中文，正文翻译属于其他小组的整合范围。

原包中的服务密钥已经从修正版及 GitHub 交付中清除。密钥吊销和轮换只能由对应服务账号持有人在后台完成，不属于代码处理步骤。
