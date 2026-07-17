from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QSize, QThread, Qt, QUrl, Signal, Slot
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
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
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
GROUP_ACCENTS = {"A": "#1F6F72", "B": "#9A6A24", "C": "#B4543E"}
UI_FONT_FAMILY = "Microsoft YaHei UI"
ICON_FONT_FAMILY = "Segoe MDL2 Assets"
_FONTS_CONFIGURED = False
PAGE_META = {
    "overview": ("项目总览", "从真实翻译通道进入整合、审校与交付"),
    "agent": ("智能体", "生成、校验并整理翻译任务结果"),
    "terms": ("术语库", "统一文化术语译法与上下文依据"),
    "workflow": ("总整合工作流", "扫描、适配、导出与智能质检"),
    "outputs": ("交付中心", "报告、表格、运行日志与最终输出"),
}


def configure_application_fonts(app: QApplication | None = None) -> None:
    global UI_FONT_FAMILY, ICON_FONT_FAMILY, _FONTS_CONFIGURED
    if _FONTS_CONFIGURED:
        return
    _FONTS_CONFIGURED = True

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/segmdl2.ttf"),
    ]
    loaded_families: list[str] = []
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    families = set(QFontDatabase.families()) | set(loaded_families)
    for preferred in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "SimHei", "SimSun"):
        if preferred in families:
            UI_FONT_FAMILY = preferred
            break
    for preferred in ("Segoe MDL2 Assets", "Segoe Fluent Icons", "Segoe UI Symbol"):
        if preferred in families:
            ICON_FONT_FAMILY = preferred
            break

    target_app = app or QApplication.instance()
    if target_app is not None:
        target_app.setFont(QFont(UI_FONT_FAMILY, 10))


