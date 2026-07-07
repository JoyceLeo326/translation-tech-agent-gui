from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSize, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .agent import AgentClient
from .config import load_config
from .workflow import WorkflowResult, StepResult, format_workflow_result, run_default_workflow


SYSTEM_PROMPT = "你是一个可靠的桌面应用智能体助手。请给出准确、简洁、可执行的结果。"


class JobWorker(QObject):
    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, prompt: str) -> None:
        super().__init__()
        self._mode = mode
        self._prompt = prompt

    @Slot()
    def run(self) -> None:
        try:
            config = load_config()
            client = AgentClient(config)
            if self._mode == "workflow":
                result = run_default_workflow(client, self._prompt, self.progress.emit)
                self.finished.emit(format_workflow_result(result))
            else:
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
        self._config = load_config()

        self.setWindowTitle(self._config.app_name)
        self.resize(1180, 760)
        self._build_ui()

    def _build_ui(self) -> None:
        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("输入任务、材料或工作流目标")
        self._input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        self._output = QPlainTextEdit()
        self._output.setPlaceholderText("运行结果会显示在这里")
        self._output.setReadOnly(True)
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        font = QFont("Microsoft YaHei UI", 10)
        self._input.setFont(font)
        self._output.setFont(font)

        left = self._panel("输入", self._input)
        right = self._panel("输出", self._output)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([560, 620])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.addWidget(splitter)
        self.setCentralWidget(root)

        self._build_toolbar()
        self._build_statusbar()
        self._apply_styles()

    def _panel(self, title: str, editor: QPlainTextEdit) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        layout.addWidget(label)
        layout.addWidget(editor)
        return panel

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("工具")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        self.addToolBar(toolbar)

        run_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        workflow_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        save_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        clear_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)

        self._agent_action = QAction(run_icon, "智能体", self)
        self._agent_action.setToolTip("执行单次智能体调用")
        self._agent_action.triggered.connect(lambda: self._start_job("agent"))
        toolbar.addAction(self._agent_action)

        self._workflow_action = QAction(workflow_icon, "工作流", self)
        self._workflow_action.setToolTip("按预设步骤执行工作流")
        self._workflow_action.triggered.connect(lambda: self._start_job("workflow"))
        toolbar.addAction(self._workflow_action)

        toolbar.addSeparator()

        save_action = QAction(save_icon, "保存", self)
        save_action.setToolTip("保存输出文本")
        save_action.triggered.connect(self._save_output)
        toolbar.addAction(save_action)

        clear_action = QAction(clear_icon, "清空", self)
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
        status.showMessage("就绪")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f6f7f9;
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
                background: #edf2f7;
            }
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #d8dde6;
                border-radius: 6px;
                padding: 10px;
                color: #111827;
                selection-background-color: #2563eb;
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

    def _start_job(self, mode: str) -> None:
        prompt = self._input.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "需要输入", "请先输入要处理的内容。")
            return
        if self._thread is not None:
            return

        self._set_busy(True)
        self._output.setPlainText("")

        self._thread = QThread(self)
        self._worker = JobWorker(mode, prompt)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.statusBar().showMessage)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._release_worker)
        self._thread.start()

    @Slot(str)
    def _handle_finished(self, text: str) -> None:
        self._output.setPlainText(text)
        self.statusBar().showMessage("完成")

    @Slot(str)
    def _handle_failed(self, message: str) -> None:
        self.statusBar().showMessage("失败")
        QMessageBox.critical(self, "执行失败", message)

    @Slot()
    def _release_worker(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._agent_action.setEnabled(not busy)
        self._workflow_action.setEnabled(not busy)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) if busy else QApplication.restoreOverrideCursor()

    def _save_output(self) -> None:
        text = self._output.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "没有输出", "当前没有可保存的输出。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存输出",
            str(Path.cwd() / "agent-output.txt"),
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)",
        )
        if not path:
            return

        Path(path).write_text(text, encoding="utf-8")
        self.statusBar().showMessage(f"已保存：{path}")

    def _clear_all(self) -> None:
        self._input.clear()
        self._output.clear()
        self.statusBar().showMessage("已清空")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-check" in argv:
        config = load_config()
        print(f"app={config.app_name}")
        print(f"model={config.openai_model}")
        print(f"api_key={'yes' if config.has_api_key else 'no'}")
        return 0
    if "--smoke-test" in argv:
        result = WorkflowResult(
            steps=[
                StepResult("environment", "configuration loaded", "local-test"),
                StepResult("workflow", "formatting ok", "local-test"),
            ]
        )
        print(format_workflow_result(result))
        return 0

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon())
    window = MainWindow()
    window.show()
    return app.exec()
