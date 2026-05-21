import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_health():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("health", TOOLS_DIR / "health.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SourceLinkCompatTest(unittest.TestCase):
    def test_health_accepts_legacy_source_wikilink_for_canonical_index_page(self):
        health = load_health()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "wiki" / "sources" / "123-业务页面-index.md"
            concept = project / "wiki" / "concepts" / "业务概念.md"
            source.parent.mkdir(parents=True)
            concept.parent.mkdir(parents=True)
            source.write_text("# 业务页面\n", encoding="utf-8")
            concept.write_text("# 业务概念\n\n参考 [[sources/123-业务页面]]。\n", encoding="utf-8")

            broken = health.find_broken_links(project, health.markdown_pages(project))

            self.assertEqual(broken, [])

    def test_graph_accepts_legacy_source_wikilink_for_canonical_index_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "wiki" / "sources" / "123-业务页面-index.md"
            concept = project / "wiki" / "concepts" / "业务概念.md"
            source.parent.mkdir(parents=True)
            concept.parent.mkdir(parents=True)
            source.write_text("# 业务页面\n", encoding="utf-8")
            concept.write_text("# 业务概念\n\n参考 [[sources/123-业务页面]]。\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "build_graph.py"), "--project", str(project)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((project / "staging" / "graph" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["broken_edges"], 0)

    def test_graph_accepts_bare_page_stem_wikilink(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            target = project / "wiki" / "entities" / "KA商户.md"
            source = project / "wiki" / "truth" / "当前基线.md"
            target.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            target.write_text("# KA商户\n", encoding="utf-8")
            source.write_text("# 当前基线\n\n参考 [[KA商户]]。\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "build_graph.py"), "--project", str(project)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((project / "staging" / "graph" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["broken_edges"], 0)


if __name__ == "__main__":
    unittest.main()
