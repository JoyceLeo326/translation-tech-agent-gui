from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSize, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .agent import AgentClient
from .config import load_config
from .integration import (
    GROUPS,
    find_project_root,
    format_dashboard_markdown,
    format_terms_markdown,
    output_dir_for,
    run_group_adapter,
    scan_collaboration,
    search_terms,
    write_integration_outputs,
)
from .workflow import (
    WorkflowResult,
    StepResult,
    format_workflow_result,
    run_default_workflow,
    run_translation_integration_workflow,
)


SYSTEM_PROMPT = "你是中国文化多模态知识库外译项目的桌面端智能体助手。请给出准确、简洁、可执行的结果。"


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
                records = search_terms(self._prompt, self._project_root, limit=40)
                self.finished.emit(format_terms_markdown(records))
                return

            if self._mode.startswith("adapter:"):
                group_key = self._mode.split(":", 1)[1]
                self.progress.emit(f"正在运行 {group_key} 组适配器")
                self.finished.emit(run_group_adapter(group_key, self._prompt, self._project_root))
                return

            self.progress.emit("正在调用智能体")
            response = client.run(SYSTEM_PROMPT, self._prompt)
            self.finished.emit(response.text)
        except Exception as exc:  # pragma: no cover - shown in GUI.
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._active_mode = "dashboard"
        self._config = load_config()
        self._project_root = find_project_root()
        self._scan = scan_collaboration(self._project_root)

        self.setWindowTitle(self._config.app_name)
        self.resize(1320, 820)
        self._build_ui()
        self._refresh_from_scan()

    def _build_ui(self) -> None:
        self._resource_tree = QTreeWidget()
        self._resource_tree.setHeaderLabels(["资源区", "状态/数量"])
        self._resource_tree.setMinimumWidth(360)
        self._resource_tree.itemActivated.connect(self._handle_tree_item)

        self._dashboard = self._editor("扫描看板")
        self._agent_output = self._editor("智能体和工作流输出")
        self._log = self._editor("运行日志")
        self._log.setReadOnly(True)

        tabs = QTabWidget()
        tabs.addTab(self._dashboard, "整合看板")
        tabs.addTab(self._agent_output, "智能体/工作流")
        tabs.addTab(self._log, "运行日志")
        self._tabs = tabs

        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("输入要处理的文本、整合目标或术语检索关键词。留空也可以生成当前整合报告。")
        self._input.setMaximumHeight(130)
        self._input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._input.setFont(QFont("Microsoft YaHei UI", 10))

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(tabs)
        right_layout.addWidget(self._panel("输入区", self._input))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._panel("协作资源", self._resource_tree))
        splitter.addWidget(right)
        splitter.setSizes([390, 930])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.addWidget(splitter)
        self.setCentralWidget(root)

        self._build_toolbar()
        self._build_statusbar()
        self._apply_styles()

    def _editor(self, placeholder: str) -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setPlaceholderText(placeholder)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        editor.setFont(QFont("Microsoft YaHei UI", 10))
        return editor

    def _panel(self, title: str, widget: QWidget) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        layout.addWidget(label)
        layout.addWidget(widget)
        return panel

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("工具")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        self.addToolBar(toolbar)

        self._busy_actions: list[QAction] = []
        actions = [
            ("scan", self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "扫描资源", "重新扫描 collaboration 协作区", self._scan_now),
            ("report", self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon), "生成整合报告", "生成 Markdown/CSV/Excel 整合输出", lambda: self._start_job("report", allow_empty=True)),
            ("terms", self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), "术语检索", "检索 B 组共享术语库", lambda: self._start_job("terms", allow_empty=True)),
            ("agent", self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), "智能体", "执行单次智能体调用", lambda: self._start_job("agent")),
            ("workflow", self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "综合工作流", "扫描协作区并调用整合工作流", lambda: self._start_job("integration_workflow", allow_empty=True)),
            ("default", self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "三步工作流", "执行通用分析-草稿-质检流程", lambda: self._start_job("default_workflow")),
        ]
        for _, icon, text, tooltip, callback in actions:
            action = QAction(icon, text, self)
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            toolbar.addAction(action)
            self._busy_actions.append(action)

        toolbar.addSeparator()

        for group_key in ("A", "B", "C"):
            action = QAction(group_key, self)
            action.setToolTip(f"运行 {group_key} 组本地适配器")
            action.triggered.connect(lambda checked=False, key=group_key: self._start_job(f"adapter:{key}", allow_empty=True))
            toolbar.addAction(action)
            self._busy_actions.append(action)

        toolbar.addSeparator()

        open_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "打开输出目录", self)
        open_action.setToolTip("打开 final_outputs/generated 输出目录")
        open_action.triggered.connect(self._open_output_dir)
        toolbar.addAction(open_action)

        save_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "保存当前页", self)
        save_action.setToolTip("保存当前输出文本")
        save_action.triggered.connect(self._save_current_output)
        toolbar.addAction(save_action)

        clear_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton), "清空", self)
        clear_action.setToolTip("清空输入和输出")
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        api_state = "API 已配置" if self._config.has_api_key else "本地占位"
        self._state_label = QLabel(f"{api_state} | {self._config.openai_model}")
        self._state_label.setObjectName("StateLabel")
        toolbar.addWidget(self._state_label)

    def _build_statusbar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage(f"就绪 | 项目根目录：{self._project_root}")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f6f8;
            }
            QToolBar {
                background: #ffffff;
                border: 0;
                border-bottom: 1px solid #d8dde6;
                spacing: 6px;
                padding: 6px 10px;
            }
            QToolButton {
                padding: 7px 10px;
                border-radius: 6px;
                color: #1f2937;
            }
            QToolButton:hover {
                background: #eef3f8;
            }
            QPlainTextEdit, QTreeWidget {
                background: #ffffff;
                border: 1px solid #d8dde6;
                border-radius: 6px;
                padding: 8px;
                color: #111827;
                selection-background-color: #2f6f9f;
            }
            QTabWidget::pane {
                border: 1px solid #d8dde6;
                background: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                padding: 8px 14px;
                color: #374151;
            }
            QTabBar::tab:selected {
                color: #111827;
                font-weight: 600;
                border-bottom: 2px solid #2f6f9f;
            }
            QLabel#PanelTitle {
                color: #374151;
                font-weight: 600;
                padding: 6px 2px;
            }
            QLabel#StateLabel {
                color: #4b5563;
                padding: 0 8px;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #d8dde6;
                color: #4b5563;
            }
            """
        )

    def _refresh_from_scan(self) -> None:
        self._dashboard.setPlainText(format_dashboard_markdown(self._scan))
        self._refresh_tree()
        self._append_log("协作区扫描完成")

    def _refresh_tree(self) -> None:
        self._resource_tree.clear()
        root = QTreeWidgetItem(["collaboration", str(self._project_root / "collaboration")])
        self._resource_tree.addTopLevelItem(root)

        for group in self._scan.groups:
            item = QTreeWidgetItem([group.name, f"{group.status} / {group.file_count} 个文件"])
            item.setData(0, Qt.ItemDataRole.UserRole, group.key)
            root.addChild(item)
            for category, count in group.categories.items():
                item.addChild(QTreeWidgetItem([category, str(count)]))

        shared = QTreeWidgetItem(["shared/terminology", f"{self._scan.terminology.count} 条术语"])
        root.addChild(shared)
        integration = QTreeWidgetItem(["integration/final_outputs", str(output_dir_for(self._project_root))])
        root.addChild(integration)
        root.setExpanded(True)
        for index in range(root.childCount()):
            root.child(index).setExpanded(True)
        self._resource_tree.resizeColumnToContents(0)

    def _handle_tree_item(self, item: QTreeWidgetItem) -> None:
        group_key = item.data(0, Qt.ItemDataRole.UserRole)
        if group_key in GROUPS:
            self._start_job(f"adapter:{group_key}", allow_empty=True)

    def _scan_now(self) -> None:
        self._scan = scan_collaboration(self._project_root)
        self._refresh_from_scan()
        self.statusBar().showMessage("扫描完成")

    def _start_job(self, mode: str, allow_empty: bool = False) -> None:
        prompt = self._input.toPlainText().strip()
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
        if self._active_mode in {"report", "terms"} or self._active_mode.startswith("adapter:"):
            self._dashboard.setPlainText(text)
            self._tabs.setCurrentWidget(self._dashboard)
            self._scan = scan_collaboration(self._project_root)
            self._refresh_tree()
        else:
            self._agent_output.setPlainText(text)
            self._tabs.setCurrentWidget(self._agent_output)

        self.statusBar().showMessage("完成")
        self._append_log(f"任务完成：{self._active_mode}")

    @Slot(str)
    def _handle_failed(self, message: str) -> None:
        self.statusBar().showMessage("失败")
        self._append_log(f"任务失败：{message}")
        QMessageBox.critical(self, "执行失败", message)

    @Slot()
    def _release_worker(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        for action in self._busy_actions:
            action.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _save_current_output(self) -> None:
        current = self._tabs.currentWidget()
        if not isinstance(current, QPlainTextEdit):
            return
        text = current.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "没有输出", "当前页没有可保存的输出。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存输出",
            str(output_dir_for(self._project_root) / "gui-output.md"),
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        Path(path).write_text(text, encoding="utf-8")
        self.statusBar().showMessage(f"已保存：{path}")
        self._append_log(f"已保存当前页：{path}")

    def _open_output_dir(self) -> None:
        out_dir = output_dir_for(self._project_root)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
        self._append_log(f"打开输出目录：{out_dir}")

    def _clear_all(self) -> None:
        self._input.clear()
        self._agent_output.clear()
        self._log.clear()
        self.statusBar().showMessage("已清空")

    def _append_log(self, message: str) -> None:
        self._log.appendPlainText(message)


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
    app.setWindowIcon(QIcon())
    window = MainWindow()
    window.show()
    return app.exec()


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
