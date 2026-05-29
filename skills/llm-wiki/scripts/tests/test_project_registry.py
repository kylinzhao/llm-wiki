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

    def test_discover_projects_finds_strong_and_legacy_kbs_without_descending_generated_dirs(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strong = root / "strong-kb"
            (strong / "tools").mkdir(parents=True)
            (strong / "kb.manifest.yaml").write_text("version: 1\n", encoding="utf-8")
            (strong / "tools" / "update_wiki.py").write_text("# update\n", encoding="utf-8")

            legacy = root / "nested" / "legacy-kb"
            (legacy / "wiki").mkdir(parents=True)
            (legacy / "staging").mkdir()
            (legacy / "BUSINESS_CONTEXT.md").write_text("# Context\n", encoding="utf-8")

            ignored = root / "raw" / "ignored-kb"
            (ignored / "tools").mkdir(parents=True)
            (ignored / "kb.manifest.yaml").write_text("version: 1\n", encoding="utf-8")
            (ignored / "tools" / "update_wiki.py").write_text("# update\n", encoding="utf-8")

            found = registry.discover_projects(root)

            self.assertEqual(found, sorted([strong.resolve(), legacy.resolve()]))

    def test_reconcile_marks_missing_and_prunes_after_three_missing_runs(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "projects.json"
            missing = root / "missing-kb"
            registry.save_registry(
                {
                    "version": 1,
                    "projects": [
                        {
                            "path": str(missing),
                            "name": "missing-kb",
                            "first_seen_at": "2026-05-29T01:00:00+00:00",
                            "last_seen_at": "2026-05-29T01:00:00+00:00",
                            "last_success_at": "",
                            "status": "active",
                            "missing_count": 0,
                            "last_error": "",
                        }
                    ],
                },
                registry_path,
            )

            first = registry.reconcile_registry(registry_path=registry_path, now="2026-05-29T02:00:00+00:00")
            second = registry.reconcile_registry(registry_path=registry_path, now="2026-05-29T03:00:00+00:00")
            third = registry.reconcile_registry(registry_path=registry_path, now="2026-05-29T04:00:00+00:00")

            self.assertEqual(first["registry"]["projects"][0]["status"], "missing")
            self.assertEqual(first["registry"]["projects"][0]["missing_count"], 1)
            self.assertEqual(second["registry"]["projects"][0]["missing_count"], 2)
            self.assertEqual(third["registry"]["projects"], [])
            self.assertEqual(third["removed"][0]["path"], str(missing))

    def test_prune_missing_removes_missing_paths_immediately(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "projects.json"
            missing = root / "missing-kb"
            registry.save_registry(
                {
                    "version": 1,
                    "projects": [
                        {
                            "path": str(missing),
                            "name": "missing-kb",
                            "status": "missing",
                            "missing_count": 1,
                        }
                    ],
                },
                registry_path,
            )

            removed = registry.prune_missing(registry_path=registry_path)

            self.assertEqual(removed[0]["path"], str(missing))
            self.assertEqual(registry.load_registry(registry_path)["projects"], [])

    def test_registry_rows_returns_stable_display_fields(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "projects.json"
            registry.save_registry(
                {
                    "version": 1,
                    "projects": [
                        {
                            "path": "/tmp/demo",
                            "name": "demo",
                            "status": "failed",
                            "missing_count": 0,
                            "last_success_at": "2026-05-29T01:00:00+00:00",
                            "last_error": "boom",
                        }
                    ],
                },
                registry_path,
            )

            rows = registry.registry_rows(registry_path=registry_path)

            self.assertEqual(
                rows,
                [
                    {
                        "status": "failed",
                        "missing_count": "0",
                        "last_success_at": "2026-05-29T01:00:00+00:00",
                        "path": "/tmp/demo",
                        "last_error": "boom",
                    }
                ],
            )

    def test_git_worktree_dirty_detects_dirty_clean_and_non_git_paths(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

            self.assertFalse(registry.git_worktree_dirty(repo))

            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            self.assertTrue(registry.git_worktree_dirty(repo))
            self.assertFalse(registry.git_worktree_dirty(root / "not-git"))


if __name__ == "__main__":
    unittest.main()
