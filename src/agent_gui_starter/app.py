from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QEasingCurve, QObject, QPropertyAnimation, QSize, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
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
    run_group_adapter,
    scan_collaboration,
    search_terms,
    write_integration_outputs,
)
from .workflow import (
    StepResult,
    WorkflowResult,
    format_workflow_result,
    run_default_workflow,
    run_translation_integration_workflow,
)


SYSTEM_PROMPT = "你是中国文化多模态知识库外译项目的桌面端智能体助手。请给出准确、简洁、可执行的结果。"
GROUP_ACCENTS = {"A": "#426B9B", "B": "#167A65", "C": "#C95F46"}
UI_FONT_FAMILY = "Noto Sans SC"
DISPLAY_FONT_FAMILY = "Noto Serif SC"
SIDEBAR_WIDTH = 256
_FONTS_CONFIGURED = False
PAGE_META = {
    "overview": ("项目总览", "从真实翻译通道进入整合、审校与交付"),
    "agent": ("智能体", "生成、校验并整理翻译任务结果"),
    "terms": ("术语库", "统一文化术语译法与上下文依据"),
    "workflow": ("总整合工作流", "扫描、适配、导出与智能质检"),
    "outputs": ("交付中心", "报告、表格、运行日志与最终输出"),
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
    for preferred in ("Noto Serif SC", "Source Han Serif SC", "SimSun"):
        if preferred in families:
            DISPLAY_FONT_FAMILY = preferred
            break

    target_app = app or QApplication.instance()
    if target_app is not None:
        target_app.setFont(QFont(UI_FONT_FAMILY, 10))


def make_brand_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    padding = max(1, int(size * 0.04))
    painter.setBrush(QColor("#18201D"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(
        padding,
        padding,
        size - padding * 2,
        size - padding * 2,
        max(4, int(size * 0.12)),
        max(4, int(size * 0.12)),
    )
    painter.setBrush(QColor("#42A389"))
    painter.drawRoundedRect(
        padding,
        padding,
        max(3, int(size * 0.11)),
        size - padding * 2,
        max(2, int(size * 0.04)),
        max(2, int(size * 0.04)),
    )
    painter.setBrush(QColor("#D6664E"))
    dot_size = max(3, int(size * 0.10))
    painter.drawEllipse(size - padding - dot_size - 2, padding + 3, dot_size, dot_size)
    font = QFont(DISPLAY_FONT_FAMILY, max(16, int(size * 0.50)), QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#F7FAF7"))
    text_rect = pixmap.rect().adjusted(max(2, int(size * 0.06)), 0, 0, 0)
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "译")
    painter.end()
    return QIcon(pixmap)


def make_icon(
    name: str,
    color: str = "#68736E",
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


def add_surface_shadow(widget: QWidget, blur: int = 20, y_offset: int = 4, alpha: int = 24) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(18, 28, 24, alpha))
    widget.setGraphicsEffect(shadow)


class GlassFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QColor(255, 255, 255, 232))
        painter.setBrush(QColor(255, 255, 255, 214))
        painter.drawRoundedRect(outer, 8, 8)
        inner = outer.adjusted(1, 1, -1, -1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(73, 102, 89, 30))
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
            "h1 { color: #172033; font-size: 22px; margin-bottom: 10px; }"
            "h2 { color: #25324a; font-size: 17px; margin-top: 18px; }"
            "h3 { color: #475467; font-size: 14px; margin-top: 14px; }"
            "p, li { line-height: 1.55; }"
            "code { background: #eef4ff; color: #2457bd; }"
            "table { border-collapse: collapse; }"
            "th { background: #f2f5f9; font-weight: 600; }"
            "th, td { border: 1px solid #dfe5ec; padding: 6px; }"
        )

    def set_output(self, text: str) -> None:
        self._raw_text = text.strip()
        self.setMarkdown(self._raw_text)
        self.moveCursor(self.textCursor().MoveOperation.Start)

    def raw_text(self) -> str:
        return self._raw_text


class StatCard(QFrame):
    def __init__(self, label: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("accent", accent)
        self.setMinimumHeight(112)

        signal = QFrame()
        signal.setObjectName("StatSignal")
        signal.setFixedSize(38, 3)
        signal.setStyleSheet(f"background: {accent}; border: 0; border-radius: 1px;")

        self._value = QLabel("-")
        self._value.setObjectName("StatValue")
        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self._detail = QLabel("")
        self._detail.setObjectName("StatDetail")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(3)
        layout.addWidget(signal)
        layout.addSpacing(5)
        layout.addWidget(self._label)
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
        badge = QLabel(group_key)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(34, 34)
        badge.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border: 0; "
            "border-radius: 7px; font-size: 15px; font-weight: 700;"
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
        badge: str,
        title: str,
        kicker: str,
        body: str,
        primary_label: str,
        primary_action: str,
        secondary_label: str,
        secondary_action: str,
        accent: str,
    ) -> None:
        super().__init__()
        self.setObjectName("TaskEntryCard")
        self.setMinimumHeight(202)
        add_surface_shadow(self, blur=16, y_offset=3, alpha=18)

        signal = QFrame()
        signal.setFixedSize(46, 3)
        signal.setStyleSheet(f"background: {accent}; border: 0; border-radius: 1px;")

        badge_label = QLabel(badge)
        badge_label.setObjectName("TaskBadge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_label.setFixedSize(42, 42)
        badge_label.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border-radius: 7px; "
            "font-size: 18px; font-weight: 800;"
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

        primary = QPushButton(primary_label)
        primary.setObjectName("TaskPrimary")
        primary.setIcon(make_icon("play", "#FFFFFF"))
        primary.clicked.connect(lambda: self.action_requested.emit(primary_action))
        secondary = QPushButton(secondary_label)
        secondary.setObjectName("TaskSecondary")
        secondary.setIcon(make_icon("arrow-right", "#25302B"))
        secondary.clicked.connect(lambda: self.action_requested.emit(secondary_action))

        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addWidget(primary)
        actions.addWidget(secondary)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(signal)
        layout.addLayout(header)
        layout.addWidget(body_label, 1)
        layout.addLayout(actions)


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

        self.setWindowTitle(self._config.app_name)
        self.setWindowIcon(make_brand_icon())
        self.setMinimumSize(1100, 720)
        self.resize(1440, 900)
        self._build_ui()
        self._apply_styles()
        self._configure_interactions()
        self._install_shortcuts()
        self._refresh_from_scan()

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
        status.showMessage(
            f"就绪  ·  {len(self._scan.assets)} 个资源  ·  {self._scan.terminology.count} 条术语"
        )

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        logo = QLabel()
        logo.setPixmap(make_brand_icon(46).pixmap(46, 46))
        logo.setFixedSize(46, 46)
        brand_title = QLabel("华译工作台")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("文化知识 · 多模态外译")
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
        layout.addWidget(self._sidebar_label("工作区"))

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        nav_items = [
            ("overview", "项目总览", "layout-dashboard"),
            ("agent", "智能体", "bot"),
            ("terms", "术语库", "book-open"),
            ("workflow", "总整合工作流", "route"),
            ("outputs", "交付中心", "package-check"),
        ]
        for key, text, icon_name in nav_items:
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(make_icon(icon_name, "#8F9B95", selected_color="#69BEA7"))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, page=key: self._switch_page(page))
            self._nav_group.addButton(button)
            self._nav_buttons[key] = button
            layout.addWidget(button)

        self._nav_buttons["overview"].setChecked(True)
        layout.addSpacing(18)
        layout.addWidget(self._sidebar_label("协作分组"))
        for key, text in (("A", "图文翻译与回填"), ("B", "术语与风格控制"), ("C", "文本与音视频翻译")):
            button = QPushButton(f"{key}    {text}")
            button.setObjectName("GroupNavButton")
            button.clicked.connect(lambda checked=False, group=key: self._show_group(group))
            self._group_nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        connection = QFrame()
        connection.setObjectName("ConnectionPanel")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(13, 12, 13, 12)
        connection_layout.setSpacing(4)
        channel_kicker = QLabel("运行通道")
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
            "agent": self._build_agent_page(),
            "terms": self._build_terms_page(),
            "workflow": self._build_workflow_page(),
            "outputs": self._build_outputs_page(),
            "group": self._build_group_page(),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)
        layout.addWidget(self._stack, 1)
        return workspace

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(82)
        self._page_title = QLabel(PAGE_META["overview"][0])
        self._page_title.setObjectName("PageTitle")
        self._page_subtitle = QLabel(PAGE_META["overview"][1])
        self._page_subtitle.setObjectName("PageSubtitle")
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(2)
        titles.addWidget(self._page_title)
        titles.addWidget(self._page_subtitle)

        self._scan_button = QToolButton()
        self._scan_button.setObjectName("IconButton")
        self._scan_button.setIcon(make_icon("refresh-cw"))
        self._scan_button.setIconSize(QSize(19, 19))
        self._scan_button.setToolTip("重新扫描协作资源 (F5)")
        self._scan_button.clicked.connect(self._scan_now)

        output_button = QToolButton()
        output_button.setObjectName("IconButton")
        output_button.setIcon(make_icon("folder-open"))
        output_button.setIconSize(QSize(19, 19))
        output_button.setToolTip("打开输出目录")
        output_button.clicked.connect(self._open_output_dir)

        self._top_run_button = QPushButton("运行整合")
        self._top_run_button.setObjectName("PrimaryButton")
        self._top_run_button.setIcon(make_icon("play", "#FFFFFF"))
        self._top_run_button.clicked.connect(
            lambda: self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)
        )
        self._busy_controls.extend([self._scan_button, self._top_run_button])

        repository_state = QLabel("PUBLIC · MAIN")
        repository_state.setObjectName("RepositoryState")
        repository_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repository_state.setFixedHeight(34)
        repository_state.setMinimumWidth(96)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(repository_state)
        actions.addWidget(self._scan_button)
        actions.addWidget(output_button)
        actions.addWidget(self._top_run_button)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(30, 0, 30, 0)
        layout.addLayout(titles)
        layout.addStretch(1)
        layout.addLayout(actions)
        return topbar

    def _build_overview_page(self) -> QWidget:
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
        entry_text.addWidget(self._section_title("真实工作入口"))
        self._scan_time_label = QLabel()
        self._scan_time_label.setObjectName("SectionSubtitle")
        entry_text.addWidget(self._scan_time_label)
        entry_row.addLayout(entry_text)
        entry_row.addStretch(1)
        self._report_button = QPushButton("生成整合报告")
        self._report_button.setObjectName("SecondaryButton")
        self._report_button.setIcon(make_icon("file-text", "#344054"))
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
                "A",
                "图文翻译与回填",
                "图片 OCR / 图文回填",
                "读取 71 条审校清单、最终 DOCX、10 个 SVG 与 17 页渲染证据。",
                "查看 A 组",
                "group:A",
                "运行适配器",
                "adapter:A",
                GROUP_ACCENTS["A"],
            ),
            TaskEntryCard(
                "B",
                "术语与风格约束",
                "共享术语库 / 儿童文学风格",
                "调用 B 组扣子多模型工作流，并以 212 条共享术语作为全局翻译约束。",
                "运行扣子工作流",
                "agent:coze",
                "打开术语库",
                "page:terms",
                GROUP_ACCENTS["B"],
            ),
            TaskEntryCard(
                "D",
                "文本与 DOCX 翻译",
                "普通文本 / DOCX 回填",
                "使用 C 组二次交付的修正版 DOCX 通道，支持译文表回填和替换覆盖报告。",
                "查看 C 组",
                "group:C",
                "运行适配器",
                "adapter:C",
                GROUP_ACCENTS["C"],
            ),
            TaskEntryCard(
                "V",
                "音视频翻译通道",
                "ASR / 审校表 / 语音合成",
                "面向模式一音频转表格、模式二定稿表格生成总音频的后续整合入口。",
                "运行总整合",
                "workflow:run",
                "交付中心",
                "page:outputs",
                "#7565A8",
            ),
        )
        for card in self._task_cards:
            card.action_requested.connect(self._handle_task_action)
        layout.addLayout(self._task_grid)

        layout.addWidget(self._section_title("整合状态"))

        self._stats_grid = QGridLayout()
        self._stats_grid.setHorizontalSpacing(12)
        self._stats_grid.setVerticalSpacing(12)
        self._stat_ready = StatCard("分组就绪", "#167A65")
        self._stat_assets = StatCard("资源文件", "#426B9B")
        self._stat_terms = StatCard("共享术语", "#C95F46")
        self._stat_outputs = StatCard("已生成输出", "#7565A8")
        self._stat_cards = (self._stat_ready, self._stat_assets, self._stat_terms, self._stat_outputs)
        layout.addLayout(self._stats_grid)

        layout.addWidget(self._section_title("交付物接手状态"))
        self._group_grid = QGridLayout()
        self._group_grid.setHorizontalSpacing(12)
        self._group_grid.setVerticalSpacing(12)
        self._group_cards: dict[str, GroupCard] = {}
        for key in ("A", "B", "C"):
            card = GroupCard(key)
            card.open_requested.connect(self._show_group)
            self._group_cards[key] = card
        layout.addLayout(self._group_grid)

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
        score_label = QLabel("技术验收")
        score_label.setObjectName("ReadinessLabel")
        score_value = QLabel("19 / 19")
        score_value.setObjectName("ReadinessValue")
        score_box.addWidget(score_label)
        score_box.addWidget(score_value)

        divider = QFrame()
        divider.setObjectName("ReadinessDivider")
        divider.setFixedWidth(1)

        evidence_box = QVBoxLayout()
        evidence_box.setContentsMargins(0, 0, 0, 0)
        evidence_box.setSpacing(2)
        evidence_title = QLabel("最新版证据已接入")
        evidence_title.setObjectName("ReadinessTitle")
        evidence = QLabel("A · 71 条清单 / 17 页渲染    B · 212 条术语 / Coze    C · 5 套 DOCX / 2 条音频")
        evidence.setObjectName("ReadinessSummary")
        evidence.setWordWrap(True)
        evidence_box.addWidget(evidence_title)
        evidence_box.addWidget(evidence)

        pending = QLabel("3 项责任人确认")
        pending.setObjectName("ReadinessPending")
        pending.setAlignment(Qt.AlignmentFlag.AlignCenter)

        open_record = QPushButton("验收记录")
        open_record.setObjectName("SecondaryButton")
        open_record.setIcon(make_icon("clipboard-check", "#29342F"))
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
        panel.setMinimumHeight(238)
        add_surface_shadow(panel, blur=28, y_offset=7, alpha=34)

        eyebrow = QLabel("CULTURAL TRANSLATION OPERATIONS")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("中国文化多模态外译工作台")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel(
            "统一接入图文回填、术语风格、DOCX 与音视频翻译。"
            "A/B/C 最新交付、审校证据和公开构建状态在一个工作区内完成管理。"
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)

        run_button = QPushButton("运行总整合")
        run_button.setObjectName("HeroPrimary")
        run_button.setIcon(make_icon("play", "#FFFFFF"))
        run_button.clicked.connect(
            lambda: self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)
        )
        outputs_button = QPushButton("查看交付中心")
        outputs_button.setObjectName("HeroSecondary")
        outputs_button.clicked.connect(lambda: self._switch_page("outputs"))
        self._busy_controls.append(run_button)

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
        status_layout.setContentsMargins(16, 15, 16, 15)
        status_layout.setSpacing(10)
        status_title = QLabel("交付运行指数")
        status_title.setObjectName("HeroStatusTitle")
        status_layout.addWidget(status_title)
        self._hero_status_labels: list[QLabel] = []
        for _ in range(4):
            label = QLabel()
            label.setObjectName("HeroStatusItem")
            label.setWordWrap(True)
            self._hero_status_labels.append(label)
            status_layout.addWidget(label)
        status_layout.addStretch(1)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(30, 27, 27, 25)
        layout.setSpacing(30)
        layout.addLayout(left, 3)
        layout.addWidget(status_panel, 2)
        return panel

    def _overview_workflow_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SectionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 17, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section_title("整合链路"))
        stages = [
            ("01", "统一术语约束", "读取 B 组共享术语库"),
            ("02", "接入图文成果", "校验 A 组清单、DOCX 与预览"),
            ("03", "接入文本音频", "读取 C 组二次交付目录"),
            ("04", "生成最终交付", "输出 Markdown、CSV 与 Excel"),
        ]
        for number, title, detail in stages:
            row = QHBoxLayout()
            badge = QLabel(number)
            badge.setObjectName("StageBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(34, 28)
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
        layout.addWidget(self._section_title("任务输入"))

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._agent_modes = QButtonGroup(self)
        self._agent_modes.setExclusive(True)
        for mode, text in (
            ("agent", "单次智能体"),
            ("default_workflow", "分析 · 草稿 · 质检"),
            ("coze_workflow", "扣子工作流"),
        ):
            button = QPushButton(text)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setProperty("mode", mode)
            self._agent_modes.addButton(button)
            mode_row.addWidget(button)
        self._agent_modes.buttons()[0].setChecked(True)
        layout.addLayout(mode_row)

        self._agent_title = QLineEdit()
        self._agent_title.setObjectName("SearchInput")
        self._agent_title.setPlaceholderText("标题或来源（选填，扣子工作流会作为 input_title 传入）")
        self._agent_title.setClearButtonEnabled(True)
        layout.addWidget(self._agent_title)

        self._agent_input = QPlainTextEdit()
        self._agent_input.setObjectName("InputEditor")
        self._agent_input.setPlaceholderText("输入待翻译文本、审校要求或需要智能体处理的任务…")
        self._agent_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._agent_input, 1)

        footer = QHBoxLayout()
        clear = QPushButton("清空")
        clear.setObjectName("TextButton")
        clear.clicked.connect(self._clear_agent_input)
        self._agent_run_button = QPushButton("开始生成")
        self._agent_run_button.setObjectName("PrimaryButton")
        self._agent_run_button.setIcon(make_icon("play", "#FFFFFF"))
        self._agent_run_button.clicked.connect(self._run_agent)
        self._busy_controls.append(self._agent_run_button)
        footer.addWidget(clear)
        footer.addStretch(1)
        footer.addWidget(self._agent_run_button)
        layout.addLayout(footer)
        return panel

    def _agent_output_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ToolPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(self._section_title("生成结果"))
        header.addStretch(1)
        copy_button = self._icon_button("copy", "复制结果")
        copy_button.clicked.connect(lambda: self._copy_view(self._agent_output))
        save_button = self._icon_button("save", "保存结果 (Ctrl+S)")
        save_button.clicked.connect(lambda: self._save_view(self._agent_output, "agent-output.md"))
        header.addWidget(copy_button)
        header.addWidget(save_button)
        layout.addLayout(header)
        self._agent_output = MarkdownView("智能体结果会显示在这里。")
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
        self._use_term_button = QPushButton("加入智能体约束")
        self._use_term_button.setObjectName("SecondaryButton")
        self._use_term_button.setIcon(make_icon("plus", "#344054"))
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
        self._term_table.setHorizontalHeaderLabels(["术语", "英文翻译", "出处页码", "上下文片段"])
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
        for index, (title, detail) in enumerate(
            (("扫描资源", "A/B/C 协作区"), ("运行适配器", "统一接入结果"), ("生成报告", "MD · CSV · Excel"), ("智能质检", "给出交付建议")),
            start=1,
        ):
            node = QFrame()
            node.setObjectName("WorkflowNode")
            node_layout = QHBoxLayout(node)
            node_layout.setContentsMargins(13, 11, 13, 11)
            number = QLabel(f"{index:02}")
            number.setObjectName("WorkflowNumber")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setFixedSize(32, 32)
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
            node_layout.addWidget(number)
            node_layout.addLayout(texts, 1)
            node_layout.addWidget(state)
            stages.addWidget(node, 0, index - 1)
            stages.setColumnStretch(index - 1, 1)
        layout.addLayout(stages)

        input_row = QHBoxLayout()
        self._workflow_input = QPlainTextEdit()
        self._workflow_input.setObjectName("WorkflowInput")
        self._workflow_input.setPlaceholderText("可选：填写本次整合目标，例如“生成可供课堂演示的最终交付状态与风险清单”。")
        self._workflow_input.setMaximumHeight(106)
        self._workflow_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._workflow_run_button = QPushButton("运行完整工作流")
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
        ready_groups = sum(group.status == "可整合" for group in self._scan.groups)
        workflow_snapshot = (
            "# 总整合已就绪\n\n"
            f"- 协作分组：{ready_groups}/{len(self._scan.groups)} 可整合\n"
            f"- 共享术语：{self._scan.terminology.count} 条\n"
            "- A 组：71 条审校清单、10 个 SVG、17 页渲染证据\n"
            "- B 组：Coze 工作流结构通过，在线发布状态待责任人确认\n"
            "- C 组：5 套 DOCX 样例、测试音频、总音频、终版表格与二维码\n\n"
            "本地扫描、分组适配和三类报告导出可直接运行；在线质检按 `.env` 配置决定调用通道。"
        )
        self._workflow_output = MarkdownView("工作流状态会显示在这里。")
        self._workflow_output.setObjectName("OutputView")
        self._workflow_output.set_output(workflow_snapshot)
        layout.addWidget(self._workflow_output, 1)
        return page

    def _build_outputs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("OutputsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        path_row = QHBoxLayout()
        path_text = QVBoxLayout()
        path_text.setSpacing(2)
        path_text.addWidget(self._section_title("最近输出"))
        self._output_path_label = QLabel()
        self._output_path_label.setObjectName("PathLabel")
        self._output_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_text.addWidget(self._output_path_label)
        path_row.addLayout(path_text, 1)
        open_button = QPushButton("打开目录")
        open_button.setObjectName("SecondaryButton")
        open_button.setIcon(make_icon("folder-open", "#344054"))
        open_button.clicked.connect(self._open_output_dir)
        report_button = QPushButton("生成报告")
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
            "# 稳定交付基线\n\n"
            "- 技术验收：19/19\n"
            "- 单元与界面测试：15 项\n"
            "- 输出格式：Markdown、CSV、Excel\n"
            "- Windows：PyInstaller onedir，可独立启动\n"
            "- 公开协作：GitHub main + Windows CI\n\n"
            "责任人确认项会保留在正式验收记录中，不计作技术执行失败。"
        )
        self._delivery_output = MarkdownView("交付摘要会显示在这里。")
        self._delivery_output.setObjectName("OutputView")
        self._delivery_output.set_output(delivery_snapshot)
        self._log = QPlainTextEdit()
        self._log.setObjectName("LogView")
        self._log.setReadOnly(True)
        tabs.addTab(self._delivery_output, "报告摘要")
        tabs.addTab(self._log, "运行日志")
        layout.addWidget(tabs, 3)
        return page

    def _build_group_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("GroupPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        summary_row = QHBoxLayout()
        self._group_badge = QLabel("A")
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
        self._group_query.setPlaceholderText("可选：输入适配目标；B 组可直接输入术语关键词")
        self._group_query.returnPressed.connect(self._run_group_adapter)
        open_button = QPushButton("打开分组目录")
        open_button.setObjectName("SecondaryButton")
        open_button.setIcon(make_icon("folder-open", "#344054"))
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
            (self._group_grid, tuple(self._group_cards.values()), group_columns),
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
            self._agent_input.setFocus()
            return
        if action == "workflow:run":
            self._switch_page("workflow")
            self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)

    def _switch_page(self, page_key: str) -> None:
        if page_key not in self._pages:
            return
        self._current_page_key = page_key
        self._stack.setCurrentWidget(self._pages[page_key])
        self._animate_page(self._pages[page_key])
        title, subtitle = PAGE_META[page_key]
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitle)
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
        self._group_badge.setText(group_key)
        self._group_badge.setStyleSheet(
            f"background: {GROUP_ACCENTS[group_key]}; color: white; border-radius: 8px; font-size: 22px; font-weight: 700;"
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

    def _animate_page(self, page: QWidget) -> None:
        if self._page_animation is not None:
            self._page_animation.stop()
        if self._animated_page is not None:
            self._animated_page.setGraphicsEffect(None)

        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(160)
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: page.setGraphicsEffect(None))
        self._page_animation = animation
        self._animated_page = page
        animation.start()

    def _refresh_from_scan(self) -> None:
        ready = sum(group.status == "可整合" for group in self._scan.groups)
        output_files = self._output_files()
        self._stat_ready.update_value(f"{ready}/{len(self._scan.groups)}", "A/B/C 当前状态")
        self._stat_assets.update_value(str(len(self._scan.assets)), "协作区有效资源")
        self._stat_terms.update_value(str(self._scan.terminology.count), "已同步至共享区")
        self._stat_outputs.update_value(str(len(output_files)), "generated 目录")
        self._scan_time_label.setText(f"最近扫描：{self._scan.scanned_at}  ·  项目根目录已连接")

        for group in self._scan.groups:
            self._group_cards[group.key].update_summary(group)
            self._group_nav_buttons[group.key].setProperty("ready", group.status == "可整合")
            self._group_nav_buttons[group.key].style().unpolish(self._group_nav_buttons[group.key])
            self._group_nav_buttons[group.key].style().polish(self._group_nav_buttons[group.key])

        handoff_messages = {
            "A": "7 月 17 日图文修正版已接手：71 条清单、10 个 SVG 与 17 页渲染证据通过技术复核。",
            "B": "术语库与 API 接入已就绪；Coze 平台最新版发布仍待 B 组账号确认。",
            "C": "C 组二次交付达标：无需返工，后续接入 DOCX 与音视频通道。",
        }
        for label, group in zip(self._advice_labels, self._scan.groups):
            label.setText(f"{group.key}  {handoff_messages.get(group.key, group.recommendation)}")

        hero_items = [
            f"● A/B/C 就绪：{ready}/{len(self._scan.groups)}",
            f"● 共享术语：{self._scan.terminology.count} 条，可直接检索约束",
            "● Coze：API 入口已接入，最新版发布待 B 组确认",
            f"● 输出中心：{len(output_files)} 个已生成文件",
        ]
        for label, text in zip(self._hero_status_labels, hero_items):
            label.setText(text)

        providers: list[str] = []
        if self._config.has_api_key:
            providers.append("OpenAI")
        if self._config.has_coze_workflow:
            providers.append("扣子")
        online = bool(providers)
        api_text = f"{' + '.join(providers)} 已连接" if online else "离线演示模式"
        self._api_state.setText(f"●  {api_text}")
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
                f"在线通道：{'、'.join(providers)}。未配置的通道仍会明确返回本地说明。"
            )
        else:
            self._agent_state_text.setText(
                "当前为离线演示模式；界面与本地整合可完整运行，"
                "在线模型步骤不会伪装成真实调用。"
            )
        self._agent_state_dot.setProperty("connected", online)
        self._agent_state_dot.style().unpolish(self._agent_state_dot)
        self._agent_state_dot.style().polish(self._agent_state_dot)

        output_path = output_dir_for(self._project_root)
        self._output_path_label.setText("collaboration/integration/final_outputs/generated")
        self._output_path_label.setToolTip(str(output_path))
        self._refresh_outputs_table()
        self._search_terms_now()
        if self._current_page_key == "group":
            self._show_group(self._active_group)
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
        title = self._agent_title.text().strip()
        prompt = self._agent_input.toPlainText()
        if title and mode != "coze_workflow":
            prompt = f"标题/来源：{title}\n\n正文/任务：\n{prompt}"
        self._start_job(mode, prompt, title=title)

    def _clear_agent_input(self) -> None:
        self._agent_title.clear()
        self._agent_input.clear()

    def _run_group_adapter(self) -> None:
        self._start_job(f"adapter:{self._active_group}", self._group_query.text(), allow_empty=True)

    def _run_current_page(self) -> None:
        if self._current_page_key == "agent":
            self._run_agent()
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
        if self._active_mode == "report":
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
        self._top_run_button.setText("整合运行中…" if busy else "运行整合")
        self._agent_run_button.setText("生成中…" if busy else "开始生成")
        self._workflow_run_button.setText("工作流运行中…" if busy else "运行完整工作流")
        self._report_button.setText("报告生成中…" if busy else "生成整合报告")
        self._group_run_button.setText("适配器运行中…" if busy else "运行适配器")
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

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
    app.setApplicationName("华译工作台")
    app.setWindowIcon(make_brand_icon())
    window = MainWindow()
    window.show()
    return app.exec()


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
