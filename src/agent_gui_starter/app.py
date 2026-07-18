from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QEasingCurve, QObject, QPropertyAnimation, QSize, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .agent import AgentClient
from .config import load_config
from .coze import CozeWorkflowClient, CozeWorkflowError
from .integration import (
    GROUPS,
    CollaborationScan,
    GroupSummary,
    find_project_root,
    format_dashboard_markdown,
    format_size,
    format_terms_markdown,
    output_dir_for,
    load_terms,
    run_group_adapter,
    scan_collaboration,
    search_terms,
    write_integration_outputs,
)
from .production import (
    create_audio_review_from_transcript,
    extract_docx_to_review,
    refill_docx_from_review,
    synthesize_audio_from_review,
    translate_review_workbook,
    validate_c_docx_samples,
)
from .workflow import (
    StepResult,
    WorkflowResult,
    format_workflow_result,
    run_default_workflow,
    run_translation_integration_workflow,
)


SYSTEM_PROMPT = "你是译述的中国文化多模态外译助手。请给出准确、简洁、可执行的结果。"
GROUP_ACCENTS = {"A": "#3B6ED8", "B": "#0F9D8A", "C": "#E15D47"}
GROUP_ICONS = {"A": "image", "B": "languages", "C": "audio-lines"}
UI_FONT_FAMILY = "Noto Sans SC"
DISPLAY_FONT_FAMILY = "Noto Sans SC"
SIDEBAR_WIDTH = 224
_FONTS_CONFIGURED = False
PAGE_META = {
    "overview": ("开始", "从素材到译成品"),
    "production": ("翻译文件", "图片、Word 和音视频"),
    "agent": ("翻译文字", "快速翻译、精译与多模型精译"),
    "terms": ("查文化术语", "统一文化术语译法"),
    "workflow": ("批量处理", "一次处理多个素材"),
    "showcase": ("看完整成果", "查看完整能力与真实成品"),
    "outputs": ("找成品", "查看已生成的文件"),
}


def _resource_path(relative_path: str) -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    base_path = Path(bundled_root) if bundled_root else Path(__file__).resolve().parents[2]
    return base_path / relative_path


def configure_application_fonts(app: QApplication | None = None) -> None:
    global UI_FONT_FAMILY, DISPLAY_FONT_FAMILY, _FONTS_CONFIGURED
    if _FONTS_CONFIGURED:
        return
    _FONTS_CONFIGURED = True

    font_candidates = [
        _resource_path("assets/fonts/NotoSansSC-VF.ttf"),
        _resource_path("assets/fonts/NotoSerifSC-VF.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    loaded_families: list[str] = []
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    families = set(QFontDatabase.families()) | set(loaded_families)
    for preferred in (
        "Noto Sans SC",
        "Segoe UI Variable Text",
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans SC",
        "SimHei",
    ):
        if preferred in families:
            UI_FONT_FAMILY = preferred
            break
    DISPLAY_FONT_FAMILY = UI_FONT_FAMILY

    target_app = app or QApplication.instance()
    if target_app is not None:
        target_app.setFont(QFont(UI_FONT_FAMILY, 10))


def make_brand_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    padding = max(1, int(size * 0.045))
    border_pen = QPen(QColor("#DDD5C8"), max(1.0, size * 0.016))
    border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(border_pen)
    painter.setBrush(QColor("#FBF8F1"))
    painter.drawRoundedRect(
        padding,
        padding,
        size - padding * 2,
        size - padding * 2,
        max(4, int(size * 0.13)),
        max(4, int(size * 0.13)),
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    stroke = max(1.8, size * 0.072)

    # Paired Chinese corner quotes frame a single cross-language path.
    source_mark = QPainterPath()
    source_mark.moveTo(size * 0.44, size * 0.26)
    source_mark.lineTo(size * 0.25, size * 0.26)
    source_mark.lineTo(size * 0.25, size * 0.55)
    source_pen = QPen(QColor("#327568"), stroke)
    source_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    source_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(source_pen)
    painter.drawPath(source_mark)

    target_mark = QPainterPath()
    target_mark.moveTo(size * 0.56, size * 0.74)
    target_mark.lineTo(size * 0.75, size * 0.74)
    target_mark.lineTo(size * 0.75, size * 0.45)
    target_pen = QPen(QColor("#C86F4D"), stroke)
    target_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    target_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(target_pen)
    painter.drawPath(target_mark)

    flow = QPainterPath()
    flow.moveTo(size * 0.33, size * 0.61)
    flow.cubicTo(size * 0.43, size * 0.56, size * 0.52, size * 0.45, size * 0.67, size * 0.40)
    flow_pen = QPen(QColor("#587E91"), max(1.2, size * 0.036))
    flow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(flow_pen)
    painter.drawPath(flow)
    painter.drawLine(int(size * 0.60), int(size * 0.38), int(size * 0.67), int(size * 0.40))
    painter.drawLine(int(size * 0.63), int(size * 0.47), int(size * 0.67), int(size * 0.40))
    painter.end()
    return QIcon(pixmap)


def make_icon(
    name: str,
    color: str = "#667085",
    size: int = 32,
    selected_color: str | None = None,
) -> QIcon:
    icon_path = _resource_path(f"assets/icons/lucide/{name}.svg")
    if not icon_path.exists():
        return QIcon()

    try:
        source = icon_path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()

    def render(icon_color: str) -> QPixmap:
        renderer = QSvgRenderer(QByteArray(source.replace("currentColor", icon_color).encode("utf-8")))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        return pixmap

    icon = QIcon()
    icon.addPixmap(render(color), QIcon.Mode.Normal, QIcon.State.Off)
    if selected_color:
        selected = render(selected_color)
        icon.addPixmap(selected, QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.On)
    return icon


def add_surface_shadow(
    widget: QWidget,
    blur: int = 20,
    y_offset: int = 4,
    alpha: int = 24,
) -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(24, 30, 42, alpha))
    widget.setGraphicsEffect(shadow)
    return shadow


class GlassFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QColor(255, 255, 255, 242))
        painter.setBrush(QColor(255, 254, 251, 232))
        painter.drawRoundedRect(outer, 8, 8)
        inner = outer.adjusted(1, 1, -1, -1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(64, 78, 104, 30))
        painter.drawRoundedRect(inner, 7, 7)
        painter.end()
        super().paintEvent(event)  # type: ignore[arg-type]


class JobWorker(QObject):
    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, prompt: str, project_root: Path, title: str = "") -> None:
        super().__init__()
        self._mode = mode
        self._prompt = prompt
        self._project_root = project_root
        self._title = title

    @Slot()
    def run(self) -> None:
        try:
            config = load_config()

            if self._mode == "coze_workflow":
                self.progress.emit("正在执行扣子翻译工作流")
                response = CozeWorkflowClient(config).run(self._prompt, self._title)
                output = response.text
                if response.debug_url:
                    output += f"\n\n---\n扣子运行调试页：{response.debug_url}"
                self.finished.emit(output)
                return

            client = AgentClient(config)

            if self._mode == "production:image-translate":
                self.progress.emit("正在识别图片文字并生成中英对照")
                translation = client.translate_image(self._prompt)
                self.finished.emit(
                    json.dumps(
                        {
                            "kind": "image-translation",
                            "message": translation,
                            "artifacts": [],
                        },
                        ensure_ascii=False,
                    )
                )
                return

            if self._mode == "production:docx-extract":
                self.progress.emit("正在提取 DOCX 正文、表格与页眉页脚")
                result = extract_docx_to_review(self._prompt)
                self.finished.emit(result.to_payload("docx-review"))
                return

            if self._mode == "production:review-translate":
                self.progress.emit("正在按共享术语与儿童文学风格翻译")
                payload = json.loads(self._prompt)
                terms = load_terms(self._project_root)
                glossary = [
                    (str(item.get("术语", "")), str(item.get("英文翻译", "")))
                    for item in terms
                    if item.get("术语") and item.get("英文翻译")
                ]
                result = translate_review_workbook(
                    payload["review"],
                    lambda lines: client.translate_lines(lines, glossary),
                )
                self.finished.emit(result.to_payload(payload.get("target", "translated-review")))
                return

            if self._mode == "production:docx-refill":
                self.progress.emit("正在执行 Word XML 级译文回填")
                payload = json.loads(self._prompt)
                result = refill_docx_from_review(payload["source"], payload["review"])
                self.finished.emit(result.to_payload("refilled-docx"))
                return

            if self._mode == "production:audio-transcribe":
                self.progress.emit("正在识别音频并生成逐句审校表")
                transcript = client.transcribe_audio(self._prompt)
                result = create_audio_review_from_transcript(transcript, Path(self._prompt).name)
                self.finished.emit(result.to_payload("audio-review"))
                return

            if self._mode == "production:audio-synthesize":
                self.progress.emit("正在使用人工审核译文生成英文语音")
                result = synthesize_audio_from_review(self._prompt)
                self.finished.emit(result.to_payload("audio-output"))
                return

            if self._mode == "integration_workflow":
                result = run_translation_integration_workflow(
                    client,
                    self._prompt,
                    self._project_root,
                    self.progress.emit,
                )
                self.finished.emit(format_workflow_result(result))
                return

            if self._mode == "default_workflow":
                result = run_default_workflow(client, self._prompt, self.progress.emit)
                self.finished.emit(format_workflow_result(result))
                return

            if self._mode == "report":
                self.progress.emit("正在生成整合报告")
                scan = scan_collaboration(self._project_root)
                bundle = write_integration_outputs(scan, self._prompt)
                self.finished.emit(bundle.summary_markdown)
                return

            if self._mode == "terms":
                self.progress.emit("正在检索共享术语库")
                records = search_terms(self._prompt, self._project_root)
                self.finished.emit(format_terms_markdown(records))
                return

            if self._mode.startswith("adapter:"):
                group_key = self._mode.partition(":")[2]
                self.progress.emit(f"正在运行 {group_key} 组适配器")
                self.finished.emit(run_group_adapter(group_key, self._prompt, self._project_root))
                return

            self.progress.emit("正在调用智能体")
            response = client.run(SYSTEM_PROMPT, self._prompt)
            self.finished.emit(response.text)
        except Exception as exc:  # pragma: no cover - displayed in the GUI.
            self.failed.emit(str(exc))


class MarkdownView(QTextBrowser):
    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self._raw_text = ""
        self.setPlaceholderText(placeholder)
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        self.document().setDefaultStyleSheet(
            "h1 { color: #171a22; font-family: 'Noto Sans SC'; font-size: 22px; font-weight: 700; margin-bottom: 10px; }"
            "h2 { color: #222734; font-family: 'Noto Sans SC'; font-size: 17px; font-weight: 700; margin-top: 18px; }"
            "h3 { color: #465168; font-size: 14px; margin-top: 14px; }"
            "p, li { line-height: 1.55; }"
            "code { background: #eaf1ff; color: #245fcc; }"
            "table { border-collapse: collapse; }"
            "th { background: #eef2f8; font-weight: 600; }"
            "th, td { border: 1px solid #dce2eb; padding: 6px; }"
        )

    def set_output(self, text: str) -> None:
        self._raw_text = text.strip()
        self.setMarkdown(self._raw_text)
        self.moveCursor(self.textCursor().MoveOperation.Start)

    def raw_text(self) -> str:
        return self._raw_text


class StatCard(QFrame):
    def __init__(self, label: str, accent: str, icon_name: str) -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("accent", accent)
        self.setMinimumHeight(112)

        icon = QLabel()
        icon.setObjectName("StatIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(30, 30)
        icon.setPixmap(make_icon(icon_name, accent, 17).pixmap(17, 17))
        tone = QColor(accent)
        icon.setStyleSheet(
            f"background: rgba({tone.red()}, {tone.green()}, {tone.blue()}, 22); "
            f"border: 1px solid rgba({tone.red()}, {tone.green()}, {tone.blue()}, 32); "
            "border-radius: 6px;"
        )

        signal = QFrame()
        signal.setObjectName("StatSignal")
        signal.setFixedSize(30, 3)
        signal.setStyleSheet(f"background: {accent}; border: 0; border-radius: 1px;")

        self._value = QLabel("-")
        self._value.setObjectName("StatValue")
        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self._detail = QLabel("")
        self._detail.setObjectName("StatDetail")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(9)
        header.addWidget(icon)
        header.addWidget(self._label)
        header.addStretch(1)
        header.addWidget(signal, 0, Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(3)
        layout.addLayout(header)
        layout.addSpacing(2)
        layout.addWidget(self._value)
        layout.addWidget(self._detail)

    def update_value(self, value: str, detail: str) -> None:
        self._value.setText(value)
        self._detail.setText(detail)


class GroupCard(QFrame):
    open_requested = Signal(str)

    def __init__(self, group_key: str) -> None:
        super().__init__()
        self._group_key = group_key
        self.setObjectName("GroupCard")
        self.setMinimumHeight(228)

        accent = GROUP_ACCENTS[group_key]
        signal = QFrame()
        signal.setFixedSize(44, 3)
        signal.setStyleSheet(f"background: {accent}; border: 0; border-radius: 1px;")
        badge = QLabel()
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(34, 34)
        badge.setPixmap(make_icon(GROUP_ICONS[group_key], "#FFFFFF", 19).pixmap(19, 19))
        badge.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border: 0; border-radius: 7px;"
        )
        self._title = QLabel()
        self._title.setObjectName("GroupTitle")
        self._title.setWordWrap(True)
        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setMinimumWidth(72)
        self._status.setFixedHeight(25)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        title_layout.addWidget(self._title)
        self._subtitle = QLabel()
        self._subtitle.setObjectName("GroupSubtitle")
        title_layout.addWidget(self._subtitle)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(badge)
        top.addLayout(title_layout, 1)
        top.addWidget(self._status)

        self._description = QLabel()
        self._description.setObjectName("GroupDescription")
        self._description.setWordWrap(True)
        self._metrics = QLabel()
        self._metrics.setObjectName("GroupMetrics")
        self._categories = QLabel()
        self._categories.setObjectName("CategoryLine")
        self._categories.setWordWrap(True)

        open_button = QPushButton("查看交付")
        open_button.setObjectName("CardAction")
        open_button.setIcon(make_icon("external-link", "#167A65"))
        open_button.clicked.connect(lambda: self.open_requested.emit(self._group_key))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(10)
        layout.addWidget(signal)
        layout.addLayout(top)
        layout.addWidget(self._description)
        layout.addWidget(self._metrics)
        layout.addWidget(self._categories)
        layout.addStretch(1)
        layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)

    def update_summary(self, summary: GroupSummary) -> None:
        short_title = summary.name.partition("：")[2] or summary.name
        self._title.setText(short_title)
        self._subtitle.setText(f"{summary.key} 组协作区")
        self._description.setText(summary.description)
        self._metrics.setText(f"{summary.file_count} 个文件  ·  {format_size(summary.total_size_bytes)}")
        categories = sorted(summary.categories.items(), key=lambda item: (-item[1], item[0]))[:4]
        self._categories.setText("   ".join(f"{name} {count}" for name, count in categories) or "暂无分类资产")
        self._status.setText(summary.status)
        if summary.status == "可整合":
            self._status.setText("●  可整合")
            self._status.setStyleSheet(
                "background: transparent; color: #167A65; border: 0; font-weight: 650;"
            )
        else:
            self._status.setText(f"●  {summary.status}")
            self._status.setStyleSheet(
                "background: transparent; color: #A36724; border: 0; font-weight: 650;"
            )


class TaskEntryCard(QFrame):
    action_requested = Signal(str)

    def __init__(
        self,
        channel_icon: str,
        title: str,
        kicker: str,
        body: str,
        proof: str,
        primary_label: str,
        primary_action: str,
        secondary_label: str,
        secondary_action: str,
        accent: str,
    ) -> None:
        super().__init__()
        self.setObjectName("TaskEntryCard")
        self.setMinimumHeight(218)
        self._shadow = add_surface_shadow(self, blur=16, y_offset=3, alpha=18)
        self._shadow_animation = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._shadow_animation.setDuration(180)
        self._shadow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        signal = QFrame()
        signal.setFixedSize(46, 3)
        signal.setStyleSheet(f"background: {accent}; border: 0; border-radius: 1px;")

        badge_label = QLabel()
        badge_label.setObjectName("TaskBadge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_label.setFixedSize(42, 42)
        badge_label.setPixmap(make_icon(channel_icon, "#FFFFFF", 23).pixmap(23, 23))
        badge_label.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border-radius: 7px;"
        )

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        kicker_label = QLabel(kicker)
        kicker_label.setObjectName("TaskKicker")
        title_label = QLabel(title)
        title_label.setObjectName("TaskTitle")
        title_label.setWordWrap(True)
        title_box.addWidget(kicker_label)
        title_box.addWidget(title_label)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(badge_label)
        header.addLayout(title_box, 1)

        body_label = QLabel(body)
        body_label.setObjectName("TaskBody")
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        proof_label = QLabel(proof)
        proof_label.setObjectName("TaskProof")
        proof_tone = QColor(accent)
        proof_label.setStyleSheet(
            f"background: rgba({proof_tone.red()}, {proof_tone.green()}, {proof_tone.blue()}, 15); "
            f"color: {accent}; border: 1px solid rgba({proof_tone.red()}, {proof_tone.green()}, {proof_tone.blue()}, 30); "
            "border-radius: 6px; padding: 5px 8px; font-size: 10px; font-weight: 700;"
        )

        primary = QPushButton(primary_label)
        primary.setObjectName("TaskPrimary")
        primary_icon = (
            "play"
            if primary_action.startswith(("agent:", "workflow:", "adapter:"))
            else "external-link"
        )
        primary.setIcon(make_icon(primary_icon, "#FFFFFF"))
        primary.clicked.connect(lambda: self.action_requested.emit(primary_action))
        secondary = QToolButton()
        secondary.setObjectName("TaskSecondaryIcon")
        secondary_icon = {
            "page:terms": "book-open",
            "page:outputs": "package-check",
        }.get(secondary_action, "route")
        secondary.setIcon(make_icon(secondary_icon, "#334155"))
        secondary.setIconSize(QSize(17, 17))
        secondary.setFixedSize(38, 38)
        secondary.setToolTip(secondary_label)
        secondary.setAccessibleName(secondary_label)
        secondary.clicked.connect(lambda: self.action_requested.emit(secondary_action))

        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addWidget(primary, 1)
        actions.addWidget(secondary)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(signal)
        layout.addLayout(header)
        layout.addWidget(body_label, 1)
        layout.addWidget(proof_label)
        layout.addLayout(actions)

    def enterEvent(self, event: object) -> None:
        self._animate_shadow(26)
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: object) -> None:
        self._animate_shadow(16)
        super().leaveEvent(event)  # type: ignore[arg-type]

    def _animate_shadow(self, target_blur: float) -> None:
        self._shadow_animation.stop()
        self._shadow_animation.setStartValue(self._shadow.blurRadius())
        self._shadow_animation.setEndValue(target_blur)
        self._shadow_animation.start()


