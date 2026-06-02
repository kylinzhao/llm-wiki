import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_drawio_repair():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("drawio_repair", TOOLS_DIR / "drawio_repair.py")
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


class DrawioRepairTest(unittest.TestCase):
    def test_repair_writes_evidence_and_links_page_index(self):
        drawio_repair = load_drawio_repair()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            page = project / "raw" / "product" / "index.md"
            page.parent.mkdir(parents=True)
            page.write_text("# Product\n\n正文。\n", encoding="utf-8")
            drawio = page.parent / "assets" / "flow.drawio"
            drawio.parent.mkdir()
            drawio.write_text(DRAWIO_XML, encoding="utf-8")

            report = drawio_repair.build_report(project)
            drawio_repair.write_report(project, report)

            evidence = drawio.with_suffix(".drawio.md")
            self.assertTrue(evidence.is_file())
            self.assertIn("flowchart TD", evidence.read_text(encoding="utf-8"))
            page_text = page.read_text(encoding="utf-8")
            self.assertIn("## Draw.io Diagrams", page_text)
            self.assertIn("assets/flow.drawio.md", page_text)
            self.assertEqual(report["drawio_count"], 1)
            self.assertEqual(report["converted_count"], 1)
            self.assertEqual(report["missing_evidence_count"], 0)

    def test_check_reports_missing_without_writing(self):
        drawio_repair = load_drawio_repair()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            drawio = project / "raw" / "product" / "assets" / "flow.drawio"
            drawio.parent.mkdir(parents=True)
            drawio.write_text(DRAWIO_XML, encoding="utf-8")

            report = drawio_repair.build_report(project, check=True)

            self.assertEqual(report["changed_count"], 1)
            self.assertFalse(drawio.with_suffix(".drawio.md").exists())


if __name__ == "__main__":
    unittest.main()
