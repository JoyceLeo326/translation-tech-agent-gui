from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QScrollArea, QToolButton

import agent_gui_starter.app as app_module
from agent_gui_starter.app import MainWindow, make_brand_icon, make_icon


class WorkbenchUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.resize(1100, 720)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def test_primary_pages_and_brand_asset_are_available(self) -> None:
        self.assertEqual(len(self.window._nav_buttons), 5)
        self.assertEqual(set(self.window._group_cards), {"A", "B", "C"})
        self.assertEqual(self.window._stack.count(), 6)
        self.assertFalse(make_brand_icon().isNull())
        self.assertFalse(make_icon("layout-dashboard").isNull())
        self.assertFalse(make_icon("play").isNull())
        self.assertFalse(make_icon("scan-text").isNull())
        self.assertFalse(make_icon("audio-lines").isNull())
        self.assertEqual(app_module.UI_FONT_FAMILY, "Noto Sans SC")
        self.assertEqual(app_module.DISPLAY_FONT_FAMILY, "Noto Serif SC")
        self.assertIsNotNone(self.window.findChild(QFrame, "ReadinessBand"))
        modes = {str(button.property("mode")) for button in self.window._agent_modes.buttons()}
        self.assertEqual(modes, {"agent", "default_workflow", "coze_workflow"})
        icon_actions = self.window.findChildren(QToolButton, "TaskSecondaryIcon")
        self.assertEqual(len(icon_actions), 4)
        self.assertTrue(all(button.toolTip() for button in icon_actions))

    def test_b_group_entry_opens_coze_workflow_mode(self) -> None:
        self.window._handle_task_action("agent:coze")
        self.assertEqual(self.window._current_page_key, "agent")
        self.assertEqual(self.window._agent_modes.checkedButton().property("mode"), "coze_workflow")
        self.assertTrue(self.window._agent_title.placeholderText())

    def test_action_controls_have_pointer_and_busy_feedback(self) -> None:
        controls = (*self.window.findChildren(QPushButton), *self.window.findChildren(QToolButton))
        self.assertGreater(len(controls), 10)
        self.assertTrue(all(control.cursor().shape() == Qt.CursorShape.PointingHandCursor for control in controls))

        self.window._set_busy(True)
        self.assertEqual(self.window._top_run_button.text(), "整合运行中…")
        self.assertEqual(self.window._agent_run_button.text(), "生成中…")
        self.assertTrue(self.window._progress.isVisible())
        self.window._set_busy(False)
        self.assertEqual(self.window._top_run_button.text(), "运行整合")
        self.assertEqual(self.window._agent_run_button.text(), "开始生成")

    def test_overview_reflows_without_horizontal_scrolling(self) -> None:
        self.window._switch_page("overview")
        self.app.processEvents()
        overview = self.window._pages["overview"]
        self.assertIsInstance(overview, QScrollArea)
        self.assertEqual(self.window._overview_layout_mode, 22)
        self.assertEqual(overview.horizontalScrollBar().maximum(), 0)

    def test_term_search_can_feed_agent_constraints(self) -> None:
        self.window._term_search.setText("孔子")
        self.window._search_terms_now()
        self.assertGreater(self.window._term_table.rowCount(), 0)
        self.assertEqual(self.window._term_table.item(0, 0).text(), "孔子")
        self.window._term_table.selectRow(0)
        self.window._append_selected_term_to_agent()
        self.assertIn("术语约束：孔子", self.window._agent_input.toPlainText())
        self.assertEqual(self.window._current_page_key, "agent")

    def test_status_pages_have_real_initial_content(self) -> None:
        self.assertIn("19/19", self.window._delivery_output.raw_text())
        self.assertIn("71 条审校清单", self.window._workflow_output.raw_text())
        self.window._show_group("A")
        self.assertIn("extracted_20260717_update", self.window._group_output.raw_text())

    def test_each_workspace_page_renders_nonblank(self) -> None:
        for page_key in ("overview", "agent", "terms", "workflow", "outputs"):
            self.window._switch_page(page_key)
            self.app.processEvents()
            image = self.window.grab().toImage()
            self.assertFalse(image.isNull(), page_key)
            self.assertGreater(image.width(), 1000, page_key)
            self.assertGreater(image.height(), 700, page_key)


if __name__ == "__main__":
    unittest.main()