class StartDropZone(QFrame):
    select_requested = Signal()
    files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("StartDropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(250)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("选择或拖入待翻译文件")

        icon = QLabel()
        icon.setObjectName("DropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(58, 58)
        icon.setPixmap(make_icon("folder-open", "#5D8FA4", 27).pixmap(27, 27))

        title = QLabel("把素材放进来，从这里开始")
        title.setObjectName("DropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("自动识别图片、Word、音频和视频")
        subtitle.setObjectName("DropSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        browse = QPushButton("选择素材")
        browse.setObjectName("DropBrowseButton")
        browse.setIcon(make_icon("plus", "#FFFFFF", 17))
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self.select_requested.emit)

        formats = QLabel("JPG  ·  PNG  ·  DOCX  ·  MP3  ·  WAV  ·  MP4")
        formats.setObjectName("DropFormats")
        formats.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addWidget(browse, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(formats)
        layout.addStretch(1)

    def dragEnterEvent(self, event: object) -> None:
        mime = event.mimeData()  # type: ignore[attr-defined]
        if mime.hasUrls():
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()  # type: ignore[attr-defined]

    def dragLeaveEvent(self, event: object) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)  # type: ignore[arg-type]

    def dropEvent(self, event: object) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]  # type: ignore[attr-defined]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()  # type: ignore[attr-defined]

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
            self.select_requested.emit()
        super().mousePressEvent(event)  # type: ignore[arg-type]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        configure_application_fonts(QApplication.instance())
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._active_mode = "dashboard"
        self._active_group = "A"
        self._current_page_key = "overview"
        self._config = load_config()
        self._project_root = find_project_root()
        self._scan = scan_collaboration(self._project_root)
        self._busy_controls: list[QPushButton | QToolButton] = []
        self._nav_buttons: dict[str, QPushButton] = {}
        self._group_nav_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._page_animation: QPropertyAnimation | None = None
        self._animated_page: QWidget | None = None
        self._reveal_animations: dict[QWidget, QPropertyAnimation] = {}

        self.setWindowTitle(self._config.app_name)
        self.setWindowIcon(make_brand_icon())
        self.setMinimumSize(1080, 720)
        self.resize(1440, 900)
        self._build_ui()
        self._apply_styles()
        self._configure_interactions()
        self._install_shortcuts()
        self._refresh_from_scan()
        QTimer.singleShot(100, self._animate_overview_intro)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        shell.addWidget(self._build_workspace(), 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        status.showMessage("已准备好，可以选择文件开始")

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        logo = QLabel()
        logo.setPixmap(make_brand_icon(46).pixmap(46, 46))
        logo.setFixedSize(46, 46)
        brand_title = QLabel("译述")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("YISHU · CULTURE STUDIO")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(1)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addWidget(logo)
        brand.addLayout(brand_text, 1)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 23, 18, 17)
        layout.setSpacing(8)
        layout.addLayout(brand)
        brand_rule = QFrame()
        brand_rule.setObjectName("SidebarRule")
        brand_rule.setFixedHeight(1)
        layout.addSpacing(18)
        layout.addWidget(brand_rule)
        layout.addSpacing(14)
        layout.addWidget(self._sidebar_label("工作台"))

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        nav_items = [
            ("overview", "开始", "layout-dashboard"),
            ("production", "翻译文件", "clipboard-check"),
            ("agent", "翻译文字", "bot"),
            ("terms", "文化术语", "book-open"),
            ("workflow", "批量处理", "route"),
            ("showcase", "成果总览", "circle-check"),
            ("outputs", "导出文件", "package-check"),
        ]
        for key, text, icon_name in nav_items:
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(make_icon(icon_name, "#73877F", selected_color="#C86F4D"))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, page=key: self._switch_page(page))
            self._nav_group.addButton(button)
            self._nav_buttons[key] = button
            layout.addWidget(button)

        self._nav_buttons["overview"].setChecked(True)
        layout.addStretch(1)
        connection = QFrame()
        connection.setObjectName("ConnectionPanel")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(13, 12, 13, 12)
        connection_layout.setSpacing(4)
        channel_kicker = QLabel("当前环境")
        channel_kicker.setObjectName("ChannelKicker")
        self._api_state = QLabel()
        self._api_state.setObjectName("ApiState")
        self._model_label = QLabel(self._config.openai_model)
        self._model_label.setObjectName("ModelLabel")
        self._model_label.setWordWrap(True)
        connection_layout.addWidget(channel_kicker)
        connection_layout.addWidget(self._api_state)
        connection_layout.addWidget(self._model_label)
        layout.addWidget(connection)
        return sidebar

    def _sidebar_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SidebarLabel")
        return label

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("Workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_topbar())

        self._progress = QProgressBar()
        self._progress.setObjectName("TaskProgress")
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(3)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        self._pages = {
            "overview": self._build_overview_page(),
            "production": self._build_production_page(),
            "agent": self._build_agent_page(),
            "terms": self._build_terms_page(),
            "workflow": self._build_workflow_page(),
            "showcase": self._build_showcase_page(),
            "outputs": self._build_outputs_page(),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)
        layout.addWidget(self._stack, 1)
        return workspace

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(74)

        self._page_title = QLabel(PAGE_META["overview"][0])
        self._page_title.setObjectName("TopContext")
        self._page_subtitle = QLabel(PAGE_META["overview"][1])
        self._page_subtitle.setObjectName("PageSubtitle")
        context = QVBoxLayout()
        context.setContentsMargins(0, 0, 0, 0)
        context.setSpacing(1)
        context.addWidget(self._page_title)
        context.addWidget(self._page_subtitle)

        self._scan_button = QToolButton()
        self._scan_button.setObjectName("TopIconButton")
        self._scan_button.setIcon(make_icon("refresh-cw"))
        self._scan_button.setIconSize(QSize(18, 18))
        self._scan_button.setToolTip("刷新文件列表")
        self._scan_button.clicked.connect(self._scan_now)

        output_button = QToolButton()
        output_button.setObjectName("TopIconButton")
        output_button.setIcon(make_icon("folder-open"))
        output_button.setIconSize(QSize(18, 18))
        output_button.setToolTip("打开成品文件夹")
        output_button.clicked.connect(self._open_output_dir)

        self._top_run_button = QPushButton("导入素材")
        self._top_run_button.setObjectName("TopPrimaryButton")
        self._top_run_button.setIcon(make_icon("plus", "#FFFFFF"))
        self._top_run_button.clicked.connect(lambda: self._choose_start_file())
        self._busy_controls.extend([self._scan_button, self._top_run_button])

        actions = QHBoxLayout()
        actions.setSpacing(7)
        actions.addWidget(self._scan_button)
        actions.addWidget(output_button)
        actions.addWidget(self._top_run_button)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.addLayout(context)
        layout.addStretch(1)
        layout.addLayout(actions)
        return topbar

    def _build_overview_page(self) -> QWidget:
        content = QWidget()
        content.setObjectName("StartContent")
        content.setMaximumWidth(1160)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 34, 40, 40)
        layout.setSpacing(16)

        intro_panel = QFrame()
        intro_panel.setObjectName("IntroPanel")
        intro_layout = QHBoxLayout(intro_panel)
        intro_layout.setContentsMargins(0, 0, 0, 0)
        intro_layout.setSpacing(34)

        intro_copy = QVBoxLayout()
        intro_copy.setContentsMargins(0, 6, 0, 6)
        intro_copy.setSpacing(10)
        eyebrow = QLabel("YISHU · CULTURE TRANSLATION STUDIO")
        eyebrow.setObjectName("StartEyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title = QLabel("译文字，\n也译语境")
        title.setObjectName("StartTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setWordWrap(True)
        subtitle = QLabel("图像、Word、音视频与文化术语，在同一条可审校流程中完成提取、翻译与交付。")
        subtitle.setObjectName("StartSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle.setWordWrap(True)
        intro_copy.addWidget(eyebrow)
        intro_copy.addWidget(title)
        intro_copy.addWidget(subtitle)

        facts = QHBoxLayout()
        facts.setSpacing(14)
        for value, label in (("251", "文化术语"), ("18", "工作流节点"), ("5/5", "DOCX 实测")):
            fact = QFrame()
            fact.setObjectName("HeroFact")
            fact_layout = QVBoxLayout(fact)
            fact_layout.setContentsMargins(0, 0, 0, 0)
            fact_layout.setSpacing(0)
            value_label = QLabel(value)
            value_label.setObjectName("HeroFactValue")
            caption = QLabel(label)
            caption.setObjectName("HeroFactLabel")
            fact_layout.addWidget(value_label)
            fact_layout.addWidget(caption)
            facts.addWidget(fact)
        facts.addStretch(1)
        intro_copy.addSpacing(8)
        intro_copy.addLayout(facts)
        self._hero_reveal_widgets = (eyebrow, title, subtitle)

        self._start_drop_zone = StartDropZone()
        self._start_drop_zone.setMinimumHeight(282)
        self._start_drop_zone.select_requested.connect(self._choose_start_file)
        self._start_drop_zone.files_dropped.connect(self._handle_start_drop)
        add_surface_shadow(self._start_drop_zone, blur=28, y_offset=8, alpha=16)
        intro_layout.addLayout(intro_copy, 5)
        intro_layout.addWidget(self._start_drop_zone, 6)
        layout.addWidget(intro_panel)

        choice_label = QLabel("选择一种任务")
        choice_label.setObjectName("ChoiceLabel")
        choice_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(choice_label)

        choices = QGridLayout()
        choices.setSpacing(10)
        for index, (text, icon_name, kind, accent, color) in enumerate((
            ("翻译图片\n识别图中文字并生成英文", "image", "image", "coral", "#D97955"),
            ("翻译 Word\n保留原版式导出英文文档", "file-text", "docx", "blue", "#5B83B8"),
            ("翻译音视频\n生成审校表与英文配音", "audio-lines", "audio", "jade", "#3E8D7B"),
        )):
            button = QPushButton(text)
            button.setObjectName("QuickStartButton")
            button.setProperty("accent", accent)
            button.setIcon(make_icon(icon_name, color, 19))
            button.setIconSize(QSize(19, 19))
            button.clicked.connect(lambda checked=False, target=kind: self._choose_start_file(target))
            choices.addWidget(button, index // 2, index % 2)
        text_button = QPushButton("翻译文字\n粘贴内容直接得到英文")
        text_button.setObjectName("QuickStartButton")
        text_button.setProperty("accent", "gold")
        text_button.setIcon(make_icon("languages", "#9B7A45", 19))
        text_button.setIconSize(QSize(19, 19))
        text_button.clicked.connect(lambda: self._open_text_translation())
        choices.addWidget(text_button, 1, 1)
        choices.setColumnStretch(0, 1)
        choices.setColumnStretch(1, 1)
        layout.addLayout(choices)

        outcome = QFrame()
        outcome.setObjectName("OutcomeBand")
        outcome_layout = QHBoxLayout(outcome)
        outcome_layout.setContentsMargins(18, 11, 18, 11)
        outcome_layout.setSpacing(14)
        outcome_title = QLabel("交付内容")
        outcome_title.setObjectName("OutcomeTitle")
        outcome_layout.addWidget(outcome_title)
        for icon_name, text, color in (
            ("clipboard-check", "中英审校表", "#3E8D7B"),
            ("file-text", "保留版式的 Word", "#5B83B8"),
            ("audio-lines", "可播放英文配音", "#846FA9"),
            ("package-check", "完整验收记录", "#D97955"),
        ):
            item = QLabel(text)
            item.setObjectName("OutcomeItem")
            item_layout = QHBoxLayout()
            icon_label = QLabel()
            icon_label.setPixmap(make_icon(icon_name, color, 15).pixmap(15, 15))
            item_layout.addWidget(icon_label)
            item_layout.addWidget(item)
            outcome_layout.addLayout(item_layout)
        outcome_layout.addStretch(1)
        layout.addWidget(outcome)

        first_time = QFrame()
        first_time.setObjectName("FirstTimePanel")
        first_layout = QHBoxLayout(first_time)
        first_layout.setContentsMargins(22, 16, 22, 16)
        first_layout.setSpacing(18)
        sample_text = QVBoxLayout()
        sample_text.setSpacing(4)
        sample_title = QLabel("不知道从哪里开始？先看一个完整示例")
        sample_title.setObjectName("SampleTitle")
        sample_description = QLabel("点开就能看到原文、译文、Word 版式和英文配音，不需要先配置密钥。")
        sample_description.setObjectName("SampleDescription")
        sample_description.setWordWrap(True)
        sample_button = QPushButton("立即体验示例")
        sample_button.setObjectName("SampleButton")
        sample_button.setIcon(make_icon("play", "#C96F4B", 16))
        sample_button.clicked.connect(self._open_beginner_example)
        sample_text.addWidget(sample_title)
        sample_text.addWidget(sample_description)
        sample_text.addWidget(sample_button, 0, Qt.AlignmentFlag.AlignLeft)
        first_layout.addLayout(sample_text, 1)

        pages_root = (
            self._project_root
            / "collaboration/groups/A_image_translation/deliverables/extracted_20260717_update/"
            "validation/rendered_pages"
        )
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)
        for page_no in (1, 7, 14):
            preview = QLabel()
            preview.setObjectName("StartPreviewPage")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setFixedSize(68, 82)
            pixmap = QPixmap(str(pages_root / f"page_{page_no:02d}.png"))
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaled(
                        62,
                        76,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            preview_row.addWidget(preview)
        first_layout.addLayout(preview_row)
        layout.addWidget(first_time)

        steps = QFrame()
        steps.setObjectName("SimpleSteps")
        steps_layout = QHBoxLayout(steps)
        steps_layout.setContentsMargins(20, 16, 20, 16)
        steps_layout.setSpacing(10)
        for index, (step_title, detail) in enumerate(
            (
                ("选择素材", "拖进来，或从电脑选择"),
                ("确认译文", "术语、语气和格式已整理"),
                ("拿到成品", "下载 Word、表格或英文音频"),
            ),
            start=1,
        ):
            number = QLabel(str(index))
            number.setObjectName("SimpleStepNumber")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setFixedSize(26, 26)
            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(1)
            step_label = QLabel(step_title)
            step_label.setObjectName("SimpleStepTitle")
            detail_label = QLabel(detail)
            detail_label.setObjectName("SimpleStepDetail")
            text_box.addWidget(step_label)
            text_box.addWidget(detail_label)
            steps_layout.addWidget(number)
            steps_layout.addLayout(text_box, 1)
            if index < 3:
                arrow = QLabel()
                arrow.setPixmap(make_icon("arrow-right", "#A3AAA5", 16).pixmap(16, 16))
                steps_layout.addWidget(arrow)
        layout.addWidget(steps)
        layout.addStretch(1)

        self._group_cards = {}
        self._overview_layout_mode = 1
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll

        content = QWidget()
        content.setObjectName("OverviewContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 34)
        layout.setSpacing(20)

        layout.addWidget(self._overview_hero_panel())
        layout.addWidget(self._overview_readiness_band())

        entry_row = QHBoxLayout()
        entry_text = QVBoxLayout()
        entry_text.setSpacing(3)
        entry_text.addWidget(self._section_title("选择素材类型"))
        self._scan_time_label = QLabel()
        self._scan_time_label.setObjectName("SectionSubtitle")
        entry_text.addWidget(self._scan_time_label)
        entry_row.addLayout(entry_text)
        entry_row.addStretch(1)
        self._report_button = self._icon_button("file-text", "生成整合报告")
        self._report_button.clicked.connect(
            lambda: self._start_job("report", self._workflow_input.toPlainText(), allow_empty=True)
        )
        self._busy_controls.append(self._report_button)
        entry_row.addWidget(self._report_button)
        layout.addLayout(entry_row)

        self._task_grid = QGridLayout()
        self._task_grid.setHorizontalSpacing(12)
        self._task_grid.setVerticalSpacing(12)
        self._task_cards = (
            TaskEntryCard(
                "scan-text",
                "图片与图文",
                "识别图片文字 / 保留版式",
                "图片文字审校、替换，并回填到原版式文档。",
                "71 条审校  ·  17 页  ·  31 媒体",
                "处理图文",
                "production:images",
                "查看完整资源",
                "production:resources",
                GROUP_ACCENTS["A"],
            ),
            TaskEntryCard(
                "languages",
                "文字翻译",
                "文化术语 / 儿童文学风格",
                "使用统一术语译法和儿童文学风格生成译文。",
                "251 条术语  ·  40 条官方语料",
                "翻译文字",
                "agent:coze",
                "打开术语库",
                "page:terms",
                GROUP_ACCENTS["B"],
            ),
            TaskEntryCard(
                "file-text",
                "Word 文档",
                "正文 / 表格 / 页眉页脚",
                "提取正文、表格、页眉页脚，审核后保留版式回填。",
                "5/5 套实测  ·  失败 XML 0",
                "处理 Word",
                "production:docx",
                "查看资源库",
                "production:resources",
                GROUP_ACCENTS["C"],
            ),
            TaskEntryCard(
                "audio-lines",
                "音视频",
                "语音识别 / 英文配音",
                "识别、分句、翻译并生成可播放英文配音。",
                "219 句  ·  WAV  ·  文本  ·  二维码",
                "处理音视频",
                "production:audio",
                "交付中心",
                "page:outputs",
                "#7559C7",
            ),
        )
        for card in self._task_cards:
            card.action_requested.connect(self._handle_task_action)
        layout.addLayout(self._task_grid)

        layout.addWidget(self._section_title("当前可用资源"))

        self._stats_grid = QGridLayout()
        self._stats_grid.setHorizontalSpacing(12)
        self._stats_grid.setVerticalSpacing(12)
        self._stat_ready = StatCard("生产通道", "#0F9D8A", "circle-check")
        self._stat_assets = StatCard("资源文件", "#3B6ED8", "files")
        self._stat_terms = StatCard("文化术语", "#E15D47", "library")
        self._stat_outputs = StatCard("已生成输出", "#7559C7", "package-check")
        self._stat_cards = (self._stat_ready, self._stat_assets, self._stat_terms, self._stat_outputs)
        layout.addLayout(self._stats_grid)

        self._group_cards: dict[str, GroupCard] = {}

        lower = QHBoxLayout()
        lower.setSpacing(12)
        workflow_panel = self._overview_workflow_panel()
        advice_panel = self._overview_advice_panel()
        lower.addWidget(workflow_panel, 3)
        lower.addWidget(advice_panel, 2)
        layout.addLayout(lower)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self._overview_layout_mode = -1
        self._relayout_overview(4, 3)
        return scroll

    def _overview_readiness_band(self) -> QWidget:
        band = GlassFrame()
        band.setObjectName("ReadinessBand")
        band.setMinimumHeight(78)
        add_surface_shadow(band, blur=18, y_offset=4, alpha=18)

        score_box = QVBoxLayout()
        score_box.setContentsMargins(0, 0, 0, 0)
        score_box.setSpacing(0)
        score_label = QLabel("运行检查")
        score_label.setObjectName("ReadinessLabel")
        score_value = QLabel("全部通过")
        score_value.setObjectName("ReadinessValue")
        score_box.addWidget(score_label)
        score_box.addWidget(score_value)

        divider = QFrame()
        divider.setObjectName("ReadinessDivider")
        divider.setFixedWidth(1)

        evidence_box = QVBoxLayout()
        evidence_box.setContentsMargins(0, 0, 0, 0)
        evidence_box.setSpacing(2)
        evidence_title = QLabel("示例与资料已准备好")
        evidence_title.setObjectName("ReadinessTitle")
        evidence = QLabel("71 条图文审校清单 · 文化术语与风格约束 · 5 套 DOCX · 音频、表格与二维码样例")
        evidence.setObjectName("ReadinessSummary")
        evidence.setWordWrap(True)
        evidence_box.addWidget(evidence_title)
        evidence_box.addWidget(evidence)

        pending = QLabel("可以开始")
        pending.setObjectName("ReadinessPending")
        pending.setAlignment(Qt.AlignmentFlag.AlignCenter)

        open_record = self._icon_button("clipboard-check", "打开完整验收记录")
        open_record.clicked.connect(self._open_acceptance_record)

        layout = QHBoxLayout(band)
        layout.setContentsMargins(18, 13, 14, 13)
        layout.setSpacing(16)
        layout.addLayout(score_box)
        layout.addWidget(divider)
        layout.addLayout(evidence_box, 1)
        layout.addWidget(pending)
        layout.addWidget(open_record)
        return band

    def _overview_hero_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("HeroPanel")
        panel.setMinimumHeight(266)
        add_surface_shadow(panel, blur=28, y_offset=7, alpha=34)

        eyebrow = QLabel("CULTURE TRANSLATE · MULTIMODAL WORKBENCH")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("译述：多模态外译工作台")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel(
            "统一接入图文回填、术语风格、DOCX 与音视频翻译。"
            "从素材导入、机器翻译和人工审校，到文档回填、配音与最终交付都在一个工作区完成。"
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        self._hero_reveal_widgets = (eyebrow, title, subtitle)

        run_button = QPushButton("开始翻译")
        run_button.setObjectName("HeroPrimary")
        run_button.setIcon(make_icon("play", "#FFFFFF"))
        run_button.clicked.connect(lambda: self._switch_page("production"))
        outputs_button = QToolButton()
        outputs_button.setObjectName("HeroIconButton")
        outputs_button.setIcon(make_icon("package-check", "#E6ECE8"))
        outputs_button.setIconSize(QSize(18, 18))
        outputs_button.setFixedSize(42, 42)
        outputs_button.setToolTip("查看交付中心")
        outputs_button.setAccessibleName("查看交付中心")
        outputs_button.clicked.connect(lambda: self._switch_page("outputs"))

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(run_button)
        actions.addWidget(outputs_button)
        actions.addStretch(1)

        channel_row = QHBoxLayout()
        channel_row.setSpacing(7)
        for channel in ("图文回填", "术语风格", "DOCX", "音视频"):
            channel_label = QLabel(channel)
            channel_label.setObjectName("HeroPill")
            channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            channel_row.addWidget(channel_label)
        channel_row.addStretch(1)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        left.addWidget(eyebrow)
        left.addWidget(title)
        left.addWidget(subtitle)
        left.addLayout(channel_row)
        left.addStretch(1)
        left.addLayout(actions)

        status_panel = QFrame()
        status_panel.setObjectName("HeroStatusPanel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(17, 16, 17, 15)
        status_layout.setSpacing(9)

        preview_header = QHBoxLayout()
        status_title = QLabel("真实成品预览")
        status_title.setObjectName("HeroStatusTitle")
        preview_proof = QLabel("17 PAGES  ·  REVIEWED")
        preview_proof.setObjectName("HeroPreviewProof")
        preview_header.addWidget(status_title)
        preview_header.addStretch(1)
        preview_header.addWidget(preview_proof)
        status_layout.addLayout(preview_header)

        preview_strip = QHBoxLayout()
        preview_strip.setSpacing(8)
        pages_root = (
            self._project_root
            / "collaboration/groups/A_image_translation/deliverables/extracted_20260717_update/"
            "validation/rendered_pages"
        )
        for page_no in (1, 7, 14):
            preview = QLabel()
            preview.setObjectName("HeroPreviewPage")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setFixedSize(86, 100)
            page_path = pages_root / f"page_{page_no:02d}.png"
            pixmap = QPixmap(str(page_path))
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaled(
                        80,
                        94,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                preview.setText(f"P{page_no:02d}")
            preview_strip.addWidget(preview)
        preview_strip.addStretch(1)
        status_layout.addLayout(preview_strip)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(12)
        status_grid.setVerticalSpacing(6)
        self._hero_status_labels: list[QLabel] = []
        for index in range(4):
            label = QLabel()
            label.setObjectName("HeroStatusItem")
            label.setWordWrap(True)
            self._hero_status_labels.append(label)
            status_grid.addWidget(label, index // 2, index % 2)
        status_layout.addLayout(status_grid)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(30, 27, 27, 25)
        layout.setSpacing(28)
        layout.addLayout(left, 5)
        layout.addWidget(status_panel, 4)
        return panel

    def _overview_workflow_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SectionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 17, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section_title("整合链路"))
        stages = [
            ("library", "统一术语约束", "文化术语与风格规则自动参与翻译"),
            ("scan-text", "提取与智能翻译", "图文、文本、DOCX 与音视频统一处理"),
            ("clipboard-check", "人工审校与回填", "Excel 审校后回填文档或生成配音"),
            ("package-check", "生成最终交付", "输出文档、表格、音频与验收报告"),
        ]
        for icon_name, title, detail in stages:
            row = QHBoxLayout()
            badge = QLabel()
            badge.setObjectName("StageBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(34, 28)
            badge.setPixmap(make_icon(icon_name, "#2F6FED", 17).pixmap(17, 17))
            texts = QVBoxLayout()
            texts.setSpacing(0)
            title_label = QLabel(title)
            title_label.setObjectName("StageTitle")
            detail_label = QLabel(detail)
            detail_label.setObjectName("StageDetail")
            texts.addWidget(title_label)
            texts.addWidget(detail_label)
            state = QLabel("就绪")
            state.setObjectName("ReadyText")
            row.addWidget(badge)
            row.addLayout(texts, 1)
            row.addWidget(state)
            layout.addLayout(row)
        return panel

    def _overview_advice_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SectionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 17, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(self._section_title("接手结论"))
        self._advice_labels: list[QLabel] = []
        for index in range(3):
            label = QLabel()
            label.setObjectName("AdviceItem")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._advice_labels.append(label)
            layout.addWidget(label)
            if index < 2:
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setObjectName("Divider")
                layout.addWidget(divider)
        layout.addStretch(1)
        return panel

    def _build_production_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ProductionPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 28)
        layout.setSpacing(14)

        intro = QFrame()
        intro.setObjectName("SectionPanel")
        intro_layout = QHBoxLayout(intro)
        intro_layout.setContentsMargins(17, 14, 17, 14)
        intro_text = QVBoxLayout()
        intro_text.setSpacing(9)
        intro_text.addWidget(self._section_title("按顺序完成这四步"))
        stage_row = QHBoxLayout()
        stage_row.setSpacing(7)
        for index, stage_text in enumerate(("选择素材", "自动处理", "人工确认", "生成成品"), start=1):
            stage = QFrame()
            stage.setObjectName("ProductionStage")
            stage_layout = QHBoxLayout(stage)
            stage_layout.setContentsMargins(8, 6, 10, 6)
            stage_layout.setSpacing(6)
            stage_number = QLabel(str(index))
            stage_number.setObjectName("ProductionStageNumber")
            stage_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stage_number.setFixedSize(20, 20)
            stage_label = QLabel(stage_text)
            stage_label.setObjectName("ProductionStageLabel")
            stage_layout.addWidget(stage_number)
            stage_layout.addWidget(stage_label)
            stage_row.addWidget(stage)
            if index < 4:
                arrow = QLabel()
                arrow.setPixmap(make_icon("chevron-right", "#A1A8B5", 14).pixmap(14, 14))
                stage_row.addWidget(arrow)
        stage_row.addStretch(1)
        intro_text.addLayout(stage_row)
        intro_layout.addLayout(intro_text, 1)
        example_button = QPushButton("打开示例任务")
        example_button.setObjectName("SecondaryButton")
        example_button.setIcon(make_icon("clipboard-check", "#4F8274"))
        example_button.clicked.connect(self._load_production_example)
        intro_layout.addWidget(example_button)
        layout.addWidget(intro)

        self._production_tabs = QTabWidget()
        self._production_tabs.setObjectName("ResultTabs")

        image_tab = QWidget()
        image_layout = QVBoxLayout(image_tab)
        image_layout.setContentsMargins(16, 16, 16, 16)
        image_layout.setSpacing(14)
        image_source_row = QHBoxLayout()
        image_source_row.setSpacing(8)
        image_source_label = QLabel("选择图片")
        image_source_label.setObjectName("InfoLabel")
        image_source_label.setFixedWidth(72)
        self._image_source = QLineEdit()
        self._image_source.setObjectName("SearchInput")
        self._image_source.setPlaceholderText("选择 JPG、PNG 或 WebP 图片")
        image_browse = self._icon_button("folder-open", "选择图片")
        image_browse.clicked.connect(
            lambda: self._browse_into(
                self._image_source,
                "选择图片",
                "图片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)",
            )
        )
        self._image_translate_button = QPushButton("识别并翻译图片")
        self._image_translate_button.setObjectName("PrimaryButton")
        self._image_translate_button.setIcon(make_icon("languages", "#FFFFFF"))
        self._image_translate_button.clicked.connect(self._run_image_translate)
        self._busy_controls.append(self._image_translate_button)
        image_source_row.addWidget(image_source_label)
        image_source_row.addWidget(self._image_source, 1)
        image_source_row.addWidget(image_browse)
        image_source_row.addWidget(self._image_translate_button)
        image_layout.addLayout(image_source_row)

        image_body = QHBoxLayout()
        image_body.setSpacing(18)
        image_delivery = (
            self._project_root
            / "collaboration/groups/A_image_translation/deliverables/extracted_20260717_update"
        )
        pages_preview_path = image_delivery / "previews/final_docx_pages_contact_sheet.jpg"
        gallery = QFrame()
        gallery.setObjectName("ProductionGallery")
        gallery.setMinimumSize(520, 250)
        gallery_layout = QHBoxLayout(gallery)
        gallery_layout.setContentsMargins(20, 16, 20, 16)
        gallery_layout.setSpacing(14)
        pages_root = image_delivery / "validation/rendered_pages"
        for page_no in (1, 7, 14):
            page_box = QVBoxLayout()
            page_box.setSpacing(6)
            page_preview = QLabel()
            page_preview.setObjectName("ProductionGalleryPage")
            page_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_preview.setFixedSize(140, 194)
            page_path = pages_root / f"page_{page_no:02d}.png"
            page_pixmap = QPixmap(str(page_path))
            if not page_pixmap.isNull():
                page_preview.setPixmap(
                    page_pixmap.scaled(
                        132,
                        186,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            page_label = QLabel(f"P{page_no:02d}")
            page_label.setObjectName("ProductionPageLabel")
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_box.addWidget(page_preview)
            page_box.addWidget(page_label)
            gallery_layout.addLayout(page_box)
        gallery_layout.addStretch(1)
        self._image_preview = gallery
        image_body.addWidget(gallery, 3)
        image_details = QVBoxLayout()
        image_details.setSpacing(10)
        image_details.addWidget(self._section_title("图中文字翻译与版面回填成品"))
        image_caption = QLabel(
            "已完成 71 条图中文字审校，31 个嵌入媒体保持结构一致，"
            "其中 10 个 SVG 保持可编辑文本；最终 Word 共 17 页并完成逐页渲染检查。"
        )
        image_caption.setObjectName("SectionSubtitle")
        image_caption.setWordWrap(True)
        image_details.addWidget(image_caption)
        for text, icon_name, path in (
            (
                "打开最终图文成品",
                "file-text",
                image_delivery / "final_outputs/翻译资源编写-中国文化知识百科_A组更新完整修正版.docx",
            ),
            (
                "打开 71 条审校清单",
                "clipboard-check",
                image_delivery / "manifests/translation_manifest_reviewed.xlsx",
            ),
            ("查看 17 页预览", "image", pages_preview_path),
        ):
            button = QPushButton(text)
            button.setObjectName("SecondaryButton")
            button.setIcon(make_icon(icon_name, "#4F8274"))
            button.clicked.connect(lambda checked=False, target=path: self._open_known_path(target))
            image_details.addWidget(button)
        image_details.addStretch(1)
        image_body.addLayout(image_details, 2)
        image_layout.addLayout(image_body, 1)
        self._production_tabs.addTab(image_tab, "图片")

        document_tab = QWidget()
        document_layout = QVBoxLayout(document_tab)
        document_layout.setContentsMargins(16, 16, 16, 16)
        document_layout.setSpacing(13)
        document_layout.addWidget(self._section_title("翻译 Word 文档，并保留原来的版式"))
        self._docx_source = QLineEdit()
        self._docx_source.setObjectName("SearchInput")
        self._docx_source.setPlaceholderText("选择需要翻译的 Word 文档")
        source_browse = self._icon_button("folder-open", "选择 DOCX")
        source_browse.clicked.connect(
            lambda: self._browse_into(self._docx_source, "选择 DOCX", "Word 文档 (*.docx)")
        )
        document_layout.addLayout(self._picker_row("原始 Word", self._docx_source, source_browse))

        self._docx_review = QLineEdit()
        self._docx_review.setObjectName("SearchInput")
        self._docx_review.setPlaceholderText("第一步完成后自动填入，也可以选择已有确认表")
        review_browse = self._icon_button("folder-open", "选择审校表")
        review_browse.clicked.connect(
            lambda: self._browse_into(self._docx_review, "选择审校表", "Excel 审校表 (*.xlsx)")
        )
        document_layout.addLayout(self._picker_row("译文确认表", self._docx_review, review_browse))

        docx_actions = QHBoxLayout()
        docx_actions.setSpacing(9)
        self._docx_extract_button = QPushButton("1  生成确认表")
        self._docx_translate_button = QPushButton("2  自动翻译")
        self._docx_refill_button = QPushButton("3  生成英文 Word")
        for button, icon_name in (
            (self._docx_extract_button, "file-output"),
            (self._docx_translate_button, "languages"),
            (self._docx_refill_button, "clipboard-check"),
        ):
            button.setObjectName("PrimaryButton" if button is self._docx_refill_button else "SecondaryButton")
            button.setIcon(make_icon(icon_name, "#FFFFFF" if button is self._docx_refill_button else "#4F8274"))
            docx_actions.addWidget(button)
            self._busy_controls.append(button)
        self._docx_extract_button.clicked.connect(self._run_docx_extract)
        self._docx_translate_button.clicked.connect(lambda: self._run_review_translation("docx"))
        self._docx_refill_button.clicked.connect(self._run_docx_refill)
        docx_actions.addStretch(1)
        document_layout.addLayout(docx_actions)
        document_layout.addStretch(1)
        self._production_tabs.addTab(document_tab, "Word")

        audio_tab = QWidget()
        audio_layout = QVBoxLayout(audio_tab)
        audio_layout.setContentsMargins(16, 16, 16, 16)
        audio_layout.setSpacing(13)
        audio_layout.addWidget(self._section_title("把音视频内容翻译并生成英文配音"))
        self._audio_source = QLineEdit()
        self._audio_source.setObjectName("SearchInput")
        self._audio_source.setPlaceholderText("选择 MP3、WAV、M4A 或 MP4 文件")
        audio_browse = self._icon_button("folder-open", "选择音视频")
        audio_browse.clicked.connect(
            lambda: self._browse_into(
                self._audio_source,
                "选择音视频",
                "音视频文件 (*.mp3 *.wav *.m4a *.aac *.flac *.mp4 *.mov)",
            )
        )
        audio_layout.addLayout(self._picker_row("原始文件", self._audio_source, audio_browse))
        self._audio_review = QLineEdit()
        self._audio_review.setObjectName("SearchInput")
        self._audio_review.setPlaceholderText("识别后自动填入，也可以选择已有译文确认表")
        audio_review_browse = self._icon_button("folder-open", "选择音频审校表")
        audio_review_browse.clicked.connect(
            lambda: self._browse_into(self._audio_review, "选择音频审校表", "Excel 审校表 (*.xlsx)")
        )
        audio_layout.addLayout(self._picker_row("译文确认表", self._audio_review, audio_review_browse))

        audio_actions = QHBoxLayout()
        audio_actions.setSpacing(9)
        self._audio_transcribe_button = QPushButton("1  识别内容")
        self._audio_translate_button = QPushButton("2  自动翻译")
        self._audio_synthesize_button = QPushButton("3  生成英文语音")
        for button, icon_name in (
            (self._audio_transcribe_button, "audio-lines"),
            (self._audio_translate_button, "languages"),
            (self._audio_synthesize_button, "play"),
        ):
            button.setObjectName("PrimaryButton" if button is self._audio_synthesize_button else "SecondaryButton")
            button.setIcon(make_icon(icon_name, "#FFFFFF" if button is self._audio_synthesize_button else "#4F8274"))
            audio_actions.addWidget(button)
            self._busy_controls.append(button)
        self._audio_transcribe_button.clicked.connect(self._run_audio_transcribe)
        self._audio_translate_button.clicked.connect(lambda: self._run_review_translation("audio"))
        self._audio_synthesize_button.clicked.connect(self._run_audio_synthesize)
        audio_actions.addStretch(1)
        audio_layout.addLayout(audio_actions)
        audio_layout.addStretch(1)
        self._production_tabs.addTab(audio_tab, "音视频")

        resource_tab = QWidget()
        resource_layout = QVBoxLayout(resource_tab)
        resource_layout.setContentsMargins(16, 16, 16, 16)
        resource_layout.setSpacing(12)
        resource_search_row = QHBoxLayout()
        self._resource_search = QLineEdit()
        self._resource_search.setObjectName("SearchInput")
        self._resource_search.setPlaceholderText("搜索全部已整合资源的文件名、类型或路径")
        self._resource_search.textChanged.connect(self._refresh_resource_table)
        resource_search_row.addWidget(self._resource_search, 1)
        open_resources = self._icon_button("folder-open", "打开完整资源目录")
        open_resources.clicked.connect(self._open_collaboration_dir)
        resource_search_row.addWidget(open_resources)
        resource_layout.addLayout(resource_search_row)
        self._resource_table = QTableWidget(0, 4)
        self._resource_table.setObjectName("DataTable")
        self._resource_table.setHorizontalHeaderLabels(["文件", "内容类型", "格式", "大小"])
        self._resource_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._resource_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._resource_table.setAlternatingRowColors(True)
        self._resource_table.verticalHeader().setVisible(False)
        resource_header = self._resource_table.horizontalHeader()
        resource_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            resource_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._resource_table.cellDoubleClicked.connect(self._open_resource_file)
        resource_layout.addWidget(self._resource_table, 1)
        self._production_tabs.addTab(resource_tab, "查看全部文件")
        for field in (
            self._image_source,
            self._docx_source,
            self._docx_review,
            self._audio_source,
            self._audio_review,
        ):
            field.textChanged.connect(self._update_production_actions)
        self._update_production_actions()
        layout.addWidget(self._production_tabs, 3)

        result_row = QHBoxLayout()
        result_row.addWidget(self._section_title("下一步和本次结果"))
        result_row.addStretch(1)
        open_output = self._icon_button("folder-open", "打开输出目录")
        open_output.clicked.connect(self._open_output_dir)
        result_row.addWidget(open_output)
        layout.addLayout(result_row)
        self._production_output = MarkdownView("选择文件后，这里会告诉你下一步该做什么。")
        self._production_output.setObjectName("OutputView")
        self._production_output.setMaximumHeight(190)
        self._production_output.set_output(
            "### 从上面开始\n\n"
            "选择“图片”“Word”或“音视频”，再选择电脑里的原始文件。"
            "每完成一步，这里都会说明已经生成了什么，以及接下来该点击哪里。"
        )
        layout.addWidget(self._production_output, 2)
        return page

    def _picker_row(self, label_text: str, field: QLineEdit, button: QToolButton) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("InfoLabel")
        label.setFixedWidth(72)
        row.addWidget(label)
        row.addWidget(field, 1)
        row.addWidget(button)
        return row

    def _update_production_actions(self) -> None:
        image_source_ready = Path(self._image_source.text().strip()).is_file()
        docx_source_ready = Path(self._docx_source.text().strip()).is_file()
        docx_review_ready = Path(self._docx_review.text().strip()).is_file()
        audio_source_ready = Path(self._audio_source.text().strip()).is_file()
        audio_review_ready = Path(self._audio_review.text().strip()).is_file()
        self._image_translate_button.setEnabled(image_source_ready)
        self._docx_extract_button.setEnabled(docx_source_ready)
        self._docx_translate_button.setEnabled(docx_review_ready)
        self._docx_refill_button.setEnabled(docx_source_ready and docx_review_ready)
        self._audio_transcribe_button.setEnabled(audio_source_ready)
        self._audio_translate_button.setEnabled(audio_review_ready)
        self._audio_synthesize_button.setEnabled(audio_review_ready)

    def _build_agent_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("AgentPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        banner = QFrame()
        banner.setObjectName("InfoBanner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        self._agent_state_dot = QLabel("●")
        self._agent_state_dot.setObjectName("AgentStateDot")
        self._agent_state_text = QLabel()
        self._agent_state_text.setObjectName("InfoText")
        banner_layout.addWidget(self._agent_state_dot)
        banner_layout.addWidget(self._agent_state_text, 1)
        layout.addWidget(banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._agent_input_panel())
        splitter.addWidget(self._agent_output_panel())
        splitter.setSizes([460, 650])
        layout.addWidget(splitter, 1)
        return page

    def _agent_input_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ToolPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section_title("粘贴中文"))

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._agent_modes = QButtonGroup(self)
        self._agent_modes.setExclusive(True)
        for mode, text in (
            ("agent", "快速翻译"),
            ("default_workflow", "精译模式"),
            ("coze_workflow", "多模型精译（扣子）"),
        ):
            button = QPushButton(text)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setProperty("mode", mode)
            button.clicked.connect(
                lambda checked=False, selected=mode: self._update_agent_mode_guide(selected)
            )
            self._agent_modes.addButton(button)
            mode_row.addWidget(button)
        self._agent_modes.buttons()[0].setChecked(True)
        layout.addLayout(mode_row)

        self._agent_mode_guide = QFrame()
        self._agent_mode_guide.setObjectName("AgentModeGuide")
        guide_layout = QHBoxLayout(self._agent_mode_guide)
        guide_layout.setContentsMargins(12, 10, 12, 10)
        guide_layout.setSpacing(10)
        self._agent_mode_icon = QLabel()
        self._agent_mode_icon.setObjectName("AgentModeIcon")
        self._agent_mode_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agent_mode_icon.setFixedSize(36, 36)
        guide_copy = QVBoxLayout()
        guide_copy.setSpacing(2)
        self._agent_mode_title = QLabel()
        self._agent_mode_title.setObjectName("AgentModeTitle")
        self._agent_mode_detail = QLabel()
        self._agent_mode_detail.setObjectName("AgentModeDetail")
        self._agent_mode_detail.setWordWrap(True)
        self._agent_mode_proof = QLabel()
        self._agent_mode_proof.setObjectName("AgentModeProof")
        self._agent_mode_proof.setWordWrap(True)
        guide_copy.addWidget(self._agent_mode_title)
        guide_copy.addWidget(self._agent_mode_detail)
        guide_copy.addWidget(self._agent_mode_proof)
        self._coze_demo_button = QPushButton("演示这套流程")
        self._coze_demo_button.setObjectName("GuideAction")
        self._coze_demo_button.setIcon(make_icon("play", "#3E8D7B", 15))
        self._coze_demo_button.clicked.connect(self._show_coze_demo)
        guide_layout.addWidget(self._agent_mode_icon)
        guide_layout.addLayout(guide_copy, 1)
        guide_layout.addWidget(self._coze_demo_button)
        layout.addWidget(self._agent_mode_guide)

        self._agent_title = QLineEdit()
        self._agent_title.setObjectName("SearchInput")
        self._agent_title.setPlaceholderText("标题或来源（选填，例如：端午节儿童故事）")
        self._agent_title.setClearButtonEnabled(True)
        layout.addWidget(self._agent_title)

        self._agent_input = QPlainTextEdit()
        self._agent_input.setObjectName("InputEditor")
        self._agent_input.setPlaceholderText("在这里粘贴要翻译的中文，也可以补充语气、读者年龄等要求…")
        self._agent_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._agent_input, 1)

        footer = QHBoxLayout()
        clear = QPushButton("清空")
        clear.setObjectName("TextButton")
        clear.clicked.connect(self._clear_agent_input)
        example = QPushButton("载入示例")
        example.setObjectName("TextButton")
        example.clicked.connect(self._insert_translation_example)
        self._agent_run_button = QPushButton("生成译文")
        self._agent_run_button.setObjectName("PrimaryButton")
        self._agent_run_button.setIcon(make_icon("play", "#FFFFFF"))
        self._agent_run_button.clicked.connect(self._run_agent)
        self._busy_controls.append(self._agent_run_button)
        footer.addWidget(clear)
        footer.addWidget(example)
        footer.addStretch(1)
        footer.addWidget(self._agent_run_button)
        layout.addLayout(footer)
        self._update_agent_mode_guide("agent")
        return panel

    def _agent_output_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ToolPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(self._section_title("英文译文"))
        header.addStretch(1)
        copy_button = self._icon_button("copy", "复制结果")
        copy_button.clicked.connect(lambda: self._copy_view(self._agent_output))
        save_button = self._icon_button("save", "保存结果 (Ctrl+S)")
        save_button.clicked.connect(lambda: self._save_view(self._agent_output, "agent-output.md"))
        header.addWidget(copy_button)
        header.addWidget(save_button)
        layout.addLayout(header)
        self._agent_output = MarkdownView("生成的英文译文会显示在这里。")
        self._agent_output.setObjectName("OutputView")
        layout.addWidget(self._agent_output, 1)
        return panel

    def _build_terms_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("TermsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        search_row = QHBoxLayout()
        self._term_search = QLineEdit()
        self._term_search.setObjectName("SearchInput")
        self._term_search.setPlaceholderText("搜索中文术语、英文译法或上下文…")
        self._term_search.setClearButtonEnabled(True)
        self._term_search.returnPressed.connect(self._search_terms_now)
        search_button = QPushButton("搜索")
        search_button.setObjectName("PrimaryButton")
        search_button.setIcon(make_icon("search", "#FFFFFF"))
        search_button.clicked.connect(self._search_terms_now)
        self._use_term_button = QPushButton("用于本次翻译")
        self._use_term_button.setObjectName("SecondaryButton")
        self._use_term_button.setIcon(make_icon("plus", "#4F8274"))
        self._use_term_button.setEnabled(False)
        self._use_term_button.clicked.connect(self._append_selected_term_to_agent)
        search_row.addWidget(self._term_search, 1)
        search_row.addWidget(search_button)
        search_row.addWidget(self._use_term_button)
        layout.addLayout(search_row)

        self._term_count_label = QLabel()
        self._term_count_label.setObjectName("SectionSubtitle")
        layout.addWidget(self._term_count_label)
        self._term_table = QTableWidget(0, 4)
        self._term_table.setObjectName("DataTable")
        self._term_table.setHorizontalHeaderLabels(["中文术语", "推荐英文", "参考页", "使用语境"])
        self._term_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._term_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._term_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._term_table.setAlternatingRowColors(True)
        self._term_table.verticalHeader().setVisible(False)
        self._term_table.verticalHeader().setDefaultSectionSize(42)
        header = self._term_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 150)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 245)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 92)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._term_table.itemSelectionChanged.connect(
            lambda: self._use_term_button.setEnabled(bool(self._term_table.selectionModel().selectedRows()))
        )
        layout.addWidget(self._term_table, 1)
        return page

    def _build_workflow_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("WorkflowPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        stages = QGridLayout()
        stages.setHorizontalSpacing(10)
        workflow_stages = (
            ("scan-text", "读取素材", "图文 · 文档 · 音视频"),
            ("languages", "翻译与约束", "术语 · 风格 · 智能体"),
            ("clipboard-check", "审校与回填", "Excel · DOCX · 英文语音"),
            ("shield-check", "交付质检", "成品 · 报告 · 资源索引"),
        )
        for index, (icon_name, title, detail) in enumerate(workflow_stages):
            node = QFrame()
            node.setObjectName("WorkflowNode")
            node_layout = QHBoxLayout(node)
            node_layout.setContentsMargins(13, 11, 13, 11)
            stage_icon = QLabel()
            stage_icon.setObjectName("WorkflowNumber")
            stage_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stage_icon.setFixedSize(32, 32)
            stage_icon.setPixmap(make_icon(icon_name, "#167A65", 18).pixmap(18, 18))
            texts = QVBoxLayout()
            texts.setSpacing(0)
            title_label = QLabel(title)
            title_label.setObjectName("WorkflowTitle")
            detail_label = QLabel(detail)
            detail_label.setObjectName("WorkflowDetail")
            texts.addWidget(title_label)
            texts.addWidget(detail_label)
            state = QLabel("就绪")
            state.setObjectName("WorkflowState")
            state.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node_layout.addWidget(stage_icon)
            node_layout.addLayout(texts, 1)
            node_layout.addWidget(state)
            stages.addWidget(node, 0, index)
            stages.setColumnStretch(index, 1)
        layout.addLayout(stages)

        input_row = QHBoxLayout()
        self._workflow_input = QPlainTextEdit()
        self._workflow_input.setObjectName("WorkflowInput")
        self._workflow_input.setPlaceholderText("可选：填写本次整合目标，例如“生成可供课堂演示的最终交付状态与风险清单”。")
        self._workflow_input.setMaximumHeight(106)
        self._workflow_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._workflow_run_button = QPushButton("开始批量处理")
        self._workflow_run_button.setObjectName("PrimaryButton")
        self._workflow_run_button.setIcon(make_icon("play", "#FFFFFF"))
        self._workflow_run_button.setMinimumWidth(160)
        self._workflow_run_button.clicked.connect(
            lambda: self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)
        )
        self._busy_controls.append(self._workflow_run_button)
        input_row.addWidget(self._workflow_input, 1)
        input_row.addWidget(self._workflow_run_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_row)

        result_header = QHBoxLayout()
        result_header.addWidget(self._section_title("工作流结果"))
        result_header.addStretch(1)
        save_button = self._icon_button("save", "保存工作流结果")
        save_button.clicked.connect(lambda: self._save_view(self._workflow_output, "workflow-output.md"))
        result_header.addWidget(save_button)
        layout.addLayout(result_header)
        workflow_snapshot = (
            "# 统一生产工作流已就绪\n\n"
            f"- 已连接资源：{len(self._scan.assets)} 个\n"
            f"- 文化术语：{self._scan.terminology.count} 条\n"
            "- 文档：提取审校表、智能翻译、人工审校、Word XML 回填\n"
            "- 音视频：语音识别、逐句审校表、智能翻译、英文语音合成\n"
            "- 图文：完整审校清单、回填成品、SVG 与逐页预览证据\n\n"
            "所有最终成品统一进入交付中心，来源分组仅保留在内部追溯路径中。"
        )
        self._workflow_output = MarkdownView("工作流状态会显示在这里。")
        self._workflow_output.setObjectName("OutputView")
        self._workflow_output.set_output(workflow_snapshot)
        layout.addWidget(self._workflow_output, 1)
        return page

    def _build_showcase_page(self) -> QWidget:
        content = QWidget()
        content.setObjectName("ShowcaseContent")
        content.setMaximumWidth(1220)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 30, 36, 42)
        layout.setSpacing(18)

        ready_root = self._project_root / "collaboration/integration/final_outputs/ready_to_use"
        image_root = ready_root / "01_图文翻译"
        audio_root = ready_root / "04_音视频翻译"
        audio_candidates = sorted((audio_root / "本机重新生成产出").glob("*英文配音_*.wav"))
        showcase_audio = (
            audio_candidates[-1]
            if audio_candidates
            else audio_root / "完整音频测试与成品/模式二生成总音频.mp3"
        )

        hero = QFrame()
        hero.setObjectName("ShowcaseHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(32, 28, 28, 28)
        hero_layout.setSpacing(26)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(9)
        hero_eyebrow = QLabel("译述 YISHU  ·  可直接使用的完整成果")
        hero_eyebrow.setObjectName("ShowcaseEyebrow")
        hero_title = QLabel("从图文原稿，\n到可交付译成品")
        hero_title.setObjectName("ShowcaseTitle")
        hero_subtitle = QLabel(
            "文化术语、儿童文学语气、Word 版式与英文配音，"
            "都在同一套审校记录中可追溯。"
        )
        hero_subtitle.setObjectName("ShowcaseSubtitle")
        hero_subtitle.setWordWrap(True)
        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(9)
        demo_button = QPushButton("开始现场演示")
        demo_button.setObjectName("ShowcasePrimary")
        demo_button.setIcon(make_icon("play", "#FFFFFF", 17))
        demo_button.clicked.connect(self._open_beginner_example)
        final_button = QPushButton("打开最终文档")
        final_button.setObjectName("ShowcaseSecondary")
        final_button.setIcon(make_icon("file-text", "#327568", 17))
        final_button.clicked.connect(
            lambda: self._open_known_path(image_root / "中国文化知识百科_图文英文回填终版.docx")
        )
        hero_actions.addWidget(demo_button)
        hero_actions.addWidget(final_button)
        hero_actions.addStretch(1)
        hero_copy.addWidget(hero_eyebrow)
        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_subtitle)
        hero_copy.addStretch(1)
        hero_copy.addLayout(hero_actions)
        hero_layout.addLayout(hero_copy, 5)

        preview_stage = QFrame()
        preview_stage.setObjectName("ShowcasePreviewStage")
        preview_layout = QHBoxLayout(preview_stage)
        preview_layout.setContentsMargins(18, 17, 18, 17)
        preview_layout.setSpacing(10)
        pages_root = (
            self._project_root
            / "collaboration/groups/A_image_translation/deliverables/extracted_20260717_update/"
            "validation/rendered_pages"
        )
        for index, page_no in enumerate((1, 7, 14)):
            preview = QLabel()
            preview.setObjectName("ShowcasePage")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setFixedSize(112 if index == 1 else 92, 150 if index == 1 else 130)
            pixmap = QPixmap(str(pages_root / f"page_{page_no:02d}.png"))
            if not pixmap.isNull():
                preview.setPixmap(
                    pixmap.scaled(
                        preview.width() - 8,
                        preview.height() - 8,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            preview_layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignBottom)
        hero_layout.addWidget(preview_stage, 4)
        layout.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        for value, label, accent in (
            ("71 条", "图文逐条人工审校", "#D96C4F"),
            ("251 条", "文化术语统一约束", "#2F6658"),
            ("5 / 5", "Word 版式回填实测", "#4F6F9B"),
            ("219 句", "英文配音逐句生成", "#A88952"),
        ):
            metric = QFrame()
            metric.setObjectName("ShowcaseMetric")
            metric_layout = QVBoxLayout(metric)
            metric_layout.setContentsMargins(17, 14, 17, 14)
            metric_layout.setSpacing(2)
            value_label = QLabel(value)
            value_label.setObjectName("ShowcaseMetricValue")
            value_label.setStyleSheet(f"color: {accent};")
            detail_label = QLabel(label)
            detail_label.setObjectName("ShowcaseMetricLabel")
            metric_layout.addWidget(value_label)
            metric_layout.addWidget(detail_label)
            metrics.addWidget(metric, 1)
        layout.addLayout(metrics)

        coze_highlight = QFrame()
        coze_highlight.setObjectName("CozeHighlight")
        coze_layout = QHBoxLayout(coze_highlight)
        coze_layout.setContentsMargins(18, 14, 18, 14)
        coze_layout.setSpacing(12)
        coze_icon = QLabel()
        coze_icon.setObjectName("CozeHighlightIcon")
        coze_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coze_icon.setFixedSize(38, 38)
        coze_icon.setPixmap(make_icon("route", "#4D8E7C", 19).pixmap(19, 19))
        coze_copy = QVBoxLayout()
        coze_copy.setSpacing(2)
        coze_title = QLabel("多模型不是一句提示词，而是一套可检查的翻译流程")
        coze_title.setObjectName("CozeHighlightTitle")
        coze_detail = QLabel(
            "术语提取 → 风格提炼 → Kimi / DeepSeek / 豆包三路初译与互评 → GLM 融合终稿"
        )
        coze_detail.setObjectName("CozeHighlightDetail")
        coze_detail.setWordWrap(True)
        coze_copy.addWidget(coze_title)
        coze_copy.addWidget(coze_detail)
        coze_badge = QLabel("扣子真实配置  ·  18 个节点  ·  28 条连接  ·  图结构校验通过")
        coze_badge.setObjectName("CozeHighlightBadge")
        coze_action = QPushButton("查看流程演示")
        coze_action.setObjectName("CozeHighlightAction")
        coze_action.setIcon(make_icon("play", "#3E8D7B", 15))
        coze_action.clicked.connect(self._open_coze_showcase)
        coze_layout.addWidget(coze_icon)
        coze_layout.addLayout(coze_copy, 1)
        coze_layout.addWidget(coze_badge)
        coze_layout.addWidget(coze_action)
        layout.addWidget(coze_highlight)

        story = QFrame()
        story.setObjectName("ShowcaseStory")
        story_layout = QHBoxLayout(story)
        story_layout.setContentsMargins(24, 22, 24, 22)
        story_layout.setSpacing(26)
        contact = QLabel()
        contact.setObjectName("ShowcaseContactSheet")
        contact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact.setMinimumSize(450, 245)
        contact_path = image_root / "已翻译图片资源/image16.png"
        contact_pixmap = QPixmap(str(contact_path))
        if not contact_pixmap.isNull():
            contact.setPixmap(
                contact_pixmap.scaled(
                    440,
                    235,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        story_layout.addWidget(contact, 5)

        story_copy = QVBoxLayout()
        story_copy.setSpacing(10)
        story_kicker = QLabel("看得见的翻译质量")
        story_kicker.setObjectName("ShowcaseStoryKicker")
        story_title = QLabel("译文改变，原有表达不被破坏")
        story_title.setObjectName("ShowcaseStoryTitle")
        story_title.setWordWrap(True)
        story_body = QLabel(
            "图中文字经过审校后回填，Word 正文、表格、图片、页眉和页脚继续保持原有结构。"
            "每个最终文件都附带清单、预览和机器可读验收记录。"
        )
        story_body.setObjectName("ShowcaseStoryBody")
        story_body.setWordWrap(True)
        proof_items = (
            ("clipboard-check", "可审核", "机器译文与人工确认分列保存"),
            ("file-text", "可回填", "DOCX XML 级替换并保持版式"),
            ("audio-lines", "可播放", "终版译文生成英文语音与二维码"),
        )
        story_copy.addWidget(story_kicker)
        story_copy.addWidget(story_title)
        story_copy.addWidget(story_body)
        for icon_name, item_title, item_detail in proof_items:
            row = QHBoxLayout()
            icon = QLabel()
            icon.setObjectName("ShowcaseProofIcon")
            icon.setFixedSize(30, 30)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setPixmap(make_icon(icon_name, "#2F6658", 16).pixmap(16, 16))
            text_box = QVBoxLayout()
            text_box.setSpacing(0)
            title_label = QLabel(item_title)
            title_label.setObjectName("ShowcaseProofTitle")
            detail_label = QLabel(item_detail)
            detail_label.setObjectName("ShowcaseProofDetail")
            text_box.addWidget(title_label)
            text_box.addWidget(detail_label)
            row.addWidget(icon)
            row.addLayout(text_box, 1)
            story_copy.addLayout(row)
        story_copy.addStretch(1)
        story_layout.addLayout(story_copy, 4)
        layout.addWidget(story)

        evidence = QFrame()
        evidence.setObjectName("ShowcaseEvidence")
        evidence_layout = QHBoxLayout(evidence)
        evidence_layout.setContentsMargins(20, 16, 20, 16)
        evidence_layout.setSpacing(10)
        evidence_text = QVBoxLayout()
        evidence_text.setSpacing(2)
        evidence_title = QLabel("现场可验证，不依赖演示话术")
        evidence_title.setObjectName("EvidenceTitle")
        evidence_detail = QLabel("直接打开成品、审校表、配音和验收记录。")
        evidence_detail.setObjectName("EvidenceDetail")
        evidence_text.addWidget(evidence_title)
        evidence_text.addWidget(evidence_detail)
        evidence_layout.addLayout(evidence_text, 1)
        evidence_paths = (
            ("审校表", "clipboard-check", image_root / "图中文字_71条人工审校清单.xlsx"),
            (
                "英文配音",
                "audio-lines",
                showcase_audio,
            ),
            ("验收记录", "package-check", ready_root / "05_资源索引/最终验收.json"),
        )
        for label, icon_name, target in evidence_paths:
            button = QPushButton(label)
            button.setObjectName("EvidenceButton")
            button.setIcon(make_icon(icon_name, "#4F8274", 16))
            button.clicked.connect(lambda checked=False, path=target: self._open_known_path(path))
            evidence_layout.addWidget(button)
        workflow_button = QPushButton("运行完整流程")
        workflow_button.setObjectName("EvidenceButton")
        workflow_button.setIcon(make_icon("route", "#4F8274", 16))
        workflow_button.clicked.connect(lambda: self._switch_page("workflow"))
        evidence_layout.addWidget(workflow_button)
        layout.addWidget(evidence)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll

    def _build_outputs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("OutputsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        path_row = QHBoxLayout()
        path_text = QVBoxLayout()
        path_text.setSpacing(2)
        path_text.addWidget(self._section_title("最近生成的成品"))
        self._output_path_label = QLabel()
        self._output_path_label.setObjectName("PathLabel")
        self._output_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_text.addWidget(self._output_path_label)
        path_row.addLayout(path_text, 1)
        open_button = QPushButton("打开成品文件夹")
        open_button.setObjectName("SecondaryButton")
        open_button.setIcon(make_icon("folder-open", "#4F8274"))
        open_button.clicked.connect(self._open_output_dir)
        report_button = QPushButton("整理成品清单")
        report_button.setObjectName("PrimaryButton")
        report_button.setIcon(make_icon("file-text", "#FFFFFF"))
        report_button.clicked.connect(
            lambda: self._start_job("report", self._workflow_input.toPlainText(), allow_empty=True)
        )
        self._busy_controls.append(report_button)
        path_row.addWidget(open_button)
        path_row.addWidget(report_button)
        layout.addLayout(path_row)

        self._output_table = QTableWidget(0, 4)
        self._output_table.setObjectName("DataTable")
        self._output_table.setHorizontalHeaderLabels(["文件名", "类型", "更新时间", "大小"])
        self._output_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._output_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._output_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._output_table.setAlternatingRowColors(True)
        self._output_table.verticalHeader().setVisible(False)
        self._output_table.verticalHeader().setDefaultSectionSize(38)
        output_header = self._output_table.horizontalHeader()
        output_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        output_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        output_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        output_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._output_table.cellDoubleClicked.connect(self._open_output_file)
        layout.addWidget(self._output_table, 2)

        tabs = QTabWidget()
        tabs.setObjectName("ResultTabs")
        delivery_snapshot = (
            "# 已准备好的成品\n\n"
            "- **Word**：原稿、译文确认表和保留版式的英文文档\n"
            "- **音视频**：逐句确认表、英文配音、朗读文本和二维码\n"
            "- **图片**：人工审校清单、翻译后图片和最终页面预览\n"
            "- **资料**：文化术语库、文件索引和完整验收记录\n\n"
            "双击上方任意文件即可打开。新生成的成品会自动出现在这里。"
        )
        self._delivery_output = MarkdownView("交付摘要会显示在这里。")
        self._delivery_output.setObjectName("OutputView")
        self._delivery_output.set_output(delivery_snapshot)
        self._log = QPlainTextEdit()
        self._log.setObjectName("LogView")
        self._log.setReadOnly(True)
        tabs.addTab(self._delivery_output, "成品说明")
        tabs.addTab(self._log, "处理记录")
        layout.addWidget(tabs, 3)
        return page

    def _build_group_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("GroupPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        summary_row = QHBoxLayout()
        self._group_badge = QLabel()
        self._group_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._group_badge.setFixedSize(52, 52)
        self._group_badge.setObjectName("DetailGroupBadge")
        summary_text = QVBoxLayout()
        summary_text.setSpacing(3)
        self._group_detail_title = QLabel()
        self._group_detail_title.setObjectName("DetailTitle")
        self._group_detail_description = QLabel()
        self._group_detail_description.setObjectName("SectionSubtitle")
        self._group_detail_description.setWordWrap(True)
        summary_text.addWidget(self._group_detail_title)
        summary_text.addWidget(self._group_detail_description)
        self._group_detail_status = QLabel()
        self._group_detail_status.setObjectName("DetailStatus")
        self._group_detail_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._group_detail_status.setFixedSize(76, 29)
        summary_row.addWidget(self._group_badge)
        summary_row.addLayout(summary_text, 1)
        summary_row.addWidget(self._group_detail_status)
        layout.addLayout(summary_row)

        info_panel = QFrame()
        info_panel.setObjectName("SectionPanel")
        info_layout = QGridLayout(info_panel)
        info_layout.setContentsMargins(17, 14, 17, 14)
        info_layout.setHorizontalSpacing(24)
        info_layout.setVerticalSpacing(8)
        self._group_file_count = self._info_value()
        self._group_size = self._info_value()
        self._group_updated = self._info_value()
        self._group_path = self._info_value()
        self._group_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(self._info_label("资源文件"), 0, 0)
        info_layout.addWidget(self._group_file_count, 0, 1)
        info_layout.addWidget(self._info_label("占用空间"), 0, 2)
        info_layout.addWidget(self._group_size, 0, 3)
        info_layout.addWidget(self._info_label("最近更新"), 1, 0)
        info_layout.addWidget(self._group_updated, 1, 1)
        info_layout.addWidget(self._info_label("协作路径"), 1, 2)
        info_layout.addWidget(self._group_path, 1, 3)
        info_layout.setColumnStretch(3, 1)
        layout.addWidget(info_panel)

        controls = QHBoxLayout()
        self._group_query = QLineEdit()
        self._group_query.setObjectName("SearchInput")
        self._group_query.setPlaceholderText("可选：输入适配目标或文化术语关键词")
        self._group_query.returnPressed.connect(self._run_group_adapter)
        open_button = self._icon_button("folder-open", "打开分组目录")
        open_button.clicked.connect(self._open_group_dir)
        self._group_run_button = QPushButton("运行适配器")
        self._group_run_button.setObjectName("PrimaryButton")
        self._group_run_button.setIcon(make_icon("play", "#FFFFFF"))
        self._group_run_button.clicked.connect(self._run_group_adapter)
        self._busy_controls.append(self._group_run_button)
        controls.addWidget(self._group_query, 1)
        controls.addWidget(open_button)
        controls.addWidget(self._group_run_button)
        layout.addLayout(controls)

        self._group_output = MarkdownView("运行分组适配器后，这里会显示接入状态与建议。")
        self._group_output.setObjectName("OutputView")
        layout.addWidget(self._group_output, 1)
        return page

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _info_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoLabel")
        return label

    def _info_value(self) -> QLabel:
        label = QLabel()
        label.setObjectName("InfoValue")
        label.setWordWrap(True)
        return label

    def _icon_button(self, icon_name: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("IconButton")
        button.setIcon(make_icon(icon_name))
        button.setIconSize(QSize(17, 17))
        button.setToolTip(tooltip)
        return button

    def _configure_interactions(self) -> None:
        for button in (*self.findChildren(QPushButton), *self.findChildren(QToolButton)):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        if hasattr(self, "_stats_grid"):
            workspace_width = max(0, self.width() - SIDEBAR_WIDTH)
            if workspace_width < 1040:
                self._relayout_overview(2, 2)
            else:
                self._relayout_overview(4, 3)

    def _relayout_overview(self, stat_columns: int, group_columns: int) -> None:
        mode = stat_columns * 10 + group_columns
        if getattr(self, "_overview_layout_mode", None) == mode:
            return
        self._overview_layout_mode = mode

        for layout, widgets, columns in (
            (self._task_grid, self._task_cards, stat_columns),
            (self._stats_grid, self._stat_cards, stat_columns),
        ):
            while layout.count():
                layout.takeAt(0)
            for column in range(4):
                layout.setColumnStretch(column, 0)
            for index, widget in enumerate(widgets):
                layout.addWidget(widget, index // columns, index % columns)
            for column in range(columns):
                layout.setColumnStretch(column, 1)

    def _install_shortcuts(self) -> None:
        scan_action = QAction(self)
        scan_action.setShortcut(QKeySequence("F5"))
        scan_action.triggered.connect(self._scan_now)
        self.addAction(scan_action)

        run_action = QAction(self)
        run_action.setShortcut(QKeySequence("Ctrl+Return"))
        run_action.triggered.connect(self._run_current_page)
        self.addAction(run_action)

        save_action = QAction(self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_current_output)
        self.addAction(save_action)

    @Slot(str)
    def _handle_task_action(self, action: str) -> None:
        category, _, value = action.partition(":")
        if category == "production":
            self._switch_page("production")
            tab_index = {"images": 0, "docx": 1, "audio": 2, "resources": 3}.get(value, 0)
            self._production_tabs.setCurrentIndex(tab_index)
            return
        if category == "group" and value in GROUPS:
            self._show_group(value)
            return
        if category == "adapter" and value in GROUPS:
            self._show_group(value)
            self._start_job(f"adapter:{value}", "", allow_empty=True)
            return
        if category == "page" and value in self._pages:
            self._switch_page(value)
            return
        if category == "agent" and value == "coze":
            self._switch_page("agent")
            for button in self._agent_modes.buttons():
                if button.property("mode") == "coze_workflow":
                    button.setChecked(True)
                    break
            self._update_agent_mode_guide("coze_workflow")
            self._agent_input.setFocus()
            return
        if action == "workflow:run":
            self._switch_page("workflow")
            self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)

    def _choose_start_file(self, kind: str = "all") -> None:
        filters = {
            "image": "图片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)",
            "docx": "Word 文档 (*.docx)",
            "audio": "音频和视频 (*.mp3 *.wav *.m4a *.aac *.flac *.mp4 *.mov)",
            "all": (
                "支持的文件 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.docx "
                "*.mp3 *.wav *.m4a *.aac *.flac *.mp4 *.mov)"
            ),
        }
        title = {
            "image": "选择一张图片",
            "docx": "选择一个 Word 文档",
            "audio": "选择一个音频或视频",
        }.get(kind, "选择要翻译的文件")
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            str(self._project_root),
            filters.get(kind, filters["all"]),
        )
        if path:
            self._route_start_file(Path(path))

    @Slot(object)
    def _handle_start_drop(self, paths: object) -> None:
        values = [Path(str(path)) for path in paths] if isinstance(paths, (list, tuple)) else []
        supported = [path for path in values if path.is_file()]
        if not supported:
            QMessageBox.information(self, "没有可用文件", "请拖入图片、Word、音频或视频文件。")
            return
        if len(supported) > 1:
            self.statusBar().showMessage(f"已收到 {len(supported)} 个文件，先打开第一个；其余可在批量处理中加入", 6000)
        self._route_start_file(supported[0])

    def _route_start_file(self, path: Path) -> None:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            self._docx_source.setText(str(path))
            self._production_tabs.setCurrentIndex(1)
            message = (
                f"### 已选择 Word 文档\n\n**{path.name}**\n\n"
                "下一步点击“1 生成审校表”。系统会提取正文、表格、页眉和页脚，"
                "并把需要确认的内容整理到 Excel。"
            )
        elif suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".mp4", ".mov"}:
            self._audio_source.setText(str(path))
            self._production_tabs.setCurrentIndex(2)
            message = (
                f"### 已选择音视频\n\n**{path.name}**\n\n"
                "下一步点击“1 识别内容”。识别后可检查逐句译文，并生成英文配音。"
            )
        elif suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
            self._image_source.setText(str(path))
            self._production_tabs.setCurrentIndex(0)
            message = (
                f"### 已选择图片\n\n**{path.name}**\n\n"
                "点击“识别并翻译图片”，系统会读取图中文字并生成中英对照结果。"
            )
        else:
            QMessageBox.information(
                self,
                "暂不支持这个文件",
                "请选择 JPG、PNG、DOCX、MP3、WAV、M4A 或 MP4 文件。",
            )
            return
        self._production_output.set_output(message)
        self._switch_page("production")
        self.statusBar().showMessage(f"已选择：{path.name}", 5000)

    def _open_text_translation(self) -> None:
        self._switch_page("agent")
        self._agent_input.setFocus()

    def _open_beginner_example(self) -> None:
        self._load_production_example()
        self._production_tabs.setCurrentIndex(0)
        self._switch_page("production")

    def _browse_into(self, field: QLineEdit, title: str, file_filter: str) -> None:
        current = Path(field.text()).expanduser() if field.text().strip() else self._project_root
        start = current.parent if current.is_file() else current
        path, _ = QFileDialog.getOpenFileName(self, title, str(start), file_filter)
        if path:
            field.setText(path)

    def _load_production_example(self) -> None:
        base = (
            self._project_root
            / "collaboration/groups/C_text_audio_translation/deliverables"
        )
        docx_cases = base / "docx_translation/revised_20260717/test_cases"
        source_candidates = sorted(docx_cases.rglob("童话故事2.docx"))
        review_candidates = sorted(docx_cases.rglob("*00ef5c52*.xlsx"))
        supplement = base / "audio_video_workflow/revised_20260717/supplement"
        audio = supplement / "测试音频.mp3"
        audio_review = supplement / "模式二生成终版表格.xlsx"
        if source_candidates:
            self._docx_source.setText(str(source_candidates[0]))
        if review_candidates:
            self._docx_review.setText(str(review_candidates[0]))
        if audio.exists():
            self._audio_source.setText(str(audio))
        if audio_review.exists():
            self._audio_review.setText(str(audio_review))
        self._production_output.set_output(
            "# 完整示例已载入\n\n"
            "文档和音频字段已连接到项目真实交付样例。可直接执行 DOCX 回填或英文语音合成；"
            "智能翻译与音频识别会使用已配置的在线模型通道。"
        )
        self.statusBar().showMessage("已载入完整生产示例", 4000)

    def _run_docx_extract(self) -> None:
        source = self._docx_source.text().strip()
        if not source:
            QMessageBox.information(self, "请选择文件", "请先选择源 DOCX。")
            return
        self._start_job("production:docx-extract", source)

    def _run_image_translate(self) -> None:
        source = self._image_source.text().strip()
        if not source:
            QMessageBox.information(self, "请选择图片", "请先选择一张需要翻译的图片。")
            return
        self._start_job("production:image-translate", source)

    def _run_review_translation(self, target: str) -> None:
        field = self._docx_review if target == "docx" else self._audio_review
        review = field.text().strip()
        if not review:
            QMessageBox.information(self, "请选择文件", "请先选择或生成审校表。")
            return
        payload = json.dumps({"review": review, "target": f"{target}-translated-review"}, ensure_ascii=False)
        self._start_job("production:review-translate", payload)

    def _run_docx_refill(self) -> None:
        source = self._docx_source.text().strip()
        review = self._docx_review.text().strip()
        if not source or not review:
            QMessageBox.information(self, "需要两个文件", "请同时选择源 DOCX 和已审校 Excel。")
            return
        payload = json.dumps({"source": source, "review": review}, ensure_ascii=False)
        self._start_job("production:docx-refill", payload)

    def _run_audio_transcribe(self) -> None:
        source = self._audio_source.text().strip()
        if not source:
            QMessageBox.information(self, "请选择文件", "请先选择源音频或视频。")
            return
        self._start_job("production:audio-transcribe", source)

    def _run_audio_synthesize(self) -> None:
        review = self._audio_review.text().strip()
        if not review:
            QMessageBox.information(self, "请选择文件", "请先选择终版审校表。")
            return
        self._start_job("production:audio-synthesize", review)

    def _refresh_resource_table(self) -> None:
        if not hasattr(self, "_resource_table"):
            return
        query = self._resource_search.text().strip().lower()
        assets = [
            asset
            for asset in self._scan.assets
            if not query
            or query in asset.relative_path.lower()
            or query in asset.category.lower()
            or query in asset.suffix.lower()
        ][:1000]
        self._resource_table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            path = self._project_root / asset.relative_path
            values = (path.name, asset.category, asset.suffix.lstrip(".").upper(), format_size(asset.size_bytes))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(asset.relative_path)
                self._resource_table.setItem(row, column, item)

    def _open_resource_file(self, row: int, column: int) -> None:
        item = self._resource_table.item(row, column)
        if item is None:
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_collaboration_dir(self) -> None:
        path = self._project_root / "collaboration"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_known_path(self, path: Path) -> None:
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        QMessageBox.warning(self, "文件不存在", f"未找到文件：\n{path}")

    def _switch_page(self, page_key: str) -> None:
        if page_key not in self._pages:
            return
        self._current_page_key = page_key
        title, subtitle = PAGE_META[page_key]
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitle)
        self._stack.setCurrentWidget(self._pages[page_key])
        self._animate_page(self._pages[page_key])
        self._animate_text_reveal((self._page_title, self._page_subtitle), 45, 300)
        if page_key == "overview":
            self._animate_overview_intro()
        button = self._nav_buttons.get(page_key)
        if button is not None:
            button.setChecked(True)
        if page_key == "outputs":
            self._refresh_outputs_table()

    @Slot(str)
    def _show_group(self, group_key: str) -> None:
        if group_key not in GROUPS:
            return
        self._active_group = group_key
        self._current_page_key = "group"
        self._stack.setCurrentWidget(self._pages["group"])
        self._animate_page(self._pages["group"])
        self._nav_group.setExclusive(False)
        for button in self._nav_buttons.values():
            button.setChecked(False)
        self._nav_group.setExclusive(True)
        summary = next(group for group in self._scan.groups if group.key == group_key)
        self._page_title.setText(summary.name)
        self._page_subtitle.setText("分组交付详情与本地适配器")
        self._group_badge.setPixmap(
            make_icon(GROUP_ICONS[group_key], "#FFFFFF", 27).pixmap(27, 27)
        )
        self._group_badge.setStyleSheet(
            f"background: {GROUP_ACCENTS[group_key]}; color: white; border-radius: 8px;"
        )
        self._group_detail_title.setText(summary.name.partition("：")[2] or summary.name)
        self._group_detail_description.setText(summary.description)
        self._group_detail_status.setText(f"●  {summary.status}")
        ready = summary.status == "可整合"
        self._group_detail_status.setStyleSheet(
            "background: transparent; color: #167A65; border: 0; font-weight: 650;"
            if ready
            else "background: transparent; color: #A36724; border: 0; font-weight: 650;"
        )
        self._group_file_count.setText(str(summary.file_count))
        self._group_size.setText(format_size(summary.total_size_bytes))
        self._group_updated.setText(summary.latest_modified_at)
        self._group_path.setText(summary.relative_path)
        self._group_output.set_output(run_group_adapter(group_key, self._group_query.text(), self._project_root))
        self._animate_text_reveal((self._page_title, self._page_subtitle), 45, 300)

    def _animate_page(self, page: QWidget) -> None:
        if self._page_animation is not None:
            self._page_animation.stop()
        if self._animated_page is not None:
            self._animated_page.setGraphicsEffect(None)

        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(220)
        animation.setStartValue(0.64)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: page.setGraphicsEffect(None))
        self._page_animation = animation
        self._animated_page = page
        animation.start()

    def _animate_overview_intro(self) -> None:
        widgets = getattr(self, "_hero_reveal_widgets", ())
        self._animate_text_reveal(widgets, 85, 520)

    def _animate_text_reveal(
        self,
        widgets: tuple[QWidget, ...],
        delay_step: int,
        duration: int,
    ) -> None:
        for index, widget in enumerate(widgets):
            QTimer.singleShot(
                index * delay_step,
                lambda target=widget: self._start_text_reveal(target, duration),
            )

    def _start_text_reveal(self, widget: QWidget, duration: int) -> None:
        if not widget.isVisible():
            return
        previous = self._reveal_animations.pop(widget, None)
        if previous is not None:
            previous.stop()
        if widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.08)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(0.08)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish() -> None:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)
            if self._reveal_animations.get(widget) is animation:
                self._reveal_animations.pop(widget, None)

        animation.finished.connect(finish)
        self._reveal_animations[widget] = animation
        animation.start()

    def _refresh_from_scan(self) -> None:
        ready = sum(group.status == "可整合" for group in self._scan.groups)
        output_files = self._output_files()
        if hasattr(self, "_stat_ready"):
            self._stat_ready.update_value(f"{ready}/{len(self._scan.groups)}", "来源数据已完成接入")
            self._stat_assets.update_value(str(len(self._scan.assets)), "统一资源库")
            self._stat_terms.update_value(str(self._scan.terminology.count), "翻译时自动约束")
            self._stat_outputs.update_value(str(len(output_files)), "可直接使用的成品")
        if hasattr(self, "_scan_time_label"):
            self._scan_time_label.setText(f"最近扫描：{self._scan.scanned_at}  ·  项目根目录已连接")

        unified_messages = (
            "图文通道已纳入统一资源库：审校清单、回填成品、SVG 和逐页渲染证据可直接打开。",
            "术语与儿童文学风格约束已接入智能翻译，审校表仍保留人工最终决定权。",
            "DOCX 与音频通道可直接生成审校表、版式保留回填文档和英文语音成品。",
        )
        for label, message in zip(getattr(self, "_advice_labels", ()), unified_messages):
            label.setText(message)

        hero_items = [
            f"{len(self._scan.assets)} 项统一资源",
            f"{self._scan.terminology.count} 条术语约束",
            "5 套 DOCX 实测通过",
            f"{len(output_files)} 个成品可交付",
        ]
        for label, text in zip(getattr(self, "_hero_status_labels", ()), hero_items):
            label.setText(text)

        providers: list[str] = []
        if self._config.has_api_key:
            providers.append("OpenAI")
        if self._config.has_coze_workflow:
            providers.append("扣子")
        online = bool(providers)
        api_text = f"{' + '.join(providers)} 已连接" if online else "本地模式"
        self._api_state.setText("在线翻译可用" if online else "本地功能可用")
        self._api_state.setProperty("connected", online)
        self._api_state.style().unpolish(self._api_state)
        self._api_state.style().polish(self._api_state)
        channel_details = [f"OpenAI {self._config.openai_model}", "Coze workflow"]
        self._model_label.setText(" · ".join(channel_details))
        self._model_label.setToolTip(
            f"OpenAI model: {self._config.openai_model}\n"
            f"Coze workflow ID: {self._config.coze_workflow_id or 'not configured'}"
        )
        if online:
            self._agent_state_text.setText(
                f"{'、'.join(providers)} 已连接。粘贴中文后即可生成真实译文。"
            )
        else:
            self._agent_state_text.setText(
                "还没有配置在线密钥。Word 回填和英文配音照常可用；"
                "想先了解多模型精译，可以直接打开扣子的离线演示。"
            )
        self._agent_state_dot.setProperty("connected", online)
        self._agent_state_dot.style().unpolish(self._agent_state_dot)
        self._agent_state_dot.style().polish(self._agent_state_dot)

        output_path = output_dir_for(self._project_root)
        self._output_path_label.setText("双击下方文件即可打开；完整成品可从右侧文件夹进入")
        self._output_path_label.setToolTip(str(output_path))
        self._refresh_outputs_table()
        self._refresh_resource_table()
        self._search_terms_now()
        self._append_log("协作区扫描完成")

    def _scan_now(self) -> None:
        if self._thread is not None:
            return
        self.statusBar().showMessage("正在扫描协作区…")
        QApplication.processEvents()
        self._config = load_config()
        self._scan = scan_collaboration(self._project_root)
        self._refresh_from_scan()
        self.statusBar().showMessage(f"扫描完成  ·  {len(self._scan.assets)} 个资源文件", 5000)

    def _run_agent(self) -> None:
        checked = self._agent_modes.checkedButton()
        mode = str(checked.property("mode")) if checked is not None else "agent"
        if mode == "coze_workflow" and not self._config.has_coze_workflow:
            self._show_coze_demo()
            return
        title = self._agent_title.text().strip()
        prompt = self._agent_input.toPlainText()
        if title and mode != "coze_workflow":
            prompt = f"标题/来源：{title}\n\n正文/任务：\n{prompt}"
        self._start_job(mode, prompt, title=title)

    def _update_agent_mode_guide(self, mode: str) -> None:
        guides = {
            "agent": (
                "languages",
                "#3E8D7B",
                "快速翻译",
                "适合短句、说明文字和临时内容，直接生成一版自然英文。",
                "一次模型调用 · 速度最快 · 可继续人工修改",
            ),
            "default_workflow": (
                "clipboard-check",
                "#6D88B6",
                "精译模式",
                "先生成初译，再检查表达和文化信息，最后润色为可读终稿。",
                "初译 → 自检 → 润色 · 适合正式说明和儿童文学",
            ),
            "coze_workflow": (
                "route",
                "#E69063",
                "多模型精译（扣子）",
                "它会先找出文化术语和文体要求，再让 Kimi、DeepSeek、豆包分别翻译、互相评议，最后由 GLM 合成终稿。",
                "真实工作流 · 18 个节点 · 28 条连接 · 图结构校验通过",
            ),
        }
        icon_name, color, title, detail, proof = guides.get(mode, guides["agent"])
        self._agent_mode_icon.setPixmap(make_icon(icon_name, color, 19).pixmap(19, 19))
        self._agent_mode_title.setText(title)
        self._agent_mode_detail.setText(detail)
        self._agent_mode_proof.setText(proof)
        is_coze = mode == "coze_workflow"
        self._coze_demo_button.setVisible(is_coze)
        if is_coze:
            self._agent_run_button.setText(
                "运行多模型精译" if self._config.has_coze_workflow else "查看离线演示"
            )
        elif mode == "default_workflow":
            self._agent_run_button.setText("开始精译")
        else:
            self._agent_run_button.setText("生成译文")

    def _show_coze_demo(self) -> None:
        for button in self._agent_modes.buttons():
            if button.property("mode") == "coze_workflow":
                button.setChecked(True)
                break
        self._update_agent_mode_guide("coze_workflow")
        self._agent_title.setText("端午节儿童故事")
        self._agent_input.setPlainText(
            "端午节这天，孩子们把香囊挂在胸前，和家人一起看龙舟。"
            "请译成自然、生动、适合儿童朗读的英文。"
        )
        self._agent_output.set_output(
            "# 多模型精译流程演示\n\n"
            "**演示状态**：根据仓库中的真实扣子工作流配置离线还原，未发起网络请求。\n\n"
            "## 这套流程做了什么\n\n"
            "1. **文化术语提取**：识别“端午节、香囊、龙舟”，优先采用术语库中的统一译法。\n"
            "2. **读者与风格判断**：目标读者是儿童，要求句子短、画面感清楚、适合朗读。\n"
            "3. **三路独立初译**：Kimi、DeepSeek、豆包分别给出译文，避免单一模型偏差。\n"
            "4. **交叉评估与辩论**：三路模型比较文化准确性、自然度和儿童语气。\n"
            "5. **融合终稿**：GLM 汇总术语、风格和互评意见，只输出可供人工审校的英文。\n\n"
            "## 示例终稿\n\n"
            "On the Dragon Boat Festival, children wear fragrant sachets and watch the dragon boat races "
            "with their families.\n\n"
            "## 可验证证据\n\n"
            "- 工作流 ID：`7661678571702747178`\n"
            "- 结构：18 个节点、28 条连接、3 个代码聚合节点\n"
            "- 校验：起点与终点连通，代码节点样例全部通过\n"
            "- 知识库：已接入中国文化术语库\n\n"
            "> 配置扣子 Token 后，“查看离线演示”会变为“运行多模型精译”，直接执行线上工作流。"
        )
        self.statusBar().showMessage("已打开扣子多模型精译离线演示", 5000)

    def _open_coze_showcase(self) -> None:
        self._switch_page("agent")
        self._show_coze_demo()

    def _clear_agent_input(self) -> None:
        self._agent_title.clear()
        self._agent_input.clear()

    def _insert_translation_example(self) -> None:
        self._agent_title.setText("端午节儿童故事")
        self._agent_input.setPlainText(
            "端午节这天，孩子们把香囊挂在胸前，和家人一起看龙舟。"
            "请译成自然、生动、适合儿童朗读的英文。"
        )
        self._agent_output.set_output(
            "### 示例译文\n\n"
            "On the Dragon Boat Festival, children wear fragrant sachets and watch the dragon boat races "
            "with their families.\n\n"
            "**表达说明**：保留节日名称与“香囊”“龙舟”的文化信息，句子简短，适合儿童朗读。"
        )
        self.statusBar().showMessage("翻译示例已载入，可以修改中文或直接查看结果", 5000)

    def _run_group_adapter(self) -> None:
        self._start_job(f"adapter:{self._active_group}", self._group_query.text(), allow_empty=True)

    def _run_current_page(self) -> None:
        if self._current_page_key == "agent":
            self._run_agent()
        elif self._current_page_key == "production":
            self._run_docx_extract()
        elif self._current_page_key == "group":
            self._run_group_adapter()
        else:
            self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)

    def _start_job(
        self,
        mode: str,
        prompt: str = "",
        allow_empty: bool = False,
        title: str = "",
    ) -> None:
        prompt = prompt.strip()
        if not prompt and not allow_empty:
            QMessageBox.information(self, "需要输入", "请先输入要处理的内容。")
            return
        if self._thread is not None:
            return

        self._active_mode = mode
        self._set_busy(True)
        self._append_log(f"开始任务：{mode}")
        self._thread = QThread(self)
        self._worker = JobWorker(mode, prompt, self._project_root, title)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._handle_progress)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._release_worker)
        self._thread.start()

    @Slot(str)
    def _handle_progress(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self._append_log(message)

    @Slot(str)
    def _handle_finished(self, text: str) -> None:
        if self._active_mode.startswith("production:"):
            payload = json.loads(text)
            artifacts = [str(item) for item in payload.get("artifacts", [])]
            kind = str(payload.get("kind", ""))
            self._production_output.set_output(str(payload.get("message", "处理完成")))
            if artifacts and kind in {"docx-review", "docx-translated-review"}:
                self._docx_review.setText(artifacts[0])
            elif artifacts and kind in {"audio-review", "audio-translated-review"}:
                self._audio_review.setText(artifacts[0])
            self._switch_page("production")
        elif self._active_mode == "report":
            self._delivery_output.set_output(text)
            self._switch_page("outputs")
        elif self._active_mode.startswith("adapter:"):
            self._group_output.set_output(text)
            self._show_group(self._active_mode.partition(":")[2])
        elif self._active_mode == "integration_workflow":
            self._workflow_output.set_output(text)
            self._switch_page("workflow")
        else:
            self._agent_output.set_output(text)
            self._switch_page("agent")

        self._scan = scan_collaboration(self._project_root)
        self._refresh_from_scan()
        self.statusBar().showMessage("任务已完成", 5000)
        self._append_log(f"任务完成：{self._active_mode}")

    @Slot(str)
    def _handle_failed(self, message: str) -> None:
        self.statusBar().showMessage("任务执行失败")
        self._append_log(f"任务失败：{message}")
        QMessageBox.critical(self, "执行失败", message)

    @Slot()
    def _release_worker(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        for control in self._busy_controls:
            control.setEnabled(not busy)
        self._progress.setVisible(busy)
        self._top_run_button.setText("处理中…" if busy else "导入素材")
        if busy:
            self._agent_run_button.setText("生成中…")
        else:
            checked = self._agent_modes.checkedButton()
            current_mode = str(checked.property("mode")) if checked is not None else "agent"
            self._update_agent_mode_guide(current_mode)
        self._workflow_run_button.setText("批量处理中…" if busy else "开始批量处理")
        if hasattr(self, "_report_button"):
            self._report_button.setToolTip("报告生成中…" if busy else "生成整合报告")
        if hasattr(self, "_group_run_button"):
            self._group_run_button.setText("处理中…" if busy else "运行")
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
            self._update_production_actions()

    def _search_terms_now(self) -> None:
        records = search_terms(self._term_search.text(), self._project_root, limit=200)
        self._term_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                str(record.get("术语", "")),
                str(record.get("英文翻译", "")),
                str(record.get("出处页码", "")),
                str(record.get("上下文片段", "")),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter
                    | (Qt.AlignmentFlag.AlignCenter if column == 2 else Qt.AlignmentFlag.AlignLeft)
                )
                self._term_table.setItem(row, column, item)
        query = self._term_search.text().strip()
        suffix = f"“{query}”的匹配结果" if query else "术语库预览（最多显示 200 条）"
        self._term_count_label.setText(f"{len(records)} 条  ·  {suffix}")

    def _append_selected_term_to_agent(self) -> None:
        rows = self._term_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        term = self._term_table.item(row, 0).text()
        english = self._term_table.item(row, 1).text()
        constraint = f"术语约束：{term} → {english}"
        existing = self._agent_input.toPlainText().strip()
        self._agent_input.setPlainText(f"{existing}\n\n{constraint}".strip())
        self._switch_page("agent")
        self.statusBar().showMessage(f"已加入术语约束：{term}", 4000)

    def _output_files(self) -> list[Path]:
        out_dir = output_dir_for(self._project_root)
        try:
            return sorted(
                (path for path in out_dir.iterdir() if path.is_file()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []

    def _refresh_outputs_table(self) -> None:
        files = self._output_files()[:60]
        self._output_table.setRowCount(len(files))
        for row, path in enumerate(files):
            stat = path.stat()
            values = (
                path.name,
                path.suffix.lstrip(".").upper() or "FILE",
                datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                format_size(stat.st_size),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self._output_table.setItem(row, column, item)

    def _open_output_file(self, row: int, column: int) -> None:
        item = self._output_table.item(row, column)
        if item is None:
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _copy_view(self, view: MarkdownView) -> None:
        text = view.toPlainText().strip()
        if not text:
            self.statusBar().showMessage("当前没有可复制的结果", 3000)
            return
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("结果已复制", 3000)

    def _save_view(self, view: MarkdownView, default_name: str) -> None:
        text = view.raw_text().strip()
        if not text:
            QMessageBox.information(self, "没有输出", "当前没有可保存的结果。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存输出",
            str(output_dir_for(self._project_root) / default_name),
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self.statusBar().showMessage(f"已保存：{path}", 5000)
        self._append_log(f"已保存输出：{path}")

    def _save_current_output(self) -> None:
        views = {
            "agent": (self._agent_output, "agent-output.md"),
            "production": (self._production_output, "production-output.md"),
            "workflow": (self._workflow_output, "workflow-output.md"),
            "outputs": (self._delivery_output, "integration-output.md"),
            "group": (self._group_output, f"group-{self._active_group}-adapter.md"),
        }
        view_info = views.get(self._current_page_key)
        if view_info is None:
            self.statusBar().showMessage("当前页面没有可保存的文本结果", 3000)
            return
        self._save_view(*view_info)

    def _open_output_dir(self) -> None:
        out_dir = output_dir_for(self._project_root)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
        self._append_log(f"打开输出目录：{out_dir}")

    def _open_acceptance_record(self) -> None:
        record = (
            self._project_root
            / "collaboration"
            / "integration"
            / "final_outputs"
            / "INTEGRATION_ACCEPTANCE_20260718.md"
        )
        if record.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(record)))
            self._append_log(f"打开验收记录：{record}")
            return
        QMessageBox.warning(self, "验收记录不存在", f"未找到文件：\n{record}")

    def _open_group_dir(self) -> None:
        directory = GROUPS[self._active_group][0]
        path = self._project_root / "collaboration" / "groups" / directory
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self._append_log(f"打开 {self._active_group} 组目录：{path}")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log.appendPlainText(f"{timestamp}  {message}")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            * {
                font-family: "Noto Sans SC", "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 13px;
                color: #172033;
                outline: 0;
            }
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack {
                background: #F5F7FA;
            }
            QFrame#Sidebar {
                background: #FBFCFE;
                border: 0;
                border-right: 1px solid #E1E7EF;
            }
            QLabel#BrandTitle {
                color: #172033;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#BrandSubtitle {
                color: #7A8699;
                font-size: 11px;
            }
            QLabel#SidebarLabel {
                color: #98A2B3;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 10px;
            }
            QPushButton#NavButton, QPushButton#GroupNavButton {
                background: transparent;
                color: #526077;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
                min-height: 21px;
            }
            QPushButton#NavButton:hover, QPushButton#GroupNavButton:hover {
                background: #EEF3F9;
                color: #25324A;
            }
            QPushButton#NavButton:checked {
                background: #EAF1FF;
                color: #245FCC;
                font-weight: 600;
                border: 1px solid #D7E4FC;
            }
            QPushButton#GroupNavButton {
                color: #667085;
                font-size: 12px;
                padding-left: 13px;
            }
            QPushButton#GroupNavButton[ready="true"] {
                color: #344054;
            }
            QFrame#ConnectionPanel {
                background: #FFFFFF;
                border: 1px solid #DFE5EC;
                border-radius: 7px;
            }
            QLabel#ApiState {
                color: #B36B12;
                font-weight: 600;
            }
            QLabel#ApiState[connected="true"] {
                color: #12805C;
            }
            QLabel#ModelLabel {
                color: #98A2B3;
                font-size: 11px;
            }
            QFrame#TopBar {
                background: #FFFFFF;
                border: 0;
                border-bottom: 1px solid #E1E7EF;
            }
            QFrame#HeroPanel {
                background: #FFFFFF;
                border: 1px solid #DFE5EC;
                border-radius: 8px;
            }
            QLabel#HeroEyebrow {
                color: #2F6FED;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0;
            }
            QLabel#HeroTitle {
                color: #172033;
                font-size: 27px;
                font-weight: 700;
            }
            QLabel#HeroSubtitle {
                color: #526077;
                font-size: 13px;
                line-height: 1.45;
            }
            QFrame#HeroStatusPanel {
                background: #F6F8FB;
                border: 1px solid #E1E7EF;
                border-radius: 8px;
            }
            QLabel#HeroStatusTitle {
                color: #25324A;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#HeroStatusItem {
                color: #526077;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton#HeroPrimary {
                background: #2F6FED;
                color: #FFFFFF;
                border: 1px solid #2F6FED;
                border-radius: 7px;
                padding: 10px 16px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton#HeroPrimary:hover {
                background: #245FCC;
                border-color: #245FCC;
            }
            QPushButton#HeroPrimary:pressed {
                background: #1D4FAF;
                border-color: #1D4FAF;
            }
            QPushButton#HeroSecondary {
                background: #FFFFFF;
                color: #344054;
                border: 1px solid #C8D4E3;
                border-radius: 7px;
                padding: 10px 14px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton#HeroSecondary:hover {
                background: #F7FAFF;
                border-color: #91A8C8;
            }
            QPushButton#HeroSecondary:pressed {
                background: #EDF3FA;
            }
            QLabel#PageTitle {
                color: #172033;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#PageSubtitle, QLabel#SectionSubtitle, QLabel#PathLabel {
                color: #7A8699;
                font-size: 12px;
            }
            QLabel#PathLabel {
                font-family: Consolas;
            }
            QToolButton#IconButton {
                background: #FFFFFF;
                border: 1px solid #D9E1EA;
                border-radius: 6px;
                min-width: 35px;
                min-height: 35px;
            }
            QToolButton#IconButton:hover {
                background: #EEF4FF;
                border-color: #AFC6EE;
            }
            QToolButton#IconButton:pressed {
                background: #DCE9FF;
                border-color: #7FA4E5;
            }
            QToolButton#IconButton:focus {
                border: 1px solid #6C96E8;
            }
            QPushButton#PrimaryButton {
                background: #2F6FED;
                color: #FFFFFF;
                border: 1px solid #2F6FED;
                border-radius: 6px;
                padding: 9px 16px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton#PrimaryButton:hover {
                background: #245FCC;
                border-color: #245FCC;
            }
            QPushButton#PrimaryButton:pressed {
                background: #1D4FAF;
                border-color: #1D4FAF;
            }
            QPushButton#PrimaryButton:focus {
                border: 1px solid #17479F;
            }
            QPushButton#PrimaryButton:disabled {
                background: #AFC5EE;
                border-color: #AFC5EE;
            }
            QPushButton#SecondaryButton {
                background: #FFFFFF;
                color: #344054;
                border: 1px solid #D6DEE8;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton#SecondaryButton:hover {
                background: #F3F7FC;
                border-color: #AFC0D4;
            }
            QPushButton#SecondaryButton:pressed {
                background: #E8EEF6;
            }
            QPushButton#SecondaryButton:focus {
                border: 1px solid #6C96E8;
            }
            QPushButton#SecondaryButton:disabled {
                color: #98A2B3;
                background: #F2F5F9;
                border-color: #E4E9EF;
            }
            QPushButton#TextButton, QPushButton#CardAction {
                background: transparent;
                color: #2F6FED;
                border: 0;
                padding: 7px 2px;
                font-weight: 600;
            }
            QPushButton#TextButton:hover, QPushButton#CardAction:hover {
                color: #1D4FAF;
            }
            QLabel#SectionTitle {
                color: #25324A;
                font-size: 15px;
                font-weight: 700;
            }
            QFrame#StatCard, QFrame#GroupCard, QFrame#SectionPanel, QFrame#ToolPanel, QFrame#WorkflowNode, QFrame#TaskEntryCard {
                background: #FFFFFF;
                border: 1px solid #DFE5EC;
                border-radius: 8px;
            }
            QFrame#TaskEntryCard:hover {
                border: 1px solid #AFC5E8;
                background: #FBFDFF;
            }
            QLabel#TaskKicker {
                color: #7A8699;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#TaskTitle {
                color: #172033;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#TaskBody {
                color: #526077;
                font-size: 12px;
                line-height: 1.45;
            }
            QPushButton#TaskPrimary {
                background: #25324A;
                color: #FFFFFF;
                border: 1px solid #25324A;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton#TaskPrimary:hover {
                background: #344563;
                border-color: #344563;
            }
            QPushButton#TaskPrimary:pressed {
                background: #172033;
            }
            QPushButton#TaskSecondary {
                background: #F2F5F9;
                color: #344054;
                border: 1px solid #DFE5EC;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton#TaskSecondary:hover {
                background: #E7EDF5;
                border-color: #C6D0DC;
            }
            QPushButton#TaskSecondary:pressed {
                background: #DCE4EE;
            }
            QLabel#StatLabel {
                color: #667085;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#StatValue {
                color: #172033;
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#StatDetail {
                color: #98A2B3;
                font-size: 11px;
            }
            QLabel#GroupTitle {
                color: #172033;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#GroupSubtitle, QLabel#GroupDescription, QLabel#GroupMetrics, QLabel#CategoryLine {
                color: #7A8699;
                font-size: 11px;
            }
            QLabel#GroupDescription {
                color: #526077;
                font-size: 12px;
            }
            QLabel#GroupMetrics {
                color: #344054;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#CategoryLine {
                background: transparent;
                border-radius: 0;
                padding: 3px 0;
                color: #667085;
            }
            QLabel#StageBadge, QLabel#WorkflowNumber {
                background: #EAF1FF;
                color: #2F6FED;
                border-radius: 6px;
                font-weight: 700;
            }
            QLabel#StageTitle, QLabel#WorkflowTitle {
                color: #25324A;
                font-weight: 600;
            }
            QLabel#StageDetail, QLabel#WorkflowDetail {
                color: #7A8699;
                font-size: 11px;
            }
            QLabel#ReadyText {
                color: #12805C;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#AdviceItem {
                color: #526077;
                line-height: 1.4;
            }
            QFrame#Divider {
                color: #E6EBF1;
                max-height: 1px;
                border: 0;
                background: #E6EBF1;
            }
            QFrame#InfoBanner {
                background: #EEF4FF;
                border: 1px solid #D6E4FB;
                border-radius: 7px;
            }
            QLabel#ProductionPreview {
                background: #EEF2F7;
                border: 1px solid #D9E1EB;
                border-radius: 7px;
                padding: 8px;
            }
            QLabel#AgentStateDot {
                color: #B36B12;
            }
            QLabel#AgentStateDot[connected="true"] {
                color: #12805C;
            }
            QLabel#InfoText {
                color: #526077;
                font-size: 12px;
            }
            QPushButton#SegmentButton {
                background: #EEF2F7;
                color: #667085;
                border: 1px solid #D9E1EA;
                padding: 8px 13px;
            }
            QPushButton#SegmentButton:first {
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
            }
            QPushButton#SegmentButton:last {
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QPushButton#SegmentButton:checked {
                background: #FFFFFF;
                color: #245FCC;
                border-color: #8FB0E8;
                font-weight: 600;
            }
            QPushButton#SegmentButton:hover {
                color: #344054;
                background: #F8FAFD;
            }
            QPlainTextEdit#InputEditor, QPlainTextEdit#WorkflowInput, QLineEdit#SearchInput,
            QTextBrowser#OutputView, QPlainTextEdit#LogView {
                background: #FFFFFF;
                color: #25324A;
                border: 1px solid #D9E1EA;
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #DCE9FF;
            }
            QPlainTextEdit#InputEditor:focus, QPlainTextEdit#WorkflowInput:focus, QLineEdit#SearchInput:focus {
                border: 1px solid #5D8FE9;
            }
            QLineEdit#SearchInput {
                min-height: 24px;
                padding: 8px 11px;
            }
            QTableWidget#DataTable {
                background: #FFFFFF;
                alternate-background-color: #F8FAFD;
                border: 1px solid #DFE5EC;
                border-radius: 6px;
                gridline-color: #E8EDF3;
                selection-background-color: #E4EEFF;
                selection-color: #172033;
            }
            QTableWidget#DataTable::item {
                padding: 6px;
                border: 0;
            }
            QHeaderView::section {
                background: #F1F5F9;
                color: #526077;
                border: 0;
                border-bottom: 1px solid #D9E1EA;
                padding: 9px 8px;
                font-weight: 600;
            }
            QScrollArea#PageScroll, QWidget#OverviewContent {
                background: #F5F7FA;
            }
            QProgressBar#TaskProgress {
                background: #DCE5F2;
                border: 0;
            }
            QProgressBar#TaskProgress::chunk {
                background: #2F6FED;
            }
            QTabWidget#ResultTabs::pane {
                background: #FFFFFF;
                border: 1px solid #DFE5EC;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #667085;
                padding: 8px 14px;
                border: 0;
            }
            QTabBar::tab:hover {
                color: #344054;
                background: #F2F6FB;
            }
            QTabBar::tab:selected {
                color: #245FCC;
                font-weight: 600;
                border-bottom: 2px solid #2F6FED;
            }
            QLabel#DetailTitle {
                color: #172033;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#InfoLabel {
                color: #7A8699;
                font-size: 11px;
            }
            QLabel#InfoValue {
                color: #25324A;
                font-weight: 600;
            }
            QStatusBar {
                background: #FFFFFF;
                color: #667085;
                border-top: 1px solid #E1E7EF;
                padding-left: 8px;
            }
            QSplitter::handle {
                background: #F5F7FA;
                width: 10px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #B8C3D1;
                border-radius: 4px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #98A8BC;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            * {
                color: #1B2420;
                outline: 0;
            }
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack,
            QScrollArea#PageScroll, QWidget#OverviewContent {
                background: #F2F4F1;
            }
            QFrame#Sidebar {
                background: #171C1A;
                border: 0;
                border-right: 1px solid #29312D;
            }
            QLabel#BrandTitle {
                color: #F7F9F7;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#BrandSubtitle {
                color: #8F9B95;
                font-size: 11px;
            }
            QFrame#SidebarRule {
                background: #303834;
                border: 0;
            }
            QLabel#SidebarLabel {
                color: #707D76;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 10px;
            }
            QPushButton#NavButton, QPushButton#GroupNavButton {
                background: transparent;
                color: #A8B2AD;
                border: 0;
                border-left: 3px solid transparent;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
                min-height: 22px;
            }
            QPushButton#NavButton:hover, QPushButton#GroupNavButton:hover {
                background: #202724;
                color: #EDF2EF;
            }
            QPushButton#NavButton:checked {
                background: #25302C;
                color: #F8FAF9;
                border: 0;
                border-left: 3px solid #54B398;
                font-weight: 650;
            }
            QPushButton#GroupNavButton {
                color: #89958F;
                font-size: 12px;
            }
            QPushButton#GroupNavButton[ready="true"] {
                color: #C2CBC6;
            }
            QFrame#ConnectionPanel {
                background: #202724;
                border: 1px solid #313A35;
                border-radius: 8px;
            }
            QLabel#ChannelKicker {
                color: #6F7C75;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#ApiState {
                color: #D9A258;
                font-size: 12px;
                font-weight: 650;
            }
            QLabel#ApiState[connected="true"] {
                color: #6EC3A8;
            }
            QLabel#ModelLabel {
                color: #7F8C85;
                font-size: 10px;
            }
            QFrame#TopBar {
                background: #FCFDFC;
                border: 0;
                border-bottom: 1px solid #DDE3DE;
            }
            QLabel#PageTitle {
                color: #18201D;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 21px;
                font-weight: 700;
            }
            QLabel#PageSubtitle, QLabel#SectionSubtitle, QLabel#PathLabel {
                color: #78837D;
                font-size: 12px;
            }
            QLabel#RepositoryState {
                background: rgba(229, 242, 236, 205);
                color: #236D5B;
                border: 1px solid rgba(174, 207, 193, 190);
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QFrame#HeroPanel {
                background: #18201D;
                border: 1px solid #18201D;
                border-radius: 8px;
            }
            QFrame#ReadinessBand {
                background: transparent;
                border: 0;
                border-radius: 8px;
            }
            QLabel#ReadinessLabel {
                color: #77827C;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#ReadinessValue {
                color: #167A65;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 21px;
                font-weight: 700;
            }
            QFrame#ReadinessDivider {
                background: #DDE3DF;
                border: 0;
            }
            QLabel#ReadinessTitle {
                color: #26312C;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#ReadinessSummary {
                color: #6A756F;
                font-size: 11px;
            }
            QLabel#ReadinessPending {
                background: #FFF5E8;
                color: #9A641F;
                border: 1px solid #EED5B3;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#HeroEyebrow {
                color: #68C1A7;
                font-size: 10px;
                font-weight: 750;
            }
            QLabel#HeroTitle {
                color: #F8FAF8;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 29px;
                font-weight: 700;
            }
            QLabel#HeroSubtitle {
                color: #B7C2BC;
                font-size: 13px;
            }
            QLabel#HeroPill {
                background: rgba(255, 255, 255, 18);
                color: #C4CEC8;
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 5px;
                padding: 5px 9px;
                font-size: 10px;
                font-weight: 600;
            }
            QFrame#HeroStatusPanel {
                background: transparent;
                border: 0;
                border-left: 1px solid #39443F;
                border-radius: 0;
            }
            QLabel#HeroStatusTitle {
                color: #F1F5F2;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#HeroStatusItem {
                color: #AEBAB4;
                font-size: 12px;
            }
            QPushButton#HeroPrimary, QPushButton#PrimaryButton {
                background: #167A65;
                color: #FFFFFF;
                border: 1px solid #167A65;
                border-radius: 6px;
                padding: 9px 16px;
                font-weight: 650;
                min-height: 20px;
            }
            QPushButton#HeroPrimary:hover, QPushButton#PrimaryButton:hover {
                background: #116B58;
                border-color: #116B58;
            }
            QPushButton#HeroPrimary:pressed, QPushButton#PrimaryButton:pressed {
                background: #0B5748;
                border-color: #0B5748;
            }
            QPushButton#PrimaryButton:focus {
                border: 1px solid #74BBA7;
            }
            QPushButton#PrimaryButton:disabled {
                background: #A9C8BE;
                border-color: #A9C8BE;
            }
            QPushButton#HeroSecondary {
                background: transparent;
                color: #E6ECE8;
                border: 1px solid #56635D;
                border-radius: 6px;
                padding: 9px 14px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton#HeroSecondary:hover {
                background: #252E2A;
                border-color: #7A8981;
            }
            QToolButton#HeroIconButton {
                background: transparent;
                border: 1px solid #56635D;
                border-radius: 6px;
            }
            QToolButton#HeroIconButton:hover {
                background: #252E2A;
                border-color: #7A8981;
            }
            QToolButton#HeroIconButton:pressed {
                background: #101713;
            }
            QToolButton#IconButton {
                background: #FCFDFC;
                border: 1px solid #D6DED8;
                border-radius: 6px;
                min-width: 37px;
                min-height: 37px;
            }
            QToolButton#IconButton:hover {
                background: #EEF4F0;
                border-color: #AFC9BF;
            }
            QToolButton#IconButton:pressed {
                background: #E1EBE6;
                border-color: #7EAA9A;
            }
            QPushButton#SecondaryButton {
                background: #FFFFFF;
                color: #29342F;
                border: 1px solid #D2DAD5;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton#SecondaryButton:hover {
                background: #F0F5F2;
                border-color: #AABDB4;
            }
            QPushButton#SecondaryButton:pressed {
                background: #E5EDE9;
            }
            QPushButton#TextButton, QPushButton#CardAction {
                background: transparent;
                color: #167A65;
                border: 0;
                padding: 7px 2px;
                font-weight: 650;
            }
            QPushButton#TextButton:hover, QPushButton#CardAction:hover {
                color: #0B5748;
            }
            QLabel#SectionTitle {
                color: #202A25;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 16px;
                font-weight: 700;
            }
            QFrame#StatCard, QFrame#GroupCard, QFrame#SectionPanel,
            QFrame#ToolPanel, QFrame#WorkflowNode, QFrame#TaskEntryCard {
                background: #FFFFFF;
                border: 1px solid #DCE2DD;
                border-radius: 8px;
            }
            QFrame#TaskEntryCard:hover, QFrame#GroupCard:hover {
                background: #FCFDFC;
                border: 1px solid #AFC4BA;
            }
            QLabel#TaskKicker {
                color: #7B8781;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#TaskTitle {
                color: #1B2420;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#TaskBody {
                color: #5E6A64;
                font-size: 12px;
            }
            QPushButton#TaskPrimary {
                background: #202A25;
                color: #FFFFFF;
                border: 1px solid #202A25;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 650;
            }
            QPushButton#TaskPrimary:hover {
                background: #167A65;
                border-color: #167A65;
            }
            QPushButton#TaskPrimary:pressed {
                background: #0B5748;
                border-color: #0B5748;
            }
            QPushButton#TaskSecondary {
                background: #F1F4F2;
                color: #2D3833;
                border: 1px solid #DDE3DF;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton#TaskSecondary:hover {
                background: #E7EEEA;
                border-color: #BFCFC7;
            }
            QToolButton#TaskSecondaryIcon {
                background: #F1F4F2;
                color: #2D3833;
                border: 1px solid #DDE3DF;
                border-radius: 6px;
            }
            QToolButton#TaskSecondaryIcon:hover {
                background: #E7EEEA;
                border-color: #AFC4BA;
            }
            QToolButton#TaskSecondaryIcon:pressed {
                background: #DCE6E1;
            }
            QLabel#StatLabel {
                color: #6A756F;
                font-size: 11px;
                font-weight: 650;
            }
            QLabel#StatValue {
                color: #18201D;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 27px;
                font-weight: 700;
            }
            QLabel#StatDetail {
                color: #919B96;
                font-size: 10px;
            }
            QLabel#GroupTitle {
                color: #1B2420;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#GroupSubtitle, QLabel#GroupDescription, QLabel#GroupMetrics, QLabel#CategoryLine {
                color: #7D8882;
                font-size: 11px;
            }
            QLabel#GroupDescription {
                color: #5D6963;
                font-size: 12px;
            }
            QLabel#GroupMetrics {
                color: #2D3833;
                font-size: 13px;
                font-weight: 650;
            }
            QLabel#StageBadge, QLabel#WorkflowNumber {
                background: #EAF3EF;
                color: #167A65;
                border-radius: 6px;
                font-weight: 700;
            }
            QLabel#StageTitle, QLabel#WorkflowTitle {
                color: #26312C;
                font-weight: 650;
            }
            QLabel#StageDetail, QLabel#WorkflowDetail {
                color: #7E8983;
                font-size: 11px;
            }
            QLabel#WorkflowState {
                background: #EAF3EF;
                color: #167A65;
                border: 1px solid #D0E3DA;
                border-radius: 5px;
                padding: 4px 6px;
                font-size: 9px;
                font-weight: 700;
            }
            QLabel#ReadyText {
                color: #167A65;
                font-size: 11px;
                font-weight: 650;
            }
            QLabel#AdviceItem {
                color: #56625C;
            }
            QFrame#Divider {
                color: #E2E7E3;
                max-height: 1px;
                border: 0;
                background: #E2E7E3;
            }
            QFrame#InfoBanner {
                background: rgba(233, 243, 238, 210);
                border: 1px solid rgba(186, 211, 199, 185);
                border-radius: 7px;
            }
            QLabel#AgentStateDot {
                color: #C17A2C;
            }
            QLabel#AgentStateDot[connected="true"] {
                color: #167A65;
            }
            QLabel#InfoText {
                color: #56625C;
                font-size: 12px;
            }
            QPushButton#SegmentButton {
                background: rgba(229, 235, 231, 210);
                color: #66716B;
                border: 1px solid #D6DDD8;
                border-radius: 5px;
                padding: 8px 13px;
            }
            QPushButton#SegmentButton:checked {
                background: rgba(255, 255, 255, 235);
                color: #126C59;
                border-color: #83B5A5;
                font-weight: 650;
            }
            QPushButton#SegmentButton:hover {
                color: #26312C;
                background: #F8FAF8;
            }
            QPlainTextEdit#InputEditor, QPlainTextEdit#WorkflowInput, QLineEdit#SearchInput,
            QTextBrowser#OutputView, QPlainTextEdit#LogView {
                background: #FCFDFC;
                color: #27312D;
                border: 1px solid #D6DED8;
                border-radius: 6px;
                padding: 11px;
                selection-background-color: #CDE4DB;
            }
            QPlainTextEdit#InputEditor:focus, QPlainTextEdit#WorkflowInput:focus,
            QLineEdit#SearchInput:focus {
                background: #FFFFFF;
                border: 1px solid #4D9B84;
            }
            QTableWidget#DataTable {
                background: #FFFFFF;
                alternate-background-color: #F7F9F7;
                border: 1px solid #DCE2DD;
                border-radius: 6px;
                gridline-color: #E7EBE8;
                selection-background-color: #DCECE5;
                selection-color: #17201C;
            }
            QHeaderView::section {
                background: #EDF1EE;
                color: #59655F;
                border: 0;
                border-bottom: 1px solid #D6DDD8;
                padding: 9px 8px;
                font-weight: 650;
            }
            QProgressBar#TaskProgress {
                background: #DCE5E0;
                border: 0;
            }
            QProgressBar#TaskProgress::chunk {
                background: #39A286;
            }
            QTabWidget#ResultTabs::pane {
                background: #FFFFFF;
                border: 1px solid #DCE2DD;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #6B7771;
                padding: 8px 14px;
                border: 0;
            }
            QTabBar::tab:hover {
                color: #2C3732;
                background: #EEF3F0;
            }
            QTabBar::tab:selected {
                color: #126C59;
                font-weight: 650;
                border-bottom: 2px solid #167A65;
            }
            QLabel#DetailTitle {
                color: #18201D;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#InfoLabel {
                color: #7C8781;
                font-size: 10px;
            }
            QLabel#InfoValue {
                color: #29342F;
                font-weight: 650;
            }
            QStatusBar {
                background: #171C1A;
                color: #9CA7A1;
                border-top: 1px solid #2B332F;
                padding-left: 8px;
            }
            QSplitter::handle {
                background: #F2F4F1;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #AAB5AF;
                border-radius: 4px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7E8D85;
            }
            QToolTip {
                background: #1D2521;
                color: #F3F6F4;
                border: 1px solid #39443F;
                padding: 6px;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack,
            QScrollArea#PageScroll, QWidget#StartContent, QWidget#ShowcaseContent {
                background: #F4F0E8;
            }
            QFrame#Sidebar {
                background: #ECE7DD;
                border: 0;
                border-right: 1px solid #D8D0C3;
            }
            QLabel#BrandTitle {
                color: #2D5F55;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 24px;
                font-weight: 750;
            }
            QLabel#BrandSubtitle {
                color: #8A8175;
                font-size: 7px;
                font-weight: 650;
            }
            QFrame#SidebarRule { background: #D7CFC2; }
            QLabel#SidebarLabel {
                color: #9A9083;
                font-size: 9px;
                font-weight: 700;
                padding: 0 8px 5px 8px;
            }
            QPushButton#NavButton {
                background: transparent;
                color: #5E6B65;
                border: 1px solid transparent;
                border-radius: 6px;
                min-height: 42px;
                padding: 0 12px;
                text-align: left;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#NavButton:hover {
                background: #F5F1EA;
                color: #355E55;
                border-color: #E0D8CC;
            }
            QPushButton#NavButton:checked {
                background: #FBF8F2;
                color: #A9573B;
                border: 1px solid #DDD3C5;
                border-left: 3px solid #C86F4D;
                font-weight: 720;
            }
            QFrame#ConnectionPanel {
                background: #E4DED3;
                border: 1px solid #D4CBBE;
                border-radius: 7px;
            }
            QLabel#ChannelKicker { color: #91877A; }
            QLabel#ApiState { color: #9B624A; font-weight: 700; }
            QLabel#ApiState[connected="true"] { color: #2F7567; }
            QLabel#ModelLabel { color: #786F64; }
            QFrame#TopBar {
                background: #F8F5EE;
                border: 0;
                border-bottom: 1px solid #DED7CB;
            }
            QLabel#TopContext {
                color: #27332F;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 17px;
                font-weight: 720;
            }
            QLabel#PageSubtitle {
                color: #8A8F89;
                font-size: 9px;
            }
            QFrame#IntroPanel { background: transparent; border: 0; }
            QLabel#StartEyebrow {
                color: #5B7D8B;
                font-size: 9px;
                font-weight: 720;
            }
            QLabel#StartTitle {
                color: #284F47;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 43px;
                font-weight: 720;
            }
            QLabel#StartSubtitle {
                color: #6C746E;
                font-size: 12px;
                line-height: 1.55;
            }
            QFrame#HeroFact {
                background: transparent;
                border: 0;
                border-left: 1px solid #CFC7BA;
                padding-left: 10px;
            }
            QLabel#HeroFactValue {
                color: #A85C41;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 18px;
                font-weight: 720;
            }
            QLabel#HeroFactLabel { color: #8A8177; font-size: 8px; }
            QFrame#StartDropZone {
                background: #FCFAF5;
                border: 1px dashed #BEB4A6;
                border-radius: 8px;
            }
            QFrame#StartDropZone:hover {
                background: #FFFCF6;
                border-color: #6E9488;
            }
            QLabel#DropIcon {
                background: #EDF3F0;
                border: 1px solid #D3E1DB;
                border-radius: 8px;
            }
            QLabel#DropTitle { color: #315F56; font-size: 15px; }
            QLabel#DropSubtitle, QLabel#DropFormats { color: #8A8D88; }
            QLabel#ChoiceLabel {
                color: #3E4944;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 14px;
                font-weight: 700;
                padding-top: 3px;
            }
            QPushButton#QuickStartButton {
                background: #FAF8F3;
                color: #46534D;
                border: 1px solid #DCD4C8;
                border-radius: 7px;
                min-height: 64px;
                padding: 10px 16px;
                text-align: left;
                font-size: 11px;
                font-weight: 650;
            }
            QPushButton#QuickStartButton:hover {
                background: #FFFDF8;
                color: #2E4E47;
                border-color: #AFA496;
            }
            QPushButton#QuickStartButton[accent="coral"] {
                background: #FAF8F3; color: #87503B; border-left: 3px solid #C86F4D;
            }
            QPushButton#QuickStartButton[accent="blue"] {
                background: #FAF8F3; color: #4A6875; border-left: 3px solid #587E91;
            }
            QPushButton#QuickStartButton[accent="jade"] {
                background: #FAF8F3; color: #35675C; border-left: 3px solid #327568;
            }
            QPushButton#QuickStartButton[accent="gold"] {
                background: #FAF8F3; color: #79633E; border-left: 3px solid #A88952;
            }
            QFrame#OutcomeBand {
                background: #EEEAE2;
                border: 1px solid #D9D1C5;
                border-radius: 7px;
            }
            QLabel#OutcomeTitle { color: #6A6258; }
            QLabel#OutcomeItem { color: #656E69; }
            QFrame#FirstTimePanel {
                background: #F6EDE5;
                border: 1px solid #E5CDBE;
                border-radius: 8px;
            }
            QLabel#SampleTitle {
                color: #8B4C35;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 14px;
            }
            QLabel#SampleDescription { color: #766B63; }
            QPushButton#TopPrimaryButton, QPushButton#DropBrowseButton,
            QPushButton#PrimaryButton {
                background: #B96144;
                color: #FFFFFF;
                border-color: #B96144;
            }
            QPushButton#TopPrimaryButton:hover, QPushButton#DropBrowseButton:hover,
            QPushButton#PrimaryButton:hover {
                background: #A75338;
                border-color: #A75338;
            }
            QStatusBar {
                background: #F8F5EE;
                color: #88837A;
                border-top: 1px solid #DED7CB;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            * {
                font-family: "Noto Sans SC";
                letter-spacing: 0;
            }
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack,
            QScrollArea#PageScroll, QWidget#StartContent, QWidget#ShowcaseContent {
                background: #F7F5F0;
            }
            QFrame#TopBar {
                background: #FCFBF8;
                border: 0;
                border-bottom: 1px solid #E5E1D9;
            }
            QLabel#TopBrand {
                color: #1E2925;
                font-size: 17px;
                font-weight: 750;
            }
            QLabel#TopContext {
                color: #89918D;
                font-size: 10px;
                font-weight: 550;
            }
            QPushButton#TopNavButton {
                background: transparent;
                color: #707874;
                border: 0;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                padding: 10px 12px 9px 12px;
                font-size: 12px;
                font-weight: 560;
            }
            QPushButton#TopNavButton:hover {
                color: #23312C;
                background: #F3F0EA;
            }
            QPushButton#TopNavButton:checked {
                color: #1F332C;
                border-bottom: 2px solid #2F6658;
                font-weight: 700;
            }
            QLabel#ModeChip {
                background: #EDF4F0;
                color: #2F6658;
                border: 1px solid #D3E4DC;
                border-radius: 7px;
                padding: 7px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#ModeChip[connected="true"] {
                background: #EAF2FF;
                color: #315F9A;
                border-color: #CADAF0;
            }
            QToolButton#TopIconButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
                min-width: 34px;
                min-height: 34px;
            }
            QToolButton#TopIconButton:hover {
                background: #F0EDE6;
                border-color: #E1DDD4;
            }
            QPushButton#TopPrimaryButton {
                background: #263833;
                color: #FFFFFF;
                border: 1px solid #263833;
                border-radius: 7px;
                padding: 8px 14px;
                min-height: 18px;
                font-weight: 680;
            }
            QPushButton#TopPrimaryButton:hover {
                background: #2F6658;
                border-color: #2F6658;
            }
            QPushButton#TopPrimaryButton:pressed {
                background: #234F43;
                border-color: #234F43;
            }
            QLabel#StartEyebrow {
                color: #377364;
                font-size: 11px;
                font-weight: 750;
            }
            QLabel#StartTitle {
                color: #1D2824;
                font-size: 37px;
                font-weight: 760;
            }
            QLabel#StartSubtitle {
                color: #68716D;
                font-size: 14px;
            }
            QFrame#StartDropZone {
                background: rgba(255, 255, 252, 235);
                border: 1px dashed #BCC9C3;
                border-radius: 8px;
            }
            QFrame#StartDropZone:hover {
                background: #FFFFFF;
                border: 1px solid #83A99D;
            }
            QFrame#StartDropZone[dragActive="true"] {
                background: #EDF5F1;
                border: 2px solid #2F6658;
            }
            QLabel#DropIcon {
                background: #E8F0EC;
                border: 1px solid #D1E1DA;
                border-radius: 8px;
            }
            QLabel#DropTitle {
                color: #202C28;
                font-size: 20px;
                font-weight: 720;
            }
            QLabel#DropSubtitle {
                color: #6E7772;
                font-size: 12px;
            }
            QLabel#DropFormats {
                color: #A0A6A2;
                font-size: 9px;
                font-weight: 650;
            }
            QPushButton#DropBrowseButton {
                background: #2F6658;
                color: #FFFFFF;
                border: 1px solid #2F6658;
                border-radius: 7px;
                padding: 9px 20px;
                font-weight: 700;
            }
            QPushButton#DropBrowseButton:hover {
                background: #275A4D;
                border-color: #275A4D;
            }
            QLabel#ChoiceLabel {
                color: #8C928E;
                font-size: 10px;
                font-weight: 650;
            }
            QPushButton#QuickStartButton {
                background: #FCFBF8;
                color: #33423D;
                border: 1px solid #DFDCD4;
                border-radius: 7px;
                padding: 11px 14px;
                min-height: 24px;
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton#QuickStartButton:hover {
                background: #FFFFFF;
                border-color: #9BB5AC;
                color: #234F43;
            }
            QPushButton#QuickStartButton:pressed {
                background: #EDF3F0;
            }
            QFrame#FirstTimePanel {
                background: #202A27;
                border: 1px solid #202A27;
                border-radius: 8px;
            }
            QLabel#SampleTitle {
                color: #F8F7F2;
                font-size: 15px;
                font-weight: 720;
            }
            QLabel#SampleDescription {
                color: #B9C2BE;
                font-size: 11px;
            }
            QPushButton#SampleButton {
                background: transparent;
                color: #CDE4DB;
                border: 0;
                padding: 7px 0;
                font-weight: 700;
            }
            QPushButton#SampleButton:hover {
                color: #FFFFFF;
            }
            QLabel#StartPreviewPage {
                background: #FFFDF8;
                border: 1px solid #46504C;
                border-radius: 5px;
                padding: 2px;
            }
            QFrame#SimpleSteps {
                background: transparent;
                border: 0;
            }
            QLabel#SimpleStepNumber {
                background: #E6EEE9;
                color: #2F6658;
                border: 1px solid #D3E1DB;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 750;
            }
            QLabel#SimpleStepTitle {
                color: #303C37;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#SimpleStepDetail {
                color: #8A918D;
                font-size: 10px;
            }
            QFrame#SectionPanel, QFrame#ToolPanel, QFrame#WorkflowNode {
                background: #FFFDF9;
                border: 1px solid #E2DED6;
                border-radius: 8px;
            }
            QPushButton#PrimaryButton {
                background: #2F6658;
                border-color: #2F6658;
            }
            QPushButton#PrimaryButton:hover {
                background: #275A4D;
                border-color: #275A4D;
            }
            QStatusBar {
                background: #FCFBF8;
                color: #7D8581;
                border-top: 1px solid #E5E1D9;
            }
            QFrame#ShowcaseHero {
                background: #202A27;
                border: 1px solid #202A27;
                border-radius: 8px;
            }
            QLabel#ShowcaseEyebrow {
                color: #83C4AF;
                font-size: 9px;
                font-weight: 750;
            }
            QLabel#ShowcaseTitle {
                color: #FAF9F5;
                font-size: 31px;
                font-weight: 760;
            }
            QLabel#ShowcaseSubtitle {
                color: #B9C3BF;
                font-size: 12px;
            }
            QPushButton#ShowcasePrimary {
                background: #E9A15F;
                color: #1E2925;
                border: 1px solid #E9A15F;
                border-radius: 7px;
                padding: 10px 16px;
                font-weight: 720;
            }
            QPushButton#ShowcasePrimary:hover {
                background: #F1B477;
                border-color: #F1B477;
            }
            QPushButton#ShowcaseSecondary {
                background: transparent;
                color: #E9F1ED;
                border: 1px solid #53635C;
                border-radius: 7px;
                padding: 10px 14px;
                font-weight: 650;
            }
            QPushButton#ShowcaseSecondary:hover {
                background: #2D3935;
                border-color: #71847B;
            }
            QFrame#ShowcasePreviewStage {
                background: #2A3531;
                border: 1px solid #3E4A45;
                border-radius: 8px;
            }
            QLabel#ShowcasePage {
                background: #FFFDF8;
                border: 1px solid #59645F;
                border-radius: 5px;
                padding: 3px;
            }
            QFrame#ShowcaseMetric {
                background: #FFFDF9;
                border: 1px solid #E1DDD5;
                border-radius: 8px;
            }
            QLabel#ShowcaseMetricValue {
                font-size: 22px;
                font-weight: 760;
            }
            QLabel#ShowcaseMetricLabel {
                color: #727A76;
                font-size: 10px;
                font-weight: 600;
            }
            QFrame#ShowcaseStory {
                background: #FFFDF9;
                border: 1px solid #E1DDD5;
                border-radius: 8px;
            }
            QLabel#ShowcaseContactSheet {
                background: #F0EEE8;
                border: 1px solid #E0DCD4;
                border-radius: 7px;
                padding: 8px;
            }
            QLabel#ShowcaseStoryKicker {
                color: #377364;
                font-size: 10px;
                font-weight: 750;
            }
            QLabel#ShowcaseStoryTitle {
                color: #202B27;
                font-size: 22px;
                font-weight: 740;
            }
            QLabel#ShowcaseStoryBody {
                color: #68716D;
                font-size: 11px;
            }
            QLabel#ShowcaseProofIcon {
                background: #EAF1ED;
                border: 1px solid #D6E4DD;
                border-radius: 7px;
            }
            QLabel#ShowcaseProofTitle {
                color: #33403B;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#ShowcaseProofDetail {
                color: #858C88;
                font-size: 9px;
            }
            QFrame#ShowcaseEvidence {
                background: #EEECE6;
                border: 1px solid #DFDBD3;
                border-radius: 8px;
            }
            QLabel#EvidenceTitle {
                color: #2B3732;
                font-size: 13px;
                font-weight: 720;
            }
            QLabel#EvidenceDetail {
                color: #7D8581;
                font-size: 10px;
            }
            QPushButton#EvidenceButton {
                background: #FFFDF9;
                color: #33423D;
                border: 1px solid #D8D4CC;
                border-radius: 7px;
                padding: 8px 11px;
                font-size: 10px;
                font-weight: 650;
            }
            QPushButton#EvidenceButton:hover {
                background: #FFFFFF;
                border-color: #9EB5AC;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            * {
                font-family: "Noto Sans SC", "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI";
                color: #202531;
            }
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack,
            QScrollArea#PageScroll, QWidget#OverviewContent {
                background: #F6F5F1;
            }
            QFrame#Sidebar {
                background: #12151C;
                border: 0;
                border-right: 1px solid #252A35;
            }
            QLabel#BrandTitle {
                color: #F9FAFD;
                font-family: "Noto Sans SC";
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#BrandSubtitle { color: #858FA2; }
            QFrame#SidebarRule { background: #2A303C; }
            QLabel#SidebarLabel { color: #6F788A; }
            QPushButton#NavButton, QPushButton#GroupNavButton {
                color: #9AA4B7;
                background: transparent;
                border: 0;
                border-left: 3px solid transparent;
                border-radius: 7px;
            }
            QPushButton#NavButton:hover, QPushButton#GroupNavButton:hover {
                color: #F4F6FB;
                background: #1A1F29;
            }
            QPushButton#NavButton:checked {
                color: #FFFFFF;
                background: #202735;
                border-left: 3px solid #4C8DFF;
                font-weight: 700;
            }
            QFrame#ConnectionPanel {
                background: rgba(255, 255, 255, 10);
                border: 1px solid #303747;
                border-radius: 8px;
            }
            QLabel#ChannelKicker, QLabel#ModelLabel { color: #747E91; }
            QLabel#ApiState { color: #F3A653; }
            QLabel#ApiState[connected="true"] { color: #55D8C1; }
            QFrame#TopBar {
                background: #FFFEFB;
                border: 0;
                border-bottom: 1px solid #E1DED7;
            }
            QLabel#PageTitle {
                color: #181C25;
                font-family: "Noto Sans SC";
                font-size: 22px;
                font-weight: 720;
            }
            QLabel#PageSubtitle, QLabel#SectionSubtitle, QLabel#PathLabel { color: #747B89; }
            QLabel#RepositoryState {
                background: rgba(232, 240, 255, 220);
                color: #285DBA;
                border: 1px solid #C9D9F7;
                border-radius: 7px;
            }
            QFrame#HeroPanel {
                background: #171C28;
                border: 1px solid #242B3A;
                border-radius: 8px;
            }
            QLabel#HeroEyebrow { color: #80AFFF; }
            QLabel#HeroTitle {
                color: #FFFFFF;
                font-family: "Noto Sans SC";
                font-size: 30px;
                font-weight: 740;
            }
            QLabel#HeroSubtitle { color: #B6BECD; }
            QLabel#HeroPill {
                background: rgba(255, 255, 255, 14);
                color: #C9D0DC;
                border: 1px solid rgba(255, 255, 255, 34);
                border-radius: 6px;
            }
            QFrame#HeroStatusPanel {
                background: rgba(255, 255, 255, 10);
                border: 1px solid #303849;
                border-radius: 8px;
            }
            QLabel#HeroStatusTitle {
                color: #F5F7FB;
                font-family: "Noto Sans SC";
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#HeroPreviewProof {
                color: #79D7CA;
                font-size: 9px;
                font-weight: 700;
            }
            QLabel#HeroPreviewPage {
                background: #FFFEFA;
                color: #667085;
                border: 1px solid rgba(255, 255, 255, 44);
                border-radius: 5px;
                padding: 2px;
            }
            QLabel#HeroStatusItem {
                color: #B7C0CF;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#HeroPrimary, QPushButton#PrimaryButton {
                background: #2F6FED;
                color: #FFFFFF;
                border: 1px solid #2F6FED;
                border-radius: 7px;
            }
            QPushButton#HeroPrimary:hover, QPushButton#PrimaryButton:hover {
                background: #245FCC;
                border-color: #245FCC;
            }
            QPushButton#HeroPrimary:pressed, QPushButton#PrimaryButton:pressed {
                background: #1D4FAF;
                border-color: #1D4FAF;
            }
            QPushButton#PrimaryButton:disabled {
                background: #C7CEDA;
                color: #F7F8FA;
                border-color: #C7CEDA;
            }
            QPushButton#HeroSecondary, QToolButton#HeroIconButton {
                background: rgba(255, 255, 255, 8);
                color: #E8ECF4;
                border: 1px solid #485165;
                border-radius: 7px;
            }
            QPushButton#HeroSecondary:hover, QToolButton#HeroIconButton:hover {
                background: rgba(255, 255, 255, 18);
                border-color: #66738D;
            }
            QFrame#ReadinessBand {
                background: rgba(255, 254, 251, 235);
                border: 1px solid #E2DED6;
                border-radius: 8px;
            }
            QLabel#ReadinessLabel { color: #777E8B; }
            QLabel#ReadinessValue {
                color: #0B8D7A;
                font-family: "Noto Sans SC";
                font-size: 21px;
                font-weight: 730;
            }
            QFrame#ReadinessDivider { background: #E2DED6; }
            QLabel#ReadinessTitle { color: #242936; }
            QLabel#ReadinessSummary { color: #6D7482; }
            QLabel#ReadinessPending {
                background: #FFF3E7;
                color: #A7552B;
                border: 1px solid #F1D0B9;
                border-radius: 7px;
            }
            QLabel#SectionTitle {
                color: #202531;
                font-family: "Noto Sans SC";
                font-size: 16px;
                font-weight: 720;
            }
            QFrame#ProductionStage {
                background: #F2F3F6;
                border: 1px solid #E0E2E7;
                border-radius: 7px;
            }
            QLabel#ProductionStageNumber {
                background: #2F6FED;
                color: #FFFFFF;
                border: 0;
                border-radius: 10px;
                font-size: 9px;
                font-weight: 700;
            }
            QLabel#ProductionStageLabel {
                color: #4E5768;
                font-size: 10px;
                font-weight: 650;
            }
            QFrame#StatCard, QFrame#GroupCard, QFrame#SectionPanel,
            QFrame#ToolPanel, QFrame#WorkflowNode, QFrame#TaskEntryCard {
                background: #FFFEFB;
                border: 1px solid #E1DED7;
                border-radius: 8px;
            }
            QFrame#TaskEntryCard:hover, QFrame#GroupCard:hover {
                background: #FFFFFF;
                border: 1px solid #C8D5EC;
            }
            QLabel#TaskKicker { color: #7A8291; }
            QLabel#TaskTitle, QLabel#GroupTitle {
                color: #202531;
                font-family: "Noto Sans SC";
                font-weight: 700;
            }
            QLabel#TaskBody, QLabel#GroupDescription { color: #626B7C; }
            QPushButton#TaskPrimary {
                background: #222834;
                color: #FFFFFF;
                border: 1px solid #222834;
                border-radius: 7px;
            }
            QPushButton#TaskPrimary:hover {
                background: #2F6FED;
                border-color: #2F6FED;
            }
            QToolButton#TaskSecondaryIcon, QPushButton#TaskSecondary {
                background: #F1F3F7;
                color: #334155;
                border: 1px solid #DEE2E9;
                border-radius: 7px;
            }
            QToolButton#TaskSecondaryIcon:hover, QPushButton#TaskSecondary:hover {
                background: #E8EEF9;
                border-color: #C3D1EB;
            }
            QLabel#StatValue {
                color: #1B202B;
                font-family: "Noto Sans SC";
                font-weight: 730;
            }
            QLabel#StatLabel { color: #60697A; }
            QLabel#StatDetail, QLabel#GroupSubtitle, QLabel#GroupMetrics, QLabel#CategoryLine { color: #858C99; }
            QLabel#StageBadge, QLabel#WorkflowNumber, QLabel#WorkflowState {
                background: #EAF1FF;
                color: #2F6FED;
                border-color: #D1DFF8;
            }
            QLabel#StageTitle, QLabel#WorkflowTitle { color: #2A303D; }
            QLabel#StageDetail, QLabel#WorkflowDetail { color: #7B8290; }
            QLabel#ReadyText { color: #0B8D7A; }
            QFrame#InfoBanner {
                background: rgba(236, 243, 255, 220);
                border: 1px solid #CFDDF6;
                border-radius: 8px;
            }
            QLabel#AgentStateDot { color: #DB7B35; }
            QLabel#AgentStateDot[connected="true"] { color: #0F9D8A; }
            QLabel#InfoText { color: #5F6879; }
            QToolButton#IconButton, QPushButton#SecondaryButton {
                background: #FFFEFB;
                color: #334155;
                border: 1px solid #DCD9D2;
                border-radius: 7px;
            }
            QToolButton#IconButton:hover, QPushButton#SecondaryButton:hover {
                background: #F0F4FC;
                border-color: #BFCDE7;
            }
            QPushButton#SecondaryButton:disabled {
                background: #F0EFEC;
                color: #A0A5AE;
                border-color: #E0DDD7;
            }
            QPushButton#TextButton, QPushButton#CardAction { color: #2F6FED; }
            QPushButton#TextButton:hover, QPushButton#CardAction:hover { color: #1D4FAF; }
            QPushButton#SegmentButton {
                background: rgba(235, 237, 242, 220);
                color: #687183;
                border: 1px solid #DADDE4;
                border-radius: 6px;
            }
            QPushButton#SegmentButton:checked {
                background: #FFFFFF;
                color: #245FCC;
                border-color: #91AFE6;
                font-weight: 700;
            }
            QPlainTextEdit#InputEditor, QPlainTextEdit#WorkflowInput, QLineEdit#SearchInput,
            QTextBrowser#OutputView, QPlainTextEdit#LogView {
                background: #FFFEFB;
                color: #2A303D;
                border: 1px solid #DEDAD3;
                border-radius: 7px;
                selection-background-color: #DCE9FF;
            }
            QPlainTextEdit#InputEditor:focus, QPlainTextEdit#WorkflowInput:focus,
            QLineEdit#SearchInput:focus {
                background: #FFFFFF;
                border: 1px solid #5D8FE9;
            }
            QTableWidget#DataTable {
                background: #FFFEFB;
                alternate-background-color: #F8F7F4;
                border: 1px solid #E1DED7;
                gridline-color: #EAE7E1;
                selection-background-color: #E5EDFC;
                selection-color: #202531;
            }
            QHeaderView::section {
                background: #EFEEE9;
                color: #5E6675;
                border-bottom: 1px solid #DDD9D1;
            }
            QTabWidget#ResultTabs::pane {
                background: #FFFEFB;
                border: 1px solid #E1DED7;
            }
            QTabBar::tab { color: #6D7584; }
            QTabBar::tab:hover { color: #2B3340; background: #F0F2F6; }
            QTabBar::tab:selected {
                color: #245FCC;
                border-bottom: 2px solid #2F6FED;
            }
            QLabel#ProductionPreview {
                background: #EFF2F7;
                border: 1px solid #DCE2EB;
                border-radius: 8px;
            }
            QFrame#ProductionGallery {
                background: #EEF0F4;
                border: 1px solid #D9DEE7;
                border-radius: 8px;
            }
            QLabel#ProductionGalleryPage {
                background: #FFFEFA;
                border: 1px solid #D7DCE5;
                border-radius: 6px;
                padding: 3px;
            }
            QLabel#ProductionPageLabel {
                color: #71798A;
                font-size: 9px;
                font-weight: 700;
            }
            QProgressBar#TaskProgress { background: #DDE5F3; }
            QProgressBar#TaskProgress::chunk { background: #2F6FED; }
            QStatusBar {
                background: #12151C;
                color: #919BAD;
                border-top: 1px solid #252A35;
            }
            QSplitter::handle { background: #F6F5F1; }
            QScrollBar::handle:vertical { background: #B4B8C0; }
            QScrollBar::handle:vertical:hover { background: #8E95A2; }
            QToolTip {
                background: #171B24;
                color: #F7F8FB;
                border: 1px solid #343B4A;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack,
            QScrollArea#PageScroll, QWidget#StartContent, QWidget#ShowcaseContent {
                background: #F7F5F0;
            }
            QPushButton#PrimaryButton {
                background: #2F6658;
                color: #FFFFFF;
                border: 1px solid #2F6658;
                border-radius: 7px;
            }
            QPushButton#PrimaryButton:hover {
                background: #275A4D;
                border-color: #275A4D;
            }
            QPushButton#PrimaryButton:pressed {
                background: #214D41;
                border-color: #214D41;
            }
            QPushButton#PrimaryButton:disabled {
                background: #BEC9C4;
                color: #F7F8F7;
                border-color: #BEC9C4;
            }
            QPushButton#SecondaryButton, QToolButton#IconButton {
                background: #FFFDF9;
                color: #34413C;
                border-color: #DCD8D0;
            }
            QPushButton#SecondaryButton:hover, QToolButton#IconButton:hover {
                background: #F0F4F1;
                border-color: #AFC3BB;
            }
            QTabBar::tab:selected {
                color: #2F6658;
                border-bottom: 2px solid #2F6658;
            }
            QProgressBar#TaskProgress { background: #DDE6E1; }
            QProgressBar#TaskProgress::chunk { background: #2F6658; }
            QStatusBar {
                background: #FCFBF8;
                color: #7D8581;
                border-top: 1px solid #E5E1D9;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            QLabel#TopBrand {
                color: #2F7868;
                font-size: 16px;
                font-weight: 760;
            }
            QPushButton#TopNavButton:checked {
                color: #2F7868;
                border-bottom-color: #4BA58E;
            }
            QPushButton#TopPrimaryButton, QPushButton#DropBrowseButton,
            QPushButton#PrimaryButton {
                background: #3E8D7B;
                color: #FFFFFF;
                border-color: #3E8D7B;
            }
            QPushButton#TopPrimaryButton:hover, QPushButton#DropBrowseButton:hover,
            QPushButton#PrimaryButton:hover {
                background: #347D6D;
                border-color: #347D6D;
            }
            QLabel#StartTitle {
                color: #315F54;
                font-size: 35px;
            }
            QFrame#StartDropZone {
                background: #FFFDF9;
                border: 1px dashed #AFCFC2;
            }
            QLabel#DropIcon {
                background: #E8F4EF;
                border-color: #CAE2D8;
            }
            QLabel#DropTitle { color: #356C5F; }
            QPushButton#QuickStartButton {
                background: #FFFDF9;
                color: #42685E;
                border: 1px solid #D9E2DD;
                min-height: 46px;
                padding: 10px 14px;
                text-align: left;
                font-size: 11px;
                font-weight: 650;
            }
            QPushButton#QuickStartButton:hover {
                background: #F1F8F5;
                color: #2F7868;
                border-color: #8DBFAE;
            }
            QPushButton#QuickStartButton[accent="coral"] {
                background: #FFF4ED;
                color: #9E5539;
                border-color: #F0D2C2;
            }
            QPushButton#QuickStartButton[accent="coral"]:hover {
                background: #FFEDE2;
                color: #87432D;
                border-color: #E7A98B;
            }
            QPushButton#QuickStartButton[accent="blue"] {
                background: #F0F5FB;
                color: #496D99;
                border-color: #D4E0EE;
            }
            QPushButton#QuickStartButton[accent="blue"]:hover {
                background: #E8F0F9;
                color: #375D88;
                border-color: #9CB7D5;
            }
            QPushButton#QuickStartButton[accent="jade"] {
                background: #EEF7F3;
                color: #347666;
                border-color: #D2E6DD;
            }
            QPushButton#QuickStartButton[accent="jade"]:hover {
                background: #E5F3ED;
                color: #286656;
                border-color: #91BEAD;
            }
            QPushButton#QuickStartButton[accent="violet"] {
                background: #F5F1F8;
                color: #715C94;
                border-color: #E1D8EA;
            }
            QPushButton#QuickStartButton[accent="violet"]:hover {
                background: #EFE8F5;
                color: #604B84;
                border-color: #BCA9D0;
            }
            QFrame#OutcomeBand {
                background: #EEF5F7;
                border: 1px solid #D5E3E8;
                border-radius: 7px;
            }
            QLabel#OutcomeTitle {
                color: #4D7282;
                font-size: 10px;
                font-weight: 750;
            }
            QLabel#OutcomeItem {
                color: #596E77;
                font-size: 10px;
                font-weight: 600;
            }
            QFrame#FirstTimePanel {
                background: #FFF4EC;
                border: 1px solid #F0D6C7;
            }
            QLabel#SampleTitle { color: #9B583D; }
            QLabel#SampleDescription { color: #806C62; }
            QPushButton#SampleButton {
                background: #FFFDF9;
                color: #A45C3D;
                border: 1px solid #E8C7B5;
                border-radius: 6px;
                padding: 7px 11px;
            }
            QPushButton#SampleButton:hover {
                background: #FFFFFF;
                color: #8C482F;
                border-color: #D99B7A;
            }
            QLabel#StartPreviewPage { border-color: #C9D9D2; }
            QFrame#AgentModeGuide {
                background: #F1F7F4;
                border: 1px solid #D5E7DF;
                border-radius: 7px;
            }
            QLabel#AgentModeIcon {
                background: #FFFDF9;
                border: 1px solid #D5E4DE;
                border-radius: 7px;
            }
            QLabel#AgentModeTitle {
                color: #346E60;
                font-size: 11px;
                font-weight: 750;
            }
            QLabel#AgentModeDetail {
                color: #5F746C;
                font-size: 9px;
            }
            QLabel#AgentModeProof {
                color: #6D8DA1;
                font-size: 9px;
                font-weight: 650;
            }
            QPushButton#GuideAction, QPushButton#CozeHighlightAction {
                background: #FFFDF9;
                color: #347D6D;
                border: 1px solid #C6DDD4;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#GuideAction:hover, QPushButton#CozeHighlightAction:hover {
                background: #FFFFFF;
                border-color: #89B9A9;
            }
            QPushButton#SegmentButton:checked {
                color: #347D6D;
                border-color: #91BFAF;
            }
            QFrame#ShowcaseHero {
                background: #E7F2ED;
                border: 1px solid #C9DED5;
            }
            QLabel#ShowcaseEyebrow { color: #3C8A77; }
            QLabel#ShowcaseTitle { color: #2F6658; }
            QLabel#ShowcaseSubtitle { color: #657A71; }
            QPushButton#ShowcasePrimary {
                background: #EE9B72;
                color: #FFFFFF;
                border-color: #EE9B72;
            }
            QPushButton#ShowcasePrimary:hover {
                background: #E78B61;
                border-color: #E78B61;
            }
            QPushButton#ShowcaseSecondary {
                background: #FFFDF9;
                color: #347D6D;
                border-color: #BBD5CA;
            }
            QPushButton#ShowcaseSecondary:hover {
                background: #FFFFFF;
                border-color: #8DB9AA;
            }
            QFrame#ShowcasePreviewStage {
                background: #FFFDF9;
                border: 1px solid #C9DDD4;
            }
            QLabel#ShowcasePage { border-color: #C6D8D0; }
            QFrame#CozeHighlight {
                background: #EEF5F8;
                border: 1px solid #D2E2E9;
                border-radius: 8px;
            }
            QLabel#CozeHighlightIcon {
                background: #FFFDF9;
                border: 1px solid #D0E0E5;
                border-radius: 7px;
            }
            QLabel#CozeHighlightTitle {
                color: #356E61;
                font-size: 12px;
                font-weight: 740;
            }
            QLabel#CozeHighlightDetail {
                color: #637982;
                font-size: 9px;
            }
            QLabel#CozeHighlightBadge {
                background: #FFFDF9;
                color: #557E91;
                border: 1px solid #D1E1E7;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 9px;
                font-weight: 650;
            }
            QPushButton#TextButton, QPushButton#CardAction {
                color: #3E8D7B;
            }
            QPushButton#TextButton:hover, QPushButton#CardAction:hover {
                color: #2F6F60;
            }
            """
        )
        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#Sidebar {
                background: #22312D;
                border: 0;
                border-right: 1px solid #34443F;
            }
            QLabel#BrandTitle {
                color: #F5F0E7;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 24px;
                font-weight: 740;
            }
            QLabel#BrandSubtitle { color: #9EAEA8; font-size: 7px; }
            QFrame#SidebarRule { background: #394943; }
            QLabel#SidebarLabel { color: #84958F; }
            QPushButton#NavButton {
                background: transparent;
                color: #BECAC5;
                border: 1px solid transparent;
                border-radius: 6px;
                min-height: 42px;
                padding: 0 12px;
                text-align: left;
                font-size: 11px;
                font-weight: 590;
            }
            QPushButton#NavButton:hover {
                background: #2A3C36;
                color: #F3F0E9;
                border-color: #40524B;
            }
            QPushButton#NavButton:checked {
                background: #30433D;
                color: #FFF8EF;
                border: 1px solid #53665F;
                border-left: 3px solid #D47A58;
                font-weight: 720;
            }
            QFrame#ConnectionPanel {
                background: #293A35;
                border: 1px solid #40514B;
                border-radius: 7px;
            }
            QLabel#ChannelKicker { color: #899A94; }
            QLabel#ApiState { color: #E5A17F; font-weight: 700; }
            QLabel#ApiState[connected="true"] { color: #84C4B3; }
            QLabel#ModelLabel { color: #91A19B; }
            QFrame#TopBar { background: #F8F5EE; border-bottom-color: #DED7CB; }
            QLabel#TopContext {
                color: #27332F;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 17px;
            }
            QLabel#PageSubtitle { color: #898D88; }
            QLabel#StartTitle {
                color: #2B5B51;
                font-family: "Noto Serif SC", "SimSun";
                font-size: 43px;
            }
            QPushButton#QuickStartButton,
            QPushButton#QuickStartButton[accent="coral"],
            QPushButton#QuickStartButton[accent="blue"],
            QPushButton#QuickStartButton[accent="jade"],
            QPushButton#QuickStartButton[accent="gold"] {
                background: #FAF8F3;
                border: 1px solid #DCD4C8;
                border-radius: 7px;
                min-height: 64px;
            }
            QPushButton#QuickStartButton[accent="coral"] { color: #87503B; border-left: 3px solid #C86F4D; }
            QPushButton#QuickStartButton[accent="blue"] { color: #4A6875; border-left: 3px solid #587E91; }
            QPushButton#QuickStartButton[accent="jade"] { color: #35675C; border-left: 3px solid #327568; }
            QPushButton#QuickStartButton[accent="gold"] { color: #79633E; border-left: 3px solid #A88952; }
            QPushButton#QuickStartButton:hover,
            QPushButton#QuickStartButton[accent="coral"]:hover,
            QPushButton#QuickStartButton[accent="blue"]:hover,
            QPushButton#QuickStartButton[accent="jade"]:hover,
            QPushButton#QuickStartButton[accent="gold"]:hover {
                background: #FFFDF8;
                border-color: #AFA496;
            }
            QFrame#OutcomeBand { background: #EEEAE2; border-color: #D9D1C5; }
            QFrame#FirstTimePanel { background: #F6EDE5; border-color: #E5CDBE; }
            QPushButton#TopPrimaryButton, QPushButton#DropBrowseButton,
            QPushButton#PrimaryButton {
                background: #B96144;
                color: #FFFFFF;
                border-color: #B96144;
            }
            QPushButton#TopPrimaryButton:hover, QPushButton#DropBrowseButton:hover,
            QPushButton#PrimaryButton:hover {
                background: #A75338;
                border-color: #A75338;
            }
            QFrame#ProductionStage {
                background: #F1EEE7;
                border-color: #DED7CB;
            }
            QLabel#ProductionStageNumber { background: #C86F4D; }
            QLabel#ProductionStageLabel { color: #59635E; }
            """
        )


