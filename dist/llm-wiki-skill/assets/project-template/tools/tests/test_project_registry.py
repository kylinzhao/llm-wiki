import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_project_registry():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("project_registry", TOOLS_DIR / "project_registry.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProjectTemplateRegistryTest(unittest.TestCase):
    def test_register_current_project_is_idempotent(self):
        registry = load_project_registry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "kb"
            kb.mkdir()
            registry_path = root / "projects.json"

            first = registry.register_current_project(
                kb,
                registry_path=registry_path,
                now="2026-05-29T01:00:00+00:00",
            )
            second = registry.register_current_project(
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

    def test_best_effort_register_swallows_write_failures(self):
        registry = load_project_registry()
        with mock.patch.object(registry, "register_current_project", side_effect=OSError("boom")):
            registry.best_effort_register_current_project(Path("/tmp/kb"))


if __name__ == "__main__":
    unittest.main()
