import importlib.util
import json
import subprocess
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


def make_kb(path: Path) -> Path:
    (path / "tools").mkdir(parents=True)
    (path / "kb.manifest.yaml").write_text("version: 1\n", encoding="utf-8")
    (path / "tools" / "update_wiki.py").write_text("# update\n", encoding="utf-8")
    return path


class MaintainAllTest(unittest.TestCase):
    def test_build_plan_selects_active_projects_and_skips_missing_failed_and_dirty(self):
        maintain_all = load_script_module("maintain_all")
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = make_kb(root / "active")
            dirty = make_kb(root / "dirty")
            subprocess.run(["git", "init"], cwd=dirty, check=True, stdout=subprocess.DEVNULL)
            (dirty / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            missing = root / "missing"
            failed = root / "failed"
            failed.mkdir()
            registry_path = root / "projects.json"
            registry.save_registry(
                {
                    "version": 1,
                    "projects": [
                        {
                            "path": str(active),
                            "name": "active",
                            "status": "active",
                            "missing_count": 0,
                            "last_success_at": "",
                            "last_error": "",
                        },
                        {
                            "path": str(dirty),
                            "name": "dirty",
                            "status": "active",
                            "missing_count": 0,
                            "last_success_at": "",
                            "last_error": "",
                        },
                        {
                            "path": str(missing),
                            "name": "missing",
                            "status": "active",
                            "missing_count": 0,
                            "last_success_at": "",
                            "last_error": "",
                        },
                        {
                            "path": str(failed),
                            "name": "failed",
                            "status": "failed",
                            "missing_count": 0,
                            "last_success_at": "",
                            "last_error": "boom",
                        },
                    ],
                },
                registry_path,
            )

            before = sorted(active.rglob("*"))
            plan = maintain_all.build_plan(registry_path=registry_path)
            after = sorted(active.rglob("*"))

            self.assertEqual(before, after)
            self.assertEqual([item["project"] for item in plan["planned"]], [str(active)])
            skipped = {item["project"]: item["reason"] for item in plan["skipped"]}
            self.assertEqual(skipped[str(dirty)], "dirty_project_worktree")
            self.assertEqual(skipped[str(missing)], "missing")
            self.assertEqual(skipped[str(failed)], "failed")
            self.assertIn("install_project_template.py", plan["planned"][0]["commands"][0])
            self.assertEqual(plan["planned"][0]["commands"][1], "uv run python tools/backfill.py")


if __name__ == "__main__":
    unittest.main()
