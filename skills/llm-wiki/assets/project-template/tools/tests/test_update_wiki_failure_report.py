import importlib.util
import json
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_update_wiki():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("update_wiki", TOOLS_DIR / "update_wiki.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UpdateFailureReportTest(unittest.TestCase):
    def test_failure_report_replaces_previous_success_report(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            report_dir = project / "staging" / "update"
            report_dir.mkdir(parents=True)
            (report_dir / "latest.json").write_text('{"status":"old-success"}\n', encoding="utf-8")

            update_wiki.write_failure_report(
                project,
                failed_step="health",
                returncode=1,
                details={
                    "status": "fail",
                    "stale_sources": 241,
                    "orphan_source_pages": 242,
                    "broken_wikilinks": 0,
                },
            )

            latest = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["status"], "failed")
            self.assertEqual(latest["failed_step"], "health")
            self.assertEqual(latest["details"]["stale_sources"], 241)
            self.assertIn("health", (report_dir / "latest.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
