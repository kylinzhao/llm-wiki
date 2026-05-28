import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_migration():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("migrate_raw_publish_mode", TOOLS_DIR / "migrate_raw_publish_mode.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RawPublishMigrationTest(unittest.TestCase):
    def test_check_reports_raw_ignored_and_legacy_metadata_dir(self):
        migration = load_migration()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".gitignore").write_text("raw/\n.DS_Store\n", encoding="utf-8")
            (project / "kb.manifest.yaml").write_text("evidence:\n  raw_code: false\n", encoding="utf-8")
            (project / "raw" / "123-page").mkdir(parents=True)
            (project / "raw" / "123-page" / "index.md").write_text("# Source\n", encoding="utf-8")
            (project / "upstream").mkdir()
            (project / "upstream" / "wiki-sources.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {
                                "type": "confluence",
                                "page_id": "123",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=123",
                                "metadata_dir": "staging/wiki-export",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = migration.check_project(project)

            self.assertIn("raw_ignored", report["warnings"])
            self.assertIn("legacy_wiki_export_metadata_dir", report["warnings"])

    def test_apply_rewrites_gitignore_manifest_sources_and_copies_state(self):
        migration = load_migration()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".gitignore").write_text("raw/\ncustom-cache/\n", encoding="utf-8")
            (project / "kb.manifest.yaml").write_text("evidence:\n  raw_code: true\n", encoding="utf-8")
            (project / "raw" / "123-page").mkdir(parents=True)
            (project / "raw" / "123-page" / "index.md").write_text("# Source\n", encoding="utf-8")
            (project / "upstream").mkdir()
            (project / "upstream" / "wiki-sources.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {
                                "type": "confluence",
                                "page_id": "123",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=123",
                                "depth": 2,
                                "metadata_dir": "staging/wiki-export",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            legacy = project / "staging" / "wiki-export"
            (legacy / "progress").mkdir(parents=True)
            (legacy / "export-state.json").write_text('{"version":1,"roots":[]}\n', encoding="utf-8")
            (legacy / "progress" / "123.json").write_text('{"root_page_id":"123","depth_limit":2}\n', encoding="utf-8")

            report = migration.apply_project(project, allow_dirty=True)

            gitignore = (project / ".gitignore").read_text(encoding="utf-8")
            self.assertNotIn("raw/\n", gitignore)
            self.assertIn("raw/progress/", gitignore)
            self.assertIn("custom-cache/", gitignore)
            manifest = (project / "kb.manifest.yaml").read_text(encoding="utf-8")
            self.assertIn("raw: true", manifest)
            self.assertIn("raw_code: true", manifest)
            sources = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))["sources"]
            self.assertEqual(sources[0]["metadata_dir"], "staging/wiki-export-state")
            self.assertTrue((project / "staging" / "wiki-export-state" / "export-state.json").is_file())
            self.assertTrue((project / "staging" / "wiki-export-state" / "progress" / "123.json").is_file())
            self.assertEqual(report["status"], "applied")