def make_brand_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    padding = max(1, int(size * 0.03))
    painter.setBrush(QColor("#F1EFE9"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(
        padding,
        padding,
        size - padding * 2,
        size - padding * 2,
        max(4, int(size * 0.15)),
        max(4, int(size * 0.15)),
    )
    font = QFont(UI_FONT_FAMILY, max(16, int(size * 0.55)), QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#1E1F1D"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "译")
    accent_size = max(3, int(size * 0.11))
    accent_margin = max(5, int(size * 0.16))
    painter.setBrush(QColor("#C95A45"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(
        size - accent_margin - accent_size,
        size - accent_margin - accent_size,
        accent_size,
        accent_size,
        max(1, int(size * 0.02)),
        max(1, int(size * 0.02)),
    )
    painter.end()
    return QIcon(pixmap)


def make_glyph_icon(glyph: str, color: str = "#666862", size: int = 32) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(color))
    painter.setFont(QFont(ICON_FONT_FAMILY, max(12, int(size * 0.56))))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)


class JobWorker(QObject):
    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, prompt: str, project_root: Path) -> None:
        super().__init__()
        self._mode = mode
        self._prompt = prompt
        self._project_root = project_root

    @Slot()
    def run(self) -> None:
        try:
            config = load_config()
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
            "h1 { color: #20211f; font-size: 22px; margin-bottom: 10px; }"
            "h2 { color: #30312e; font-size: 17px; margin-top: 18px; }"
            "h3 { color: #4d4f4a; font-size: 14px; margin-top: 14px; }"
            "p, li { line-height: 1.55; }"
            "code { background: #f1f0ec; color: #6f4038; }"
            "table { border-collapse: collapse; }"
            "th { background: #f1f1ee; font-weight: 600; }"
            "th, td { border: 1px solid #dfdfdb; padding: 6px; }"
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
        self.setMinimumHeight(104)

        self._value = QLabel("-")
        self._value.setObjectName("StatValue")
        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self._detail = QLabel("")
        self._detail.setObjectName("StatDetail")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self._label)
        text_layout.addWidget(self._value)
        text_layout.addWidget(self._detail)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.addLayout(text_layout)

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
        badge = QLabel(group_key)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(34, 34)
        badge.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border: 0; "
            "border-radius: 6px; font-size: 15px; font-weight: 700;"
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
        open_button.setIcon(make_glyph_icon("\uE72A", "#B34E3D"))
        open_button.clicked.connect(lambda: self.open_requested.emit(self._group_key))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 15)
        layout.setSpacing(10)
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
                "background: transparent; color: #347255; border: 0; font-weight: 600;"
            )
        else:
            self._status.setText(f"●  {summary.status}")
            self._status.setStyleSheet(
                "background: transparent; color: #9B6928; border: 0; font-weight: 600;"
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
        self.setMinimumHeight(190)

        badge_label = QLabel(badge)
        badge_label.setObjectName("TaskBadge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_label.setFixedSize(42, 42)
        badge_label.setStyleSheet(
            f"background: {accent}; color: #FFFFFF; border-radius: 8px; "
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
        primary.clicked.connect(lambda: self.action_requested.emit(primary_action))
        secondary = QPushButton(secondary_label)
        secondary.setObjectName("TaskSecondary")
        secondary.clicked.connect(lambda: self.action_requested.emit(secondary_action))

        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addWidget(primary)
        actions.addWidget(secondary)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(13)
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

        self.setWindowTitle(self._config.app_name)
        self.setWindowIcon(make_brand_icon())
        self.setMinimumSize(1100, 720)
        self.resize(1440, 900)
        self._build_ui()
        self._apply_styles()
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
        sidebar.setFixedWidth(244)

        logo = QLabel()
        logo.setPixmap(make_brand_icon(42).pixmap(42, 42))
        logo.setFixedSize(42, 42)
        brand_title = QLabel("华译工作台")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("多模态知识库整合")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(1)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand = QHBoxLayout()
        brand.setSpacing(11)
        brand.addWidget(logo)
        brand.addLayout(brand_text, 1)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(17, 21, 17, 18)
        layout.setSpacing(7)
        layout.addLayout(brand)
        layout.addSpacing(24)
        layout.addWidget(self._sidebar_label("工作区"))

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        nav_items = [
            ("overview", "项目总览", "\uE80F"),
            ("agent", "智能体", "\uE77B"),
            ("terms", "术语库", "\uE82D"),
            ("workflow", "总整合工作流", "\uE768"),
            ("outputs", "交付中心", "\uE74E"),
        ]
        for key, text, glyph in nav_items:
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(make_glyph_icon(glyph, "#A9AAA5"))
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
        connection_layout.setContentsMargins(12, 11, 12, 11)
        connection_layout.setSpacing(3)
        self._api_state = QLabel()
        self._api_state.setObjectName("ApiState")
        self._model_label = QLabel(self._config.openai_model)
        self._model_label.setObjectName("ModelLabel")
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
        topbar.setFixedHeight(78)
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
        self._scan_button.setIcon(make_glyph_icon("\uE72C"))
        self._scan_button.setIconSize(QSize(19, 19))
        self._scan_button.setToolTip("重新扫描协作资源 (F5)")
        self._scan_button.clicked.connect(self._scan_now)

        output_button = QToolButton()
        output_button.setObjectName("IconButton")
        output_button.setIcon(make_glyph_icon("\uE8B7"))
        output_button.setIconSize(QSize(19, 19))
        output_button.setToolTip("打开输出目录")
        output_button.clicked.connect(self._open_output_dir)

        self._top_run_button = QPushButton("运行整合")
        self._top_run_button.setObjectName("PrimaryButton")
        self._top_run_button.setIcon(make_glyph_icon("\uE768", "#FFFFFF"))
        self._top_run_button.clicked.connect(
            lambda: self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)
        )
        self._busy_controls.extend([self._scan_button, self._top_run_button])

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self._scan_button)
        actions.addWidget(output_button)
        actions.addWidget(self._top_run_button)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(27, 0, 28, 0)
        layout.addLayout(titles)
        layout.addStretch(1)
        layout.addLayout(actions)
        return topbar

    def _build_overview_page(self) -> QWidget:
        content = QWidget()
        content.setObjectName("OverviewContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 30)
        layout.setSpacing(18)

        layout.addWidget(self._overview_hero_panel())

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
        self._report_button.setIcon(make_glyph_icon("\uE9D2", "#252624"))
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
                "读取 A 组翻译清单、最终 DOCX 和图片总览，用于图文资源的翻译回填演示。",
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
                "把 B 组术语库作为全局约束，检索术语后可直接加入智能体任务。",
                "打开术语库",
                "page:terms",
                "查看 B 组",
                "group:B",
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
                "#5F6F52",
            ),
        )
        for card in self._task_cards:
            card.action_requested.connect(self._handle_task_action)
        layout.addLayout(self._task_grid)

        layout.addWidget(self._section_title("整合状态"))

        self._stats_grid = QGridLayout()
        self._stats_grid.setHorizontalSpacing(12)
        self._stats_grid.setVerticalSpacing(12)
        self._stat_ready = StatCard("分组就绪", "#176B4D")
        self._stat_assets = StatCard("资源文件", "#C84A3D")
        self._stat_terms = StatCard("共享术语", "#D18A2C")
        self._stat_outputs = StatCard("已生成输出", "#536F63")
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

    def _overview_hero_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("HeroPanel")
        panel.setMinimumHeight(218)

        eyebrow = QLabel("TRANSLATION TECH WORKBENCH")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("把 A/B/C 交付物变成可演示的翻译工作台")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        subtitle = QLabel(
            "围绕图文回填、术语风格、DOCX 翻译、音视频翻译四条真实路径组织功能。"
            "当前交付物以仓库修正版为准，整合侧可以继续接手。"
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)

        run_button = QPushButton("运行总整合")
        run_button.setObjectName("HeroPrimary")
        run_button.setIcon(make_glyph_icon("\uE768", "#FFFFFF"))
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

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        left.addWidget(eyebrow)
        left.addWidget(title)
        left.addWidget(subtitle)
        left.addStretch(1)
        left.addLayout(actions)

        status_panel = QFrame()
        status_panel.setObjectName("HeroStatusPanel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(16, 15, 16, 15)
        status_layout.setSpacing(10)
        status_title = QLabel("当前可接手范围")
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
        layout.setContentsMargins(26, 24, 24, 22)
        layout.setSpacing(24)
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
        for mode, text in (("agent", "单次智能体"), ("default_workflow", "分析 · 草稿 · 质检")):
            button = QPushButton(text)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setProperty("mode", mode)
            self._agent_modes.addButton(button)
            mode_row.addWidget(button)
        self._agent_modes.buttons()[0].setChecked(True)
        layout.addLayout(mode_row)

        self._agent_input = QPlainTextEdit()
        self._agent_input.setObjectName("InputEditor")
        self._agent_input.setPlaceholderText("输入待翻译文本、审校要求或需要智能体处理的任务…")
        self._agent_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._agent_input, 1)

        footer = QHBoxLayout()
        clear = QPushButton("清空")
        clear.setObjectName("TextButton")
        clear.clicked.connect(self._agent_input.clear)
        self._agent_run_button = QPushButton("开始生成")
        self._agent_run_button.setObjectName("PrimaryButton")
        self._agent_run_button.setIcon(make_glyph_icon("\uE768", "#FFFFFF"))
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
        copy_button = self._icon_button("\uE8C8", "复制结果")
        copy_button.clicked.connect(lambda: self._copy_view(self._agent_output))
        save_button = self._icon_button("\uE74E", "保存结果 (Ctrl+S)")
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
        search_button.setIcon(make_glyph_icon("\uE721", "#FFFFFF"))
        search_button.clicked.connect(self._search_terms_now)
        self._use_term_button = QPushButton("加入智能体约束")
        self._use_term_button.setObjectName("SecondaryButton")
        self._use_term_button.setIcon(make_glyph_icon("\uE710", "#252624"))
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
            node_layout.addWidget(number)
            node_layout.addLayout(texts, 1)
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
        self._workflow_run_button.setIcon(make_glyph_icon("\uE768", "#FFFFFF"))
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
        save_button = self._icon_button("\uE74E", "保存工作流结果")
        save_button.clicked.connect(lambda: self._save_view(self._workflow_output, "workflow-output.md"))
        result_header.addWidget(save_button)
        layout.addLayout(result_header)
        self._workflow_output = MarkdownView("运行完整工作流后，这里会显示四阶段结果与最终建议。")
        self._workflow_output.setObjectName("OutputView")
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
        open_button.setIcon(make_glyph_icon("\uE8B7", "#252624"))
        open_button.clicked.connect(self._open_output_dir)
        report_button = QPushButton("生成报告")
        report_button.setObjectName("PrimaryButton")
        report_button.setIcon(make_glyph_icon("\uE9D2", "#FFFFFF"))
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
        self._delivery_output = MarkdownView("生成整合报告后，报告摘要会显示在这里。")
        self._delivery_output.setObjectName("OutputView")
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
        open_button.setIcon(make_glyph_icon("\uE8B7", "#252624"))
        open_button.clicked.connect(self._open_group_dir)
        self._group_run_button = QPushButton("运行适配器")
        self._group_run_button.setObjectName("PrimaryButton")
        self._group_run_button.setIcon(make_glyph_icon("\uE768", "#FFFFFF"))
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

    def _icon_button(self, glyph: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("IconButton")
        button.setIcon(make_glyph_icon(glyph))
        button.setIconSize(QSize(17, 17))
        button.setToolTip(tooltip)
        return button

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        if hasattr(self, "_stats_grid"):
            workspace_width = max(0, self.width() - 244)
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
        if action == "workflow:run":
            self._switch_page("workflow")
            self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)

    def _switch_page(self, page_key: str) -> None:
        if page_key not in self._pages:
            return
        self._current_page_key = page_key
        self._stack.setCurrentWidget(self._pages[page_key])
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
            "background: transparent; color: #347255; border: 0; font-weight: 600;"
            if ready
            else "background: transparent; color: #9B6928; border: 0; font-weight: 600;"
        )
        self._group_file_count.setText(str(summary.file_count))
        self._group_size.setText(format_size(summary.total_size_bytes))
        self._group_updated.setText(summary.latest_modified_at)
        self._group_path.setText(summary.relative_path)

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
            "A": "图文回填材料可接手：优先使用翻译清单、最终 DOCX 和图片总览。",
            "B": "术语库可接手：共享术语库已作为全局术语与风格控制输入。",
            "C": "C 组二次交付达标：无需返工，后续接入 DOCX 与音视频通道。",
        }
        for label, group in zip(self._advice_labels, self._scan.groups):
            label.setText(f"{group.key}  {handoff_messages.get(group.key, group.recommendation)}")

        hero_items = [
            f"● A/B/C 就绪：{ready}/{len(self._scan.groups)}",
            f"● 共享术语：{self._scan.terminology.count} 条，可直接检索约束",
            "● C 组：按整合接手标准已达标，无需返工",
            f"● 输出中心：{len(output_files)} 个已生成文件",
        ]
        for label, text in zip(self._hero_status_labels, hero_items):
            label.setText(text)

        api_text = "API 已连接" if self._config.has_api_key else "离线演示模式"
        self._api_state.setText(f"●  {api_text}")
        self._api_state.setProperty("connected", self._config.has_api_key)
        self._api_state.style().unpolish(self._api_state)
        self._api_state.style().polish(self._api_state)
        self._agent_state_text.setText(
            f"已连接 {self._config.openai_model}，将调用真实智能体。"
            if self._config.has_api_key
            else "当前未配置 OPENAI_API_KEY；界面与工作流可完整演示，模型步骤返回本地占位结果。"
        )
        self._agent_state_dot.setProperty("connected", self._config.has_api_key)
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
        self._scan = scan_collaboration(self._project_root)
        self._refresh_from_scan()
        self.statusBar().showMessage(f"扫描完成  ·  {len(self._scan.assets)} 个资源文件", 5000)

    def _run_agent(self) -> None:
        checked = self._agent_modes.checkedButton()
        mode = str(checked.property("mode")) if checked is not None else "agent"
        self._start_job(mode, self._agent_input.toPlainText())

    def _run_group_adapter(self) -> None:
        self._start_job(f"adapter:{self._active_group}", self._group_query.text(), allow_empty=True)

    def _run_current_page(self) -> None:
        if self._current_page_key == "agent":
            self._run_agent()
        elif self._current_page_key == "group":
            self._run_group_adapter()
        else:
            self._start_job("integration_workflow", self._workflow_input.toPlainText(), allow_empty=True)

    def _start_job(self, mode: str, prompt: str = "", allow_empty: bool = False) -> None:
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
        self._worker = JobWorker(mode, prompt, self._project_root)
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
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "SimHei";
                font-size: 13px;
                color: #20211F;
            }
            QMainWindow, QWidget#Root, QWidget#Workspace, QStackedWidget#PageStack {
                background: #F6F6F3;
            }
            QFrame#Sidebar {
                background: #1B1C1A;
                border: 0;
            }
            QLabel#BrandTitle {
                color: #FFFFFF;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#BrandSubtitle {
                color: #93958F;
                font-size: 11px;
            }
            QLabel#SidebarLabel {
                color: #747671;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 10px;
            }
            QPushButton#NavButton, QPushButton#GroupNavButton {
                background: transparent;
                color: #C6C7C2;
                border: 0;
                border-radius: 6px;
                padding: 10px 12px;
                text-align: left;
                min-height: 21px;
            }
            QPushButton#NavButton:hover, QPushButton#GroupNavButton:hover {
                background: #252623;
                color: #FFFFFF;
            }
            QPushButton#NavButton:checked {
                background: #2B2C29;
                color: #FFFFFF;
                font-weight: 600;
                border-left: 3px solid #C95A45;
                padding-left: 9px;
            }
            QPushButton#GroupNavButton {
                color: #9B9D97;
                font-size: 12px;
                padding-left: 13px;
            }
            QPushButton#GroupNavButton[ready="true"] {
                color: #D8D9D5;
            }
            QFrame#ConnectionPanel {
                background: #242522;
                border: 1px solid #353632;
                border-radius: 7px;
            }
            QLabel#ApiState {
                color: #D4A14C;
                font-weight: 600;
            }
            QLabel#ApiState[connected="true"] {
                color: #72B28E;
            }
            QLabel#ModelLabel {
                color: #858781;
                font-size: 11px;
            }
            QFrame#TopBar {
                background: #FDFDFC;
                border: 0;
                border-bottom: 1px solid #E0E0DC;
            }
            QFrame#HeroPanel {
                background: #20231F;
                border: 0;
                border-radius: 8px;
            }
            QLabel#HeroEyebrow {
                color: #E0A65A;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0;
            }
            QLabel#HeroTitle {
                color: #FFFFFF;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#HeroSubtitle {
                color: #CFD2C8;
                font-size: 13px;
                line-height: 1.45;
            }
            QFrame#HeroStatusPanel {
                background: #2B2E29;
                border: 1px solid #3C4038;
                border-radius: 8px;
            }
            QLabel#HeroStatusTitle {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#HeroStatusItem {
                color: #D8DBD1;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton#HeroPrimary {
                background: #C95A45;
                color: #FFFFFF;
                border: 1px solid #C95A45;
                border-radius: 7px;
                padding: 10px 16px;
                font-weight: 700;
                min-height: 20px;
            }
            QPushButton#HeroPrimary:hover {
                background: #D46A54;
                border-color: #D46A54;
            }
            QPushButton#HeroSecondary {
                background: transparent;
                color: #F4F1EA;
                border: 1px solid #6A6D62;
                border-radius: 7px;
                padding: 10px 14px;
                font-weight: 700;
                min-height: 20px;
            }
            QPushButton#HeroSecondary:hover {
                background: #33362F;
            }
            QLabel#PageTitle {
                color: #1D1E1C;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#PageSubtitle, QLabel#SectionSubtitle, QLabel#PathLabel {
                color: #747670;
                font-size: 12px;
            }
            QLabel#PathLabel {
                font-family: Consolas;
            }
            QToolButton#IconButton {
                background: #FFFFFF;
                border: 1px solid #DADAD6;
                border-radius: 6px;
                min-width: 35px;
                min-height: 35px;
            }
            QToolButton#IconButton:hover {
                background: #F2F2EF;
                border-color: #BFC0BA;
            }
            QPushButton#PrimaryButton {
                background: #242522;
                color: #FFFFFF;
                border: 1px solid #242522;
                border-radius: 6px;
                padding: 9px 16px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton#PrimaryButton:hover {
                background: #353632;
                border-color: #353632;
            }
            QPushButton#PrimaryButton:pressed {
                background: #121311;
            }
            QPushButton#PrimaryButton:disabled {
                background: #A9AAA5;
                border-color: #A9AAA5;
            }
            QPushButton#SecondaryButton {
                background: #FFFFFF;
                color: #252624;
                border: 1px solid #D3D3CE;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton#SecondaryButton:hover {
                background: #F1F1EE;
                border-color: #B7B8B2;
            }
            QPushButton#SecondaryButton:disabled {
                color: #9B9C97;
                background: #F2F2EF;
            }
            QPushButton#TextButton, QPushButton#CardAction {
                background: transparent;
                color: #B34E3D;
                border: 0;
                padding: 7px 2px;
                font-weight: 600;
            }
            QPushButton#TextButton:hover, QPushButton#CardAction:hover {
                color: #873729;
            }
            QLabel#SectionTitle {
                color: #252624;
                font-size: 15px;
                font-weight: 700;
            }
            QFrame#StatCard, QFrame#GroupCard, QFrame#SectionPanel, QFrame#ToolPanel, QFrame#WorkflowNode, QFrame#TaskEntryCard {
                background: #FFFFFF;
                border: 1px solid #E0E0DC;
                border-radius: 8px;
            }
            QFrame#TaskEntryCard:hover {
                border: 1px solid #C9C7BE;
                background: #FFFEFC;
            }
            QLabel#TaskKicker {
                color: #8A8D85;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#TaskTitle {
                color: #1F211E;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#TaskBody {
                color: #555950;
                font-size: 12px;
                line-height: 1.45;
            }
            QPushButton#TaskPrimary {
                background: #242522;
                color: #FFFFFF;
                border: 1px solid #242522;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QPushButton#TaskPrimary:hover {
                background: #34372F;
                border-color: #34372F;
            }
            QPushButton#TaskSecondary {
                background: #F5F3EE;
                color: #33352F;
                border: 1px solid #DDD9CE;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QPushButton#TaskSecondary:hover {
                background: #ECE8DE;
            }
            QLabel#StatLabel {
                color: #747670;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#StatValue {
                color: #1E1F1D;
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#StatDetail {
                color: #969792;
                font-size: 11px;
            }
            QLabel#GroupTitle {
                color: #20211F;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#GroupSubtitle, QLabel#GroupDescription, QLabel#GroupMetrics, QLabel#CategoryLine {
                color: #81837D;
                font-size: 11px;
            }
            QLabel#GroupDescription {
                color: #555751;
                font-size: 12px;
            }
            QLabel#GroupMetrics {
                color: #2B2C29;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#CategoryLine {
                background: transparent;
                border-radius: 0;
                padding: 3px 0;
                color: #747670;
            }
            QLabel#StageBadge, QLabel#WorkflowNumber {
                background: #F0F0EC;
                color: #3F403D;
                border-radius: 6px;
                font-weight: 700;
            }
            QLabel#StageTitle, QLabel#WorkflowTitle {
                color: #2B2C29;
                font-weight: 600;
            }
            QLabel#StageDetail, QLabel#WorkflowDetail {
                color: #8C8E88;
                font-size: 11px;
            }
            QLabel#ReadyText {
                color: #347255;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#AdviceItem {
                color: #555751;
                line-height: 1.4;
            }
            QFrame#Divider {
                color: #E6E6E2;
                max-height: 1px;
                border: 0;
                background: #E6E6E2;
            }
            QFrame#InfoBanner {
                background: #F3F1EB;
                border: 1px solid #E0DCD2;
                border-radius: 7px;
            }
            QLabel#AgentStateDot {
                color: #C58A35;
            }
            QLabel#AgentStateDot[connected="true"] {
                color: #347255;
            }
            QLabel#InfoText {
                color: #5E594F;
                font-size: 12px;
            }
            QPushButton#SegmentButton {
                background: #F1F1EE;
                color: #70726C;
                border: 1px solid #DADAD6;
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
                color: #252624;
                border-color: #A7A8A2;
                font-weight: 600;
            }
            QPlainTextEdit#InputEditor, QPlainTextEdit#WorkflowInput, QLineEdit#SearchInput,
            QTextBrowser#OutputView, QPlainTextEdit#LogView {
                background: #FFFFFF;
                color: #242522;
                border: 1px solid #DADAD6;
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #E8DED9;
            }
            QPlainTextEdit#InputEditor:focus, QPlainTextEdit#WorkflowInput:focus, QLineEdit#SearchInput:focus {
                border: 1px solid #9D6257;
            }
            QLineEdit#SearchInput {
                min-height: 24px;
                padding: 8px 11px;
            }
            QTableWidget#DataTable {
                background: #FFFFFF;
                alternate-background-color: #F8F8F6;
                border: 1px solid #E0E0DC;
                border-radius: 6px;
                gridline-color: #E8E8E4;
                selection-background-color: #EEE8E4;
                selection-color: #20211F;
            }
            QTableWidget#DataTable::item {
                padding: 6px;
                border: 0;
            }
            QHeaderView::section {
                background: #F1F1EE;
                color: #555751;
                border: 0;
                border-bottom: 1px solid #DADAD6;
                padding: 9px 8px;
                font-weight: 600;
            }
            QScrollArea#PageScroll, QWidget#OverviewContent {
                background: #F6F6F3;
            }
            QProgressBar#TaskProgress {
                background: #E0E0DC;
                border: 0;
            }
            QProgressBar#TaskProgress::chunk {
                background: #C95A45;
            }
            QTabWidget#ResultTabs::pane {
                background: #FFFFFF;
                border: 1px solid #E0E0DC;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #747670;
                padding: 8px 14px;
                border: 0;
            }
            QTabBar::tab:selected {
                color: #252624;
                font-weight: 600;
                border-bottom: 2px solid #C95A45;
            }
            QLabel#DetailTitle {
                color: #20211F;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#InfoLabel {
                color: #8B8D87;
                font-size: 11px;
            }
            QLabel#InfoValue {
                color: #30312E;
                font-weight: 600;
            }
            QStatusBar {
                background: #FDFDFC;
                color: #747670;
                border-top: 1px solid #E0E0DC;
                padding-left: 8px;
            }
            QSplitter::handle {
                background: #F6F6F3;
                width: 10px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #C8C9C4;
                border-radius: 4px;
                min-height: 28px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
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
