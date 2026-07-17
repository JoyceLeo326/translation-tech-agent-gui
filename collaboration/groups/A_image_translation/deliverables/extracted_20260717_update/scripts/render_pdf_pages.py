from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PACKAGE_ROOT / "validation" / "final_render.pdf"
PAGES_DIR = PACKAGE_ROOT / "validation" / "rendered_pages"
CONTACT_SHEET = PACKAGE_ROOT / "previews" / "final_docx_pages_contact_sheet.jpg"
VALIDATION_JSON = PACKAGE_ROOT / "validation" / "validation_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_font() -> ImageFont.ImageFont:
    candidate = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if candidate.exists():
        return ImageFont.truetype(str(candidate), 18)
    return ImageFont.load_default()


def main() -> None:
    document = pdfium.PdfDocument(PDF_PATH)
    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    PAGES_DIR.mkdir(parents=True)

    pages: list[Image.Image] = []
    for index in range(len(document)):
        page = document[index]
        image = page.render(scale=1.5).to_pil().convert("RGB")
        image.save(PAGES_DIR / f"page_{index + 1:02d}.png", optimize=True)
        pages.append(image)

    columns = 3
    tile_w, tile_h, label_h = 430, 610, 28
    rows = (len(pages) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), (225, 225, 225))
    draw = ImageDraw.Draw(sheet)
    font = get_font()
    for index, source in enumerate(pages):
        image = source.copy()
        image.thumbnail((tile_w - 16, tile_h - 16), Image.Resampling.LANCZOS)
        column, row = index % columns, index // columns
        x = column * tile_w + (tile_w - image.width) // 2
        y = row * (tile_h + label_h) + (tile_h - image.height) // 2
        sheet.paste(image, (x, y))
        label = f"Page {index + 1}"
        box = draw.textbbox((0, 0), label, font=font)
        draw.text(
            (
                column * tile_w + (tile_w - (box[2] - box[0])) / 2,
                row * (tile_h + label_h) + tile_h + 3,
            ),
            label,
            font=font,
            fill=(20, 20, 20),
        )
    sheet.save(CONTACT_SHEET, quality=90)

    report = json.loads(VALIDATION_JSON.read_text(encoding="utf-8"))
    report["word_render"] = {
        "application": "Microsoft Word 16.0",
        "pdf_sha256": sha256(PDF_PATH),
        "page_count": len(pages),
        "pages_contact_sheet_sha256": sha256(CONTACT_SHEET),
    }
    VALIDATION_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rendered pages: {len(pages)}")
    print(f"PDF: {PDF_PATH}")
    print(f"Contact sheet: {CONTACT_SHEET}")


if __name__ == "__main__":
    main()
