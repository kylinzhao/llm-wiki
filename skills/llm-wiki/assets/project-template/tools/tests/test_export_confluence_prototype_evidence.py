import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile
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


def zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeResponse:
    status_code = 200

    def __init__(self, payload: bytes, text: str = ""):
        self.payload = payload
        self.text = text or payload.decode("utf-8", errors="replace")

    def iter_content(self, chunk_size=8192):
        yield self.payload


class JsonResponse:
    status_code = 200

    def __init__(self, exporter, payload):
        self.payload = payload
        self.text = exporter.json.dumps(payload)

    def json(self):
        return self.payload


class PrototypeSession:
    request_timeout = 30
    request_interval = 0.0
    asset_request_interval = 0.0
    last_request_at = 0.0

    def __init__(self, exporter, payload: bytes):
        self.exporter = exporter
        self.payload = payload

    def get(self, url, timeout=30, stream=False, headers=None):
        if "/child/attachment" in url:
            return JsonResponse(
                self.exporter,
                {
                    "results": [
                        {
                            "_links": {
                                "base": "https://cwiki.guazi.com",
                                "download": "/download/attachments/669314782/prototype.zip",
                            }
                        }
                    ]
                },
            )
        return FakeResponse(self.payload)


class ExportConfluencePrototypeEvidenceTest(unittest.TestCase):
    def test_zip_attachment_is_exported_as_prototype_evidence_note(self):
        exporter = load_exporter()
        prototype_zip = zip_bytes(
            {
                "__MACOSX/._index.html": "Mac OS X metadata",
                "index.html": "<html><head><title>保证金原型</title></head><body><button>确认提交</button><form><input name='deposit'></form></body></html>",
                "mock/data.json": '{"status":"draft"}',
            }
        )
        page = exporter.PageNode(
            page_id="669314782",
            title="保证金需求",
            url="https://cwiki.guazi.com/pages/viewpage.action?pageId=669314782",
            depth=0,
            html="<p>正文</p>",
            storage_html='<ri:attachment ri:filename="prototype.zip"/>',
        )

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            markdown = exporter.prototype_evidence_markdown(page, page_dir, PrototypeSession(exporter, prototype_zip))

            self.assertIn("## Prototype Attachments", markdown)
            self.assertIn("prototype.zip.prototype.md", markdown)
            self.assertTrue((page_dir / "assets" / "prototype.zip").is_file())
            self.assertTrue((page_dir / "assets" / "prototypes" / "prototype" / "index.html").is_file())
            note = (page_dir / "assets" / "prototype.zip.prototype.md").read_text(encoding="utf-8")
            self.assertIn("HTML entry points", note)
            self.assertIn("index.html", note)
            self.assertIn("保证金原型", note)
            self.assertIn("确认提交", note)
            self.assertIn("mock/data.json", note)
            self.assertIn('"status":"draft"', note)
            self.assertNotIn("__MACOSX", note)

    def test_media_only_zip_does_not_generate_text_evidence_note(self):
        exporter = load_exporter()
        prototype_zip = zip_bytes({"cover.png": "not really png"})
        page = exporter.PageNode(
            page_id="623012387",
            title="首/列/招商页增加 OG",
            url="https://cwiki.guazi.com/pages/viewpage.action?pageId=623012387",
            depth=0,
            html="<p>正文</p>",
            storage_html='<ri:attachment ri:filename="prototype.zip"/>',
        )

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            markdown = exporter.prototype_evidence_markdown(page, page_dir, PrototypeSession(exporter, prototype_zip))

            self.assertEqual("", markdown)
            self.assertFalse((page_dir / "assets" / "prototype.zip.prototype.md").exists())

    def test_zip_mojibake_paths_and_sketch_meaxure_data_are_summarized(self):
        exporter = load_exporter()
        garbled_dir = "Φ╜ªσòåτ«ÇµèÑ+µêÉΘò┐"
        prototype_zip = zip_bytes(
            {
                f"{garbled_dir}/index.html": """
<html><head><title>Spec Export - Sketch MeaXure</title></head><body>
<script>
let data = {"artboards":[
  {"name":"4-车商成长/评分弹窗","width":750,"height":1497,"layers":[
    {"type":"text","content":"评分"},
    {"type":"text","content":"选项文字"}
  ]},
  {"name":"车商简报-初始状态","width":750,"height":1200,"layers":[
    {"type":"text","content":"今日行为"}
  ]}
]};
</script>
</body></html>
""",
            }
        )
        page = exporter.PageNode(
            page_id="410028163",
            title="商好多V1.7_车商简报+诊断",
            url="https://cwiki.guazi.com/pages/viewpage.action?pageId=410028163",
            depth=0,
            html="<p>正文</p>",
            storage_html='<ri:attachment ri:filename="prototype.zip"/>',
        )

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            exporter.prototype_evidence_markdown(page, page_dir, PrototypeSession(exporter, prototype_zip))

            note = (page_dir / "assets" / "prototype.zip.prototype.md").read_text(encoding="utf-8")
            self.assertIn("车商简报+成长/index.html", note)
            self.assertIn("Sketch MeaXure artboards", note)
            self.assertIn("4-车商成长/评分弹窗", note)
            self.assertIn("车商简报-初始状态", note)
            self.assertIn("评分", note)
            self.assertNotIn(garbled_dir, note)

    def test_html_form_structure_is_summarized_for_ai_refinement(self):
        exporter = load_exporter()
        prototype_zip = zip_bytes(
            {
                "form.html": """
<html><head><title>Customer Visit Form</title></head><body>
<button class="tab active" id="tab1">New Visit</button>
<button class="tab" id="tab2">Return Visit</button>
<div id="newVisitFields">
  <div class="form-item"><label class="label">Customer Email <span>*</span></label><input type="email" id="customerEmail" placeholder="Please enter customer email"></div>
  <div class="form-item"><label class="label">Customer Type <span>*</span></label>
    <label class="radio-item"><input type="radio" name="customerType" value="End Customer"><span>End Customer</span></label>
    <label class="radio-item"><input type="radio" name="customerType" value="Wholesale"><span>Wholesale</span></label>
  </div>
  <div class="form-item"><label class="label">Check-in pic <span>*</span></label><input type="file" id="visitProof" multiple accept="image/jpeg,image/png,application/pdf"></div>
</div>
<div id="returnVisitFields" class="hidden">
  <div class="form-item"><label class="label">Visit Type <span>*</span></label>
    <label class="radio-item"><input type="radio" name="visitType" value="WhatsApp"><span>WhatsApp</span></label>
    <label class="radio-item"><input type="radio" name="visitType" value="On-site"><span>On-site</span></label>
  </div>
</div>
<button class="submit-btn" id="submitBtn">Submit</button>
</body></html>
""",
            }
        )
        page = exporter.PageNode(
            page_id="669314782",
            title="出海属地化_拆分新老客提交",
            url="https://cwiki.guazi.com/pages/viewpage.action?pageId=669314782",
            depth=0,
            html="<p>正文</p>",
            storage_html='<ri:attachment ri:filename="prototype.zip"/>',
        )

        with tempfile.TemporaryDirectory() as tmp:
            page_dir = Path(tmp)
            exporter.prototype_evidence_markdown(page, page_dir, PrototypeSession(exporter, prototype_zip))

            note = (page_dir / "assets" / "prototype.zip.prototype.md").read_text(encoding="utf-8")
            self.assertIn("#### Prototype structure", note)
            self.assertIn("- Modes/tabs: New Visit, Return Visit", note)
            self.assertIn("##### Section `newVisitFields`", note)
            self.assertIn("Customer Email | email | required | customerEmail | Please enter customer email", note)
            self.assertIn("Customer Type | radio | required | customerType | End Customer; Wholesale", note)
            self.assertIn("Check-in pic | file | required | visitProof | accepts: image/jpeg,image/png,application/pdf; multiple", note)
            self.assertIn("##### Section `returnVisitFields`", note)
            self.assertIn("Visit Type | radio | required | visitType | WhatsApp; On-site", note)
            self.assertIn("- Buttons: New Visit, Return Visit, Submit", note)

if __name__ == "__main__":
    unittest.main()
