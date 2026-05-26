import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_migrate_raw_code():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("migrate_raw_code", TOOLS_DIR / "migrate_raw_code.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class MigrateLegacyRawCodeTests(unittest.TestCase):
    def test_migrates_local_git_repo_without_metadata(self):
        migrate_raw_code = load_migrate_raw_code()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "legacy-app"
            codebase.mkdir(parents=True)
            git(codebase, "init", "-b", "main")
            git(codebase, "config", "user.name", "Codex")
            git(codebase, "config", "user.email", "codex@example.com")
            (codebase / "README.md").write_text("# legacy\n", encoding="utf-8")
            git(codebase, "add", "README.md")
            git(codebase, "commit", "-m", "init")

            report = migrate_raw_code.migrate_legacy_raw_code(project)

            self.assertEqual(report["converted"], ["legacy-app"])
            self.assertTrue((codebase / ".llm-wiki-codebase.yaml").is_file())

    def test_symlinked_codebase_is_reported_as_blocked(self):
        migrate_raw_code = load_migrate_raw_code()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            external = project / "external-app"
            external.mkdir()
            target = project / "raw-code" / "linked-app"
            target.parent.mkdir(parents=True)
            target.symlink_to(external, target_is_directory=True)

            report = migrate_raw_code.migrate_legacy_raw_code(project)

            self.assertEqual(report["blocked"][0]["codebase_id"], "linked-app")
            self.assertEqual(report["blocked"][0]["reason"], "symlink_requires_manual_readd")

    def test_copied_directory_without_git_identity_is_blocked(self):
        migrate_raw_code = load_migrate_raw_code()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "snapshot-app"
            codebase.mkdir(parents=True)
            (codebase / "README.md").write_text("# copied\n", encoding="utf-8")

            report = migrate_raw_code.migrate_legacy_raw_code(project)

            self.assertEqual(report["blocked"][0]["codebase_id"], "snapshot-app")
            self.assertEqual(report["blocked"][0]["reason"], "missing_repository_identity")


if __name__ == "__main__":
    unittest.main()
