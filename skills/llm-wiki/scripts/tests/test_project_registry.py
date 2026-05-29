import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def load_script_module(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProjectRegistryTest(unittest.TestCase):
    def test_register_project_is_idempotent_and_preserves_first_seen(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "demo-kb"
            kb.mkdir()
            (kb / "kb.manifest.yaml").write_text("version: 1\n", encoding="utf-8")
            tools = kb / "tools"
            tools.mkdir()
            (tools / "update_wiki.py").write_text("# update\n", encoding="utf-8")
            registry_path = root / "projects.json"

            first = registry.register_project(
                kb,
                registry_path=registry_path,
                now="2026-05-29T01:00:00+00:00",
            )
            second = registry.register_project(
                kb,
                registry_path=registry_path,
                now="2026-05-29T02:00:00+00:00",
            )

            self.assertEqual(first["path"], str(kb.resolve()))
            self.assertEqual(second["first_seen_at"], "2026-05-29T01:00:00+00:00")
            self.assertEqual(second["last_seen_at"], "2026-05-29T02:00:00+00:00")
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["status"], "active")
            self.assertEqual(payload["projects"][0]["missing_count"], 0)


if __name__ == "__main__":
    unittest.main()
