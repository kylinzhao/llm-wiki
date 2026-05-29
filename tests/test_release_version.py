import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_version.py"


def load_release_version():
    spec = importlib.util.spec_from_file_location("release_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleaseVersionTest(unittest.TestCase):
    def test_updates_version_manifest_and_release_notes(self):
        release_version = load_release_version()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "repo"
            shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"))

            release_version.update_release(
                project,
                version="9.9.9",
                engine_version="engine-v9.9.9",
                note="测试发布说明。",
            )

            for rel in ["skills/llm-wiki/VERSION", "dist/llm-wiki-skill/VERSION"]:
                text = (project / rel).read_text(encoding="utf-8")
                self.assertIn("version: 9.9.9", text)
                self.assertIn("engine_version: engine-v9.9.9", text)

            manifest = json.loads((project / "dist/llm-wiki-skill/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "9.9.9")

            for rel in ["README.md", "skills/llm-wiki/README.md", "dist/llm-wiki-skill/README.md"]:
                text = (project / rel).read_text(encoding="utf-8")
                self.assertIn("engine-v9.9.9", text)
                self.assertIn("测试发布说明。", text)


if __name__ == "__main__":
    unittest.main()
