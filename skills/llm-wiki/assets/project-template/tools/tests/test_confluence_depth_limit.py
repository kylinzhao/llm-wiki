import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
EXPORTER = TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_confluence_tree", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_confluence_tree"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ConfluenceDepthLimitTests(unittest.TestCase):
    def test_normalize_confluence_depth_limit_defaults_zero_to_three(self):
        exporter = load_exporter()
        self.assertEqual(exporter.normalize_confluence_depth_limit(0), 3)
        self.assertEqual(exporter.normalize_confluence_depth_limit(None), 3)
        self.assertEqual(exporter.normalize_confluence_depth_limit(5), 5)

    def test_repair_export_state_depth_limits_syncs_from_progress(self):
        exporter = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            metadata_dir = Path(tmp)
            progress_dir = metadata_dir / "progress"
            progress_dir.mkdir(parents=True)
            (progress_dir / "638576143.json").write_text(
                json.dumps({"root_page_id": "638576143", "depth_limit": 3, "pages": {}, "queue": [], "enqueued": []}),
                encoding="utf-8",
            )
            (metadata_dir / "export-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "roots": [
                            {
                                "page_id": "638576143",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=638576143",
                                "site_base": "https://cwiki.guazi.com",
                                "depth_limit": 0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertTrue(exporter.repair_export_state_depth_limits(metadata_dir))
            payload = json.loads((metadata_dir / "export-state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["roots"][0]["depth_limit"], 3)


if __name__ == "__main__":
    unittest.main()
