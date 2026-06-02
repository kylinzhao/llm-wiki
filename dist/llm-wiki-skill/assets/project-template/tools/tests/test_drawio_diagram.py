import base64
import importlib.util
import sys
import unittest
import zlib
from pathlib import Path
from urllib.parse import quote


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_drawio():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("drawio_diagram", TOOLS_DIR / "drawio_diagram.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DrawioDiagramTest(unittest.TestCase):
    def test_plain_mxgraph_model_converts_to_mermaid(self):
        drawio = load_drawio()
        xml = """<mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="start" value="提交申请" vertex="1" parent="1"/>
  <mxCell id="audit" value="审核通过" vertex="1" parent="1"/>
  <mxCell id="edge1" value="通过" edge="1" source="start" target="audit" parent="1"/>
</root></mxGraphModel>"""

        diagrams = drawio.drawio_to_mermaid(xml, fallback_name="出海流程")

        self.assertEqual(len(diagrams), 1)
        self.assertIn('start["提交申请"]', diagrams[0].mermaid)
        self.assertIn('start -->|"通过"| audit', diagrams[0].mermaid)
        self.assertEqual(diagrams[0].node_count, 2)
        self.assertEqual(diagrams[0].edge_count, 1)

    def test_compressed_drawio_diagram_converts_to_mermaid(self):
        drawio = load_drawio()
        model = """<mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="a" value="A端" vertex="1" parent="1"/>
  <mxCell id="b" value="B端" vertex="1" parent="1"/>
  <mxCell id="e" edge="1" source="a" target="b" parent="1"/>
</root></mxGraphModel>"""
        compressed = zlib.compressobj(level=9, wbits=-15)
        payload = compressed.compress(quote(model).encode("utf-8")) + compressed.flush()
        encoded = base64.b64encode(payload).decode("ascii")
        xml = f'<mxfile><diagram name="压缩图">{encoded}</diagram></mxfile>'

        diagrams = drawio.drawio_to_mermaid(xml)

        self.assertEqual(diagrams[0].name, "压缩图")
        self.assertIn('a["A端"]', diagrams[0].mermaid)
        self.assertIn("a --> b", diagrams[0].mermaid)


if __name__ == "__main__":
    unittest.main()
