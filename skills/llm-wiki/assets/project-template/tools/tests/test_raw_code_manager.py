import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_raw_code_manager():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("raw_code_manager", TOOLS_DIR / "raw_code_manager.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class ManagedRawCodeTests(unittest.TestCase):
    def test_add_managed_codebase_clones_repo_and_writes_metadata(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Codex")
            git(source, "config", "user.email", "codex@example.com")
            (source / "README.md").write_text("# demo\n", encoding="utf-8")
            git(source, "add", "README.md")
            git(source, "commit", "-m", "init")

            project = root / "kb"
            project.mkdir()

            result = manager.add_managed_codebase(project, str(source))

            managed = project / "raw-code" / "source-repo"
            self.assertEqual(result["codebase_id"], "source-repo")
            self.assertTrue((managed / ".git").exists())
            metadata = (managed / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
            self.assertIn("managed: true", metadata)
            self.assertIn("codebase_id: source-repo", metadata)
            self.assertIn("created_by: llm-wiki-add-code", metadata)

    def test_permission_failure_does_not_create_target(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "kb"
            project.mkdir()

            with mock.patch.object(manager, "probe_repo_access", return_value=(False, "missing_access")):
                with self.assertRaises(manager.RawCodeManagerError) as ctx:
                    manager.add_managed_codebase(project, "git@example.com:private/repo.git")

            self.assertEqual(ctx.exception.code, "missing_access")
            self.assertFalse((project / "raw-code" / "repo").exists())

    def test_dirty_existing_target_is_rejected(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Codex")
            git(source, "config", "user.email", "codex@example.com")
            (source / "README.md").write_text("# demo\n", encoding="utf-8")
            git(source, "add", "README.md")
            git(source, "commit", "-m", "init")

            project = root / "kb"
            target = project / "raw-code" / "source-repo"
            target.mkdir(parents=True)
            (target / "local.txt").write_text("dirty\n", encoding="utf-8")

            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.add_managed_codebase(project, str(source))

            self.assertEqual(ctx.exception.code, "dirty_target")

    def test_metadata_writer_records_required_fields(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "raw-code" / "demo"
            managed.mkdir(parents=True)

            manager.write_codebase_metadata(
                managed,
                {
                    "codebase_id": "demo",
                    "repo_url": "/tmp/demo.git",
                    "origin_ref": "main",
                    "default_branch": "main",
                    "managed_path": str(managed),
                },
            )

            content = (managed / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
            self.assertIn("codebase_id: demo", content)
            self.assertIn("repo_url: /tmp/demo.git", content)
            self.assertIn("origin_ref: main", content)
            self.assertIn("default_branch: main", content)
            self.assertIn("managed: true", content)


if __name__ == "__main__":
    unittest.main()
