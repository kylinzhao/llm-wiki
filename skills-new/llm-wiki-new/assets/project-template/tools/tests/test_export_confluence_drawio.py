import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
CONFLUENCE_DIR = TOOLS_DIR / "confluence_sync"


def load_exporter():
    sys.path.insert(0, str(TOOLS_DIR))
    sys.path.insert(0, str(CONFLUENCE_DIR))
    spec = importlib.util.spec_from_file_location("export_confluence_tree", CONFLUENCE_DIR / "export_confluence_tree.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: bytes):
        self.payload = payload

    def iter_content(self, chunk_size=8192):
        yield self.payload


class FakeSession:
    request_timeout = 30
    request_interval = 0.0
    asset_request_interval = 0.0
    last_request_at = 0.0

    def __init__(self, exporter, drawio_text: str):
        self.exporter = exporter
        self.drawio_text = drawio_text

    def get(self, url, timeout=30, stream=False, headers=None):
        if "/child/attachment" in url:
            payload = {
                "results": [
                    {
                        "_links": {
                            "base": "https://cwiki.guazi.com",
                            "download": "/download/attachments/669314782/flow.drawio",
                        }
                    }
                ]
            }
            return JsonResponse(self.exporter, payload)
        return FakeResponse(self.drawio_text.encode("utf-8"))


class JsonResponse:
    status_code = 200

    def __init__(self, exporter, payload):
        self.payload = payload
        self.text = exporter.json.dumps(payload)

    def json(self):
        return self.payload


class ExportConfluenceDrawioTest(unittest.TestCase):
    def test_drawio_macro_is_exported_as_page_mermaid_and_asset_note(self):
        exporter = load_exporter()
        drawio_text = """<mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="start" value="开始" vertex="1" parent="1"/>
  <mxCell id="end" value="结束" vertex="1" parent="1"/>
  <mxCell id="edge" edge="1" source="start" target="end" parent="1"/>
</root></mxGraphModel>"""
        page = exporter.PageNode(
            page_id="669314782",
            title="出海流程",
            url="https://cwiki.guazi.com/pages/viewpage.action?pageId=669314782",
            depth=0,
            html="<p>正文</p>",
            storage_html='<ac:structured-macro ac:name="drawio"><ac:parameter ac:name="diagramName">flow.drawio</ac:parameter></ac:structured-macro>',
        )

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            markdown = exporter.drawio_evidence_markdown(page, page_dir, FakeSession(exporter, drawio_text))

            self.assertIn("## Draw.io Diagrams", markdown)
            self.assertIn("```mermaid", markdown)
            self.assertIn('start["开始"]', markdown)
            self.assertTrue((page_dir / "assets" / "flow.drawio").is_file())
            note = (page_dir / "assets" / "flow.drawio.md").read_text(encoding="utf-8")
            self.assertIn('end["结束"]', note)


if __name__ == "__main__":
    unittest.main()
