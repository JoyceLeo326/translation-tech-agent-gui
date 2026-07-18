from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from agent_gui_starter.app import MainWindow, configure_application_fonts


def capture_all(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    configure_application_fonts(app)
    window = MainWindow()
    window.resize(2560, 1600)
    window.show()
    app.processEvents()
    QTest.qWait(700)

    page_setups = {
        "overview": lambda: None,
        "production": window._load_production_example,
        "agent": window._show_coze_demo,
        "terms": window._search_terms_now,
        "workflow": lambda: None,
        "showcase": lambda: None,
        "outputs": window._refresh_outputs_table,
        "settings": lambda: None,
    }

    for page_key, setup in page_setups.items():
        window._switch_page(page_key)
        setup()
        app.processEvents()
        QTimer.singleShot(80, lambda: None)
        QTest.qWait(280)
        app.processEvents()
        target = output_dir / f"workbench-{page_key}.png"
        if not window.grab().save(str(target), "PNG"):
            raise RuntimeError(f"Could not save screenshot: {target}")

    window.close()
    app.processEvents()


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    capture_all(project_root / "docs" / "screenshots")
