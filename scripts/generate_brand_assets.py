from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from agent_gui_starter.app import (
    DISPLAY_FONT_FAMILY,
    UI_FONT_FAMILY,
    configure_application_fonts,
    make_brand_icon,
)


def generate(project_root: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    configure_application_fonts(app)
    assets = project_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    icon_png = assets / "app_icon.png"
    icon_pixmap = make_brand_icon(1024).pixmap(1024, 1024)
    if not icon_pixmap.save(str(icon_png), "PNG"):
        raise RuntimeError(f"Could not save {icon_png}")
    with Image.open(icon_png) as image:
        image.save(
            assets / "app_icon.ico",
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )

    canvas = QImage(1600, 520, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#FCF8EF"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(QPen(QColor("#D8D0C3"), 2))
    painter.drawLine(500, 82, 500, 438)
    painter.drawPixmap(105, 105, 310, 310, make_brand_icon(310).pixmap(310, 310))

    english_font = QFont(UI_FONT_FAMILY)
    english_font.setPixelSize(19)
    english_font.setWeight(QFont.Weight.Bold)
    painter.setFont(english_font)
    painter.setPen(QColor("#A9543B"))
    painter.drawText(QRect(570, 78, 900, 36), Qt.AlignmentFlag.AlignLeft, "YISHU  /  CULTURE TRANSLATION STUDIO")

    title_font = QFont(DISPLAY_FONT_FAMILY)
    title_font.setPixelSize(128)
    title_font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(title_font)
    painter.setPen(QColor("#254E45"))
    painter.drawText(QRect(558, 116, 900, 170), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "译述")

    tagline_font = QFont(DISPLAY_FONT_FAMILY)
    tagline_font.setPixelSize(38)
    tagline_font.setWeight(QFont.Weight.Medium)
    painter.setFont(tagline_font)
    painter.setPen(QColor("#4F625A"))
    painter.drawText(QRect(570, 286, 900, 66), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "译文字，也译语境。")

    detail_font = QFont(UI_FONT_FAMILY)
    detail_font.setPixelSize(22)
    painter.setFont(detail_font)
    painter.setPen(QColor("#7A817D"))
    painter.drawText(
        QRect(570, 362, 900, 54),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "图像 · 文档 · 文化术语 · 音视频  /  提取、翻译、审校与交付",
    )
    painter.end()

    lockup = assets / "brand_lockup.png"
    if not canvas.save(str(lockup), "PNG"):
        raise RuntimeError(f"Could not save {lockup}")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1])
