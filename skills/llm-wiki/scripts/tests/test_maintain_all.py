import importlib.util
import json
import os
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


def write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


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

    def test_run_apply_runs_each_project_writes_reports_and_updates_registry(self):
        maintain_all = load_script_module("maintain_all")
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_root = root / "skill"
            install_log = root / "install.log"
            write_executable(
                skill_root / "scripts" / "install_project_template.py",
                "import os, pathlib, sys\n"
                f"pathlib.Path({str(install_log)!r}).open('a').write(sys.argv[sys.argv.index('--project') + 1] + '\\n')\n",
            )

            success = make_kb(root / "success")
            failing = make_kb(root / "failing")
            write_executable(
                success / "tools" / "backfill.py",
                "import json, pathlib\n"
                "pathlib.Path('staging/backfill').mkdir(parents=True, exist_ok=True)\n"
                "pathlib.Path('backfill-ran').write_text('yes')\n"
                "pathlib.Path('staging/backfill/latest.json').write_text(json.dumps({'refinement_absorption_required': True}))\n",
            )
            write_executable(
                success / "tools" / "update_wiki.py",
                "import pathlib\n"
                "pathlib.Path('staging/update').mkdir(parents=True, exist_ok=True)\n"
                "pathlib.Path('update-ran').write_text('yes')\n"
                "pathlib.Path('staging/update/latest.json').write_text('{}')\n",
            )
            write_executable(
                failing / "tools" / "backfill.py",
                "import sys\n"
                "print('backfill failed')\n"
                "raise SystemExit(7)\n",
            )
            write_executable(failing / "tools" / "update_wiki.py", "raise SystemExit(0)\n")

            registry_path = root / "projects.json"
            for kb in (failing, success):
                registry.register_project(kb, registry_path=registry_path, now="2026-05-29T01:00:00+00:00")
            plan = {
                "planned": [
                    {"project": str(failing), "status": "planned"},
                    {"project": str(success), "status": "planned"},
                ],
                "skipped": [],
                "removed": [],
            }
            old_skill_root = maintain_all.SKILL_ROOT
            maintain_all.SKILL_ROOT = skill_root
            try:
                summary = maintain_all.run_apply(
                    plan,
                    registry_path=registry_path,
                    runs_dir=root / "maintenance-runs",
                    now="2026-05-29T02:00:00+00:00",
                )
            finally:
                maintain_all.SKILL_ROOT = old_skill_root

            self.assertTrue((success / "backfill-ran").is_file())
            self.assertTrue((success / "update-ran").is_file())
            self.assertEqual([item["status"] for item in summary["results"]], ["failed", "success"])
            self.assertTrue(Path(summary["json_report"]).is_file())
            self.assertTrue(Path(summary["markdown_report"]).is_file())
            report = json.loads(Path(summary["json_report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["successes"], 1)
            self.assertEqual(report["failures"], 1)
            payload = registry.load_registry(registry_path)
            by_path = {item["path"]: item for item in payload["projects"]}
            self.assertEqual(by_path[str(success.resolve())]["last_success_at"], "2026-05-29T02:00:00+00:00")
            self.assertEqual(by_path[str(success.resolve())]["status"], "active")
            self.assertEqual(by_path[str(failing.resolve())]["status"], "failed")
            self.assertEqual(by_path[str(failing.resolve())]["last_error"], "backfill")
            self.assertIn(str(success), install_log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
