from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QScrollArea, QToolButton

import agent_gui_starter.app as app_module
from agent_gui_starter.app import MainWindow, StartDropZone, make_brand_icon, make_icon


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
        self.assertEqual(len(self.window._nav_buttons), 7)
        self.assertEqual(self.window._group_cards, {})
        self.assertEqual(self.window._stack.count(), 7)
        self.assertFalse(make_brand_icon().isNull())
        self.assertFalse(make_icon("layout-dashboard").isNull())
        self.assertFalse(make_icon("play").isNull())
        self.assertFalse(make_icon("scan-text").isNull())
        self.assertFalse(make_icon("audio-lines").isNull())
        self.assertFalse(make_icon("clipboard-check").isNull())
        self.assertEqual(app_module.UI_FONT_FAMILY, "Noto Sans SC")
        self.assertEqual(app_module.DISPLAY_FONT_FAMILY, "Noto Serif SC")
        self.assertEqual(self.window.findChild(QFrame, "Sidebar").width(), 112)
        self.assertIsNotNone(self.window.findChild(StartDropZone, "StartDropZone"))
        self.assertIsNotNone(self.window.findChild(QFrame, "StudioSample"))
        self.assertIsNotNone(self.window.findChild(QFrame, "StudioProofBand"))
        self.assertIsNotNone(self.window.findChild(QFrame, "WorkflowCommandPanel"))
        self.assertIsNotNone(self.window.findChild(QFrame, "WorkflowDeliveryPanel"))
        self.assertIsNotNone(self.window.findChild(QFrame, "OutputsSummaryBand"))
        self.assertIsNotNone(self.window.findChild(QFrame, "ShowcaseHero"))
        modes = {str(button.property("mode")) for button in self.window._agent_modes.buttons()}
        self.assertEqual(modes, {"agent", "default_workflow", "coze_workflow"})
        quick_actions = self.window.findChildren(QPushButton, "QuickStartButton")
        self.assertEqual(len(quick_actions), 4)
        self.assertEqual(
            {button.text() for button in quick_actions},
            {
                "翻译图片\n识别图中文字并生成英文",
                "翻译 Word\n保留原版式导出英文文档",
                "翻译音视频\n生成审校表与英文配音",
                "翻译文字\n粘贴内容直接得到英文",
            },
        )
        self.assertEqual(
            {button.property("accent") for button in quick_actions},
            {"coral", "blue", "jade", "gold"},
        )

    def test_coze_entry_opens_coze_workflow_mode(self) -> None:
        self.window._handle_task_action("agent:coze")
        self.assertEqual(self.window._current_page_key, "agent")
        self.assertEqual(self.window._agent_modes.checkedButton().property("mode"), "coze_workflow")
        self.assertEqual(self.window._agent_mode_title.text(), "多模型精译（扣子）")
        self.assertIn("18 个节点", self.window._agent_mode_proof.text())
        self.assertTrue(self.window._agent_title.placeholderText())

    def test_action_controls_have_pointer_and_busy_feedback(self) -> None:
        controls = (*self.window.findChildren(QPushButton), *self.window.findChildren(QToolButton))
        self.assertGreater(len(controls), 10)
        self.assertTrue(all(control.cursor().shape() == Qt.CursorShape.PointingHandCursor for control in controls))

        self.window._set_busy(True)
        self.assertEqual(self.window._top_run_button.text(), "处理中…")
        self.assertEqual(self.window._agent_run_button.text(), "生成中…")
        self.assertTrue(self.window._progress.isVisible())
        self.window._set_busy(False)
        self.assertEqual(self.window._top_run_button.text(), "新建翻译")
        self.assertEqual(self.window._agent_run_button.text(), "生成译文")

    def test_overview_reflows_without_horizontal_scrolling(self) -> None:
        self.window._switch_page("overview")
        self.app.processEvents()
        overview = self.window._pages["overview"]
        self.assertIsInstance(overview, QScrollArea)
        self.assertEqual(self.window._overview_layout_mode, 1)
        self.assertEqual(overview.horizontalScrollBar().maximum(), 0)

    def test_beginner_example_populates_input_and_visible_result(self) -> None:
        self.window._switch_page("agent")
        self.window._insert_translation_example()
        self.assertIn("端午节", self.window._agent_input.toPlainText())
        self.assertIn("Dragon Boat Festival", self.window._agent_output.raw_text())

    def test_showcase_exposes_real_verifiable_outputs(self) -> None:
        self.window._switch_page("showcase")
        self.app.processEvents()
        self.assertEqual(self.window._current_page_key, "showcase")
        buttons = {button.text() for button in self.window.findChildren(QPushButton)}
        self.assertIn("开始现场演示", buttons)
        self.assertIn("审校表", buttons)
        self.assertIn("英文配音", buttons)
        self.assertIn("查看流程演示", buttons)

    def test_coze_mode_has_a_token_free_explainable_demo(self) -> None:
        self.window._switch_page("agent")
        self.window._show_coze_demo()
        output = self.window._agent_output.raw_text()
        self.assertIn("多模型精译流程演示", output)
        self.assertIn("18 个节点", output)
        self.assertIn("未发起网络请求", output)
        self.assertIn("Dragon Boat Festival", output)

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
        self.assertIn("已准备好的成品", self.window._delivery_output.raw_text())
        self.assertIn("Word XML 回填", self.window._workflow_output.raw_text())
        self.window._handle_task_action("production:resources")
        self.assertEqual(self.window._current_page_key, "production")
        self.assertEqual(self.window._production_tabs.currentIndex(), 3)
        self.assertGreater(self.window._resource_table.rowCount(), 100)

    def test_complete_example_connects_real_inputs(self) -> None:
        self.window._load_production_example()
        self.assertTrue(self.window._docx_source.text().endswith("童话故事2.docx"))
        self.assertTrue(self.window._docx_review.text().endswith(".xlsx"))
        self.assertTrue(self.window._audio_source.text().endswith("测试音频.mp3"))
        self.assertTrue(self.window._audio_review.text().endswith("模式二生成终版表格.xlsx"))
        self.assertIn("完整示例已载入", self.window._production_output.raw_text())

    def test_each_workspace_page_renders_nonblank(self) -> None:
        for page_key in ("overview", "production", "agent", "terms", "workflow", "showcase", "outputs"):
            self.window._switch_page(page_key)
            self.app.processEvents()
            image = self.window.grab().toImage()
            self.assertFalse(image.isNull(), page_key)
            self.assertGreater(image.width(), 1000, page_key)
            self.assertGreater(image.height(), 700, page_key)


if __name__ == "__main__":
    unittest.main()
