from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea

from agent_gui_starter.app import MainWindow, make_brand_icon


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