def main(argv: list[str] | None = None) -> int:
    _configure_console_output()
    argv = list(sys.argv[1:] if argv is None else argv)
    project_root = find_project_root()

    if "--self-check" in argv:
        config = load_config()
        scan = scan_collaboration(project_root)
        print(f"app={config.app_name}")
        print(f"model={config.openai_model}")
        print(f"api_key={'yes' if config.has_api_key else 'no'}")
        print(f"coze_workflow={'yes' if config.has_coze_workflow else 'no'}")
        print(f"coze_workflow_id={config.coze_workflow_id or 'none'}")
        print(f"project_root={scan.project_root}")
        print(f"groups={len(scan.groups)}")
        print(f"assets={len(scan.assets)}")
        print(f"terms={scan.terminology.count}")
        return 0

    if "--production-self-check" in argv:
        docx_result = validate_c_docx_samples(project_root)
        audio_reviews = sorted(
            (
                project_root
                / "collaboration/groups/C_text_audio_translation/deliverables/docx_translation/"
                "revised_20260717/test_cases"
            ).rglob("*.xlsx"),
            key=lambda path: path.stat().st_size,
        )
        if not audio_reviews:
            print("没有可用于语音合成验收的审校表。", file=sys.stderr)
            return 1
        audio_result = synthesize_audio_from_review(audio_reviews[0])
        print(docx_result.to_markdown())
        print()
        print(audio_result.to_markdown())
        return 0

    if "--smoke-test" in argv:
        config = load_config()
        client = AgentClient(config)
        result = WorkflowResult(
            steps=[
                StepResult("environment", "configuration loaded", "local-test"),
                StepResult("collaboration", format_dashboard_markdown(scan_collaboration(project_root)), "local-test"),
                StepResult(
                    "workflow",
                    format_workflow_result(
                        run_translation_integration_workflow(client, "烟测：生成当前项目整合状态", project_root)
                    ),
                    "local-test",
                ),
            ]
        )
        print(format_workflow_result(result))
        return 0

    if "--integration-report" in argv:
        prompt = " ".join(arg for arg in argv if arg != "--integration-report")
        bundle = write_integration_outputs(scan_collaboration(project_root), prompt)
        print(bundle.summary_markdown)
        return 0

    if "--term-search" in argv:
        query_parts = [arg for arg in argv if arg != "--term-search"]
        print(format_terms_markdown(search_terms(" ".join(query_parts), project_root)))
        return 0

    if "--coze-run" in argv:
        prompt = " ".join(arg for arg in argv if arg != "--coze-run").strip()
        if not prompt:
            print("--coze-run 需要提供待翻译正文。", file=sys.stderr)
            return 2
        try:
            response = CozeWorkflowClient(load_config()).run(prompt)
        except CozeWorkflowError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(response.text)
        return 0

    app = QApplication(sys.argv)
    configure_application_fonts(app)
    app.setApplicationName("译述 YISHU")
    app.setOrganizationName("Culture Translate")
    app.setWindowIcon(make_brand_icon())
    window = MainWindow()
    window.show()
    return app.exec()


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
