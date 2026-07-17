from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_gui_starter.integration import (
    format_dashboard_markdown,
    format_terms_markdown,
    run_group_adapter,
    scan_collaboration,
    search_terms,
    write_integration_outputs,
)


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for group_dir in ("A_image_translation", "B_terms_style", "C_text_audio_translation"):
            (self.root / "collaboration" / "groups" / group_dir / "deliverables").mkdir(parents=True)
        (self.root / "collaboration" / "shared" / "terminology").mkdir(parents=True)
        (self.root / "collaboration" / "integration" / "final_outputs").mkdir(parents=True)

        (self.root / "collaboration" / "groups" / "A_image_translation" / "deliverables" / "sample.md").write_text(
            "A",
            encoding="utf-8",
        )
        terms = [
            {
                "术语": "孔子",
                "英文翻译": "Confucius",
                "出处页码": 1,
                "上下文片段": "孔子与儒家文化",
                "source_row": 2,
            }
        ]
        (
            self.root
            / "collaboration"
            / "shared"
            / "terminology"
            / "zhonghua_culture_terms.normalized.json"
        ).write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scan_collaboration_reads_groups_and_terms(self) -> None:
        scan = scan_collaboration(self.root)
        self.assertEqual(len(scan.groups), 3)
        self.assertEqual(scan.terminology.count, 1)
        self.assertIn("A 组", format_dashboard_markdown(scan))

    def test_term_search_and_markdown(self) -> None:
        matches = search_terms("孔子", self.root)
        self.assertEqual(matches[0]["英文翻译"], "Confucius")
        self.assertIn("Confucius", format_terms_markdown(matches))

    def test_write_integration_outputs(self) -> None:
        scan = scan_collaboration(self.root)
        bundle = write_integration_outputs(scan, "测试目标")
        self.assertTrue(bundle.markdown_path.exists())
        self.assertTrue(bundle.csv_path.exists())
        self.assertIsNotNone(bundle.excel_path)
        self.assertTrue(bundle.excel_path and bundle.excel_path.exists())

    def test_a_adapter_prefers_latest_reviewed_delivery(self) -> None:
        latest = (
            self.root
            / "collaboration"
            / "groups"
            / "A_image_translation"
            / "deliverables"
            / "extracted_20260717_update"
        )
        for path in (
            latest / "manifests" / "translation_manifest_reviewed.xlsx",
            latest / "final_outputs" / "翻译资源编写-中国文化知识百科_A组更新完整修正版.docx",
            latest / "previews" / "final_docx_pages_contact_sheet.jpg",
            latest / "validation" / "validation_report.json",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test")

        report = run_group_adapter("A", project_root=self.root)

        self.assertIn("extracted_20260717_update", report)
        self.assertIn("translation_manifest_reviewed.xlsx", report)
        self.assertNotIn("extracted_20260715", report)


if __name__ == "__main__":
    unittest.main()
