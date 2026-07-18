from __future__ import annotations

from pathlib import Path

import pythoncom
import win32com.client


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = PACKAGE_ROOT / "final_outputs" / "翻译资源编写-中国文化知识百科_A组更新完整修正版.docx"
PDF_PATH = PACKAGE_ROOT / "validation" / "final_render.pdf"


def main() -> None:
    if not DOCX_PATH.exists():
        raise FileNotFoundError(DOCX_PATH)
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PDF_PATH.unlink(missing_ok=True)

    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(DOCX_PATH),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        document.ExportAsFixedFormat(str(PDF_PATH), 17)
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()

    if not PDF_PATH.exists() or PDF_PATH.stat().st_size == 0:
        raise RuntimeError("Microsoft Word did not create the expected PDF")
    print(f"Word PDF: {PDF_PATH}")
    print(f"Bytes: {PDF_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
