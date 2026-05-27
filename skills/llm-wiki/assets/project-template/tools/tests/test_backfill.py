import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_backfill():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("backfill", TOOLS_DIR / "backfill.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRAWIO_XML = """<mxfile><diagram name="流程"><mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="a" value="提交" vertex="1" parent="1"/>
  <mxCell id="b" value="审核" vertex="1" parent="1"/>
  <mxCell id="e" value="通过" edge="1" source="a" target="b" parent="1"/>
</root></mxGraphModel></diagram></mxfile>"""


class BackfillTest(unittest.TestCase):
    def test_backfill_repairs_historical_evidence_and_requests_refinement_absorption(self):
        backfill = load_backfill()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text(
                "# Product Flow\n\n"
                "| 更新时间 | 修改内容 | cjira |\n"
                "| --- | --- | --- |\n"
                "| 2026-05-01 | 调整流程 | PSP-40038 |\n",
                encoding="utf-8",
            )
            drawio = raw_page.parent / "assets" / "flow.drawio"
            drawio.parent.mkdir()
            drawio.write_text(DRAWIO_XML, encoding="utf-8")

            source_page = project / "wiki" / "sources" / "product-index.md"
            source_page.parent.mkdir(parents=True)
            source_page.write_text("# Product Flow\n\n## Summary\n\n旧摘要。\n", encoding="utf-8")

            report = backfill.run_backfill(project)

            self.assertEqual(report["status"], "ok")
            self.assertTrue(report["refinement_absorption_required"])
            self.assertIn("drawio", report["passes"])
            self.assertIn("cjira", report["passes"])
            self.assertIn("source_metadata", report["passes"])
            self.assertGreaterEqual(report["passes"]["drawio"]["changed_count"], 1)
            self.assertGreaterEqual(report["passes"]["source_metadata"]["changed_count"], 1)
            self.assertTrue(drawio.with_suffix(".drawio.md").is_file())
            self.assertTrue((project / "staging" / "cjira-registry" / "active.json").is_file())
            self.assertTrue((project / "staging" / "backfill" / "latest.json").is_file())

            latest = json.loads((project / "staging" / "backfill" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["next_command"], "llm-wiki update")
            self.assertIn("wiki/sources/product-index.md", latest["refinement_scope"]["source_pages"])
            source_text = source_page.read_text(encoding="utf-8")
            self.assertIn("## Delivery Tracking", source_text)
            self.assertIn("## Source Metadata", source_text)

    def test_backfill_is_idempotent_after_first_run(self):
        backfill = load_backfill()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# Product Flow\n\nPSP-40038\n", encoding="utf-8")
            source_page = project / "wiki" / "sources" / "product-index.md"
            source_page.parent.mkdir(parents=True)
            source_page.write_text("# Product Flow\n", encoding="utf-8")

            first = backfill.run_backfill(project)
            second = backfill.run_backfill(project)

            self.assertTrue(first["refinement_absorption_required"])
            self.assertFalse(second["refinement_absorption_required"])
            self.assertEqual(second["passes"]["drawio"]["changed_count"], 0)
            self.assertEqual(second["passes"]["source_metadata"]["changed_count"], 0)


if __name__ == "__main__":
    unittest.main()
