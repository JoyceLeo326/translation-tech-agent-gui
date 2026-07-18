from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent_gui_starter.app import MainWindow, configure_application_fonts, make_brand_icon


class DemoCaption(QFrame):
    def __init__(self, parent: MainWindow) -> None:
        super().__init__(parent.centralWidget())
        self.setObjectName("DemoCaption")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            """
            QFrame#DemoCaption {
                background: rgba(31, 54, 47, 238);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 12px;
            }
            QLabel { background: transparent; border: 0; }
            QLabel#DemoKicker { color: #F0BD91; font-size: 12px; font-weight: 700; }
            QLabel#DemoTitle { color: #FFFDF8; font-size: 20px; font-weight: 700; }
            QLabel#DemoDetail { color: #DDE6E1; font-size: 13px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 13, 18, 14)
        layout.setSpacing(3)
        self.kicker = QLabel()
        self.kicker.setObjectName("DemoKicker")
        self.title = QLabel()
        self.title.setObjectName("DemoTitle")
        self.detail = QLabel()
        self.detail.setObjectName("DemoDetail")
        self.detail.setWordWrap(True)
        layout.addWidget(self.kicker)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.animation: QPropertyAnimation | None = None
        self.resize(470, 104)
        self.hide()

    def show_step(self, kicker: str, title: str, detail: str, *, centered: bool = False) -> None:
        self.kicker.setText(kicker)
        self.title.setText(title)
        self.detail.setText(detail)
        parent = self.parentWidget()
        if centered:
            width, height = 640, 174
            self.resize(width, height)
            self.move(max(16, (parent.width() - width) // 2), max(16, (parent.height() - height) // 2))
            self.title.setFont(QFont(self.title.font().family(), 28, QFont.Weight.Bold))
        else:
            width, height = 470, 104
            self.resize(width, height)
            self.move(max(16, parent.width() - width - 30), max(16, parent.height() - height - 28))
            self.title.setFont(QFont(self.title.font().family(), 18, QFont.Weight.Bold))
        self.raise_()
        self.show()
        self.effect.setOpacity(0.0)
        self.animation = QPropertyAnimation(self.effect, b"opacity", self)
        self.animation.setDuration(420)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deterministic YISHU screen-recording tour.")
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--start-file", type=Path, required=True)
    parser.add_argument("--timing-file", type=Path)
    return parser.parse_args()


def load_timings(path: Path | None) -> list[float]:
    defaults = [0.0, 8.0, 19.0, 29.0, 39.0, 54.0, 67.0, 78.0, 89.0, 100.0, 111.0]
    if path is None or not path.exists():
        return defaults
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    values = [float(value) for value in data.get("starts", defaults)]
    return values if len(values) >= len(defaults) else defaults


def move_to(widget: object) -> None:
    if hasattr(widget, "rect") and hasattr(widget, "mapToGlobal"):
        QCursor.setPos(widget.mapToGlobal(widget.rect().center()))


def main() -> int:
    args = parse_args()
    for path in (args.ready_file, args.start_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    configure_application_fonts(app)
    app.setApplicationName("译述 YISHU 演示")
    app.setOrganizationName("Culture Translate")
    app.setWindowIcon(make_brand_icon())

    window = MainWindow()
    window.showFullScreen()
    overlay = DemoCaption(window)
    timings = load_timings(args.timing_file)
    started = False

    def click_nav(key: str, action: Callable[[], None] | None = None) -> None:
        button = window._nav_buttons[key]
        move_to(button)
        if action is None:
            QTimer.singleShot(260, button.click)
        else:
            QTimer.singleShot(260, action)

    def click_tab(index: int) -> None:
        bar = window._production_tabs.tabBar()
        QCursor.setPos(bar.mapToGlobal(bar.tabRect(index).center()))
        QTimer.singleShot(260, lambda: window._production_tabs.setCurrentIndex(index))

    def intro() -> None:
        window._switch_page("overview")
        overlay.show_step(
            "YISHU PRODUCT TOUR",
            "译述 · 中国文化多模态外译工作台",
            "把图片、Word、音视频、文化术语与智能工作流整合为一套可直接交付的桌面软件",
            centered=True,
        )

    def production_image() -> None:
        overlay.show_step("02 / 多模态入口", "翻译文件，一处完成", "无需理解技术名词，选择图片、Word 或音视频即可开始")
        click_nav("production", window._open_beginner_example)

    def settings_demo() -> None:
        overlay.show_step(
            "01 / 在线模型接口",
            "连接自己的模型，开启真实在线处理",
            "支持 OpenAI、Ollama、LM Studio、兼容服务与 Coze；密钥只保存在本机",
        )
        click_nav("settings")

    def production_docx() -> None:
        overlay.show_step("03 / Word 审校回填", "先提取审校，再保持版式回填", "正文、表格、页眉页脚统一进入 Excel 人工审校链路")
        click_tab(1)

    def production_audio() -> None:
        overlay.show_step("04 / 音视频外译", "识别、翻译、审核与英文配音", "真实测试样例和审核表已接入，可直接生成语音成果")
        click_tab(2)

    def agent_demo() -> None:
        overlay.show_step("05 / 核心精译能力", "Coze 多模型精译，让重要译文经过讨论", "术语提取、三路独立初译、交叉评价，再由 GLM 融合为可审校终稿")
        click_nav("agent", lambda: (window._switch_page("agent"), window._show_coze_demo()))

    def terms_demo() -> None:
        overlay.show_step("06 / 文化术语库", "统一文化概念的英文表达", "按关键词即时检索中英译法、出处页码和上下文证据")

        def action() -> None:
            window._switch_page("terms")
            window._term_search.setText("端午节")
            window._search_terms_now()
            move_to(window._term_search)

        click_nav("terms", action)

    def workflow_demo() -> None:
        overlay.show_step("07 / 批量流程", "所有环节可追踪、可检查", "从资源扫描到审校回填，状态、证据和输出文件集中呈现")

        def action() -> None:
            window._switch_page("workflow")
            window._workflow_input.setPlainText("检查术语一致性，并生成适合课堂展示的最终交付清单。")
            move_to(window._workflow_run_button)

        click_nav("workflow", action)

    def showcase_demo() -> None:
        overlay.show_step("08 / 交付实证", "真实文件、人工审校与验收记录", "71 条图文审校、251 条术语、5 份 Word 实测与 219 句英文配音")
        click_nav("showcase")

    def outputs_demo() -> None:
        overlay.show_step("09 / 最终交付", "成品文件集中导出", "老师或审核人员可直接打开文档、表格、配音与整合报告")
        click_nav("outputs")

    def outro() -> None:
        window._switch_page("overview")
        overlay.show_step(
            "READY TO DELIVER",
            "译述 YISHU · Windows 完整版",
            "开箱即用、成果可追溯、支持在线智能体与离线演示，可直接用于课堂汇报和项目交付",
            centered=True,
        )

    steps = [
        intro,
        settings_demo,
        production_image,
        production_docx,
        production_audio,
        agent_demo,
        terms_demo,
        workflow_demo,
        showcase_demo,
        outputs_demo,
        outro,
    ]

    def start_tour() -> None:
        nonlocal started
        if started or not args.start_file.exists():
            return
        started = True
        watcher.stop()
        for offset, callback in zip(timings, steps, strict=False):
            QTimer.singleShot(round(offset * 1000), callback)
        QTimer.singleShot(round((timings[-1] + 17.0) * 1000), app.quit)

    def mark_ready() -> None:
        window.activateWindow()
        window.raise_()
        args.ready_file.write_text("ready", encoding="utf-8")

    watcher = QTimer()
    watcher.setInterval(100)
    watcher.timeout.connect(start_tour)
    watcher.start()
    QTimer.singleShot(1200, mark_ready)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
