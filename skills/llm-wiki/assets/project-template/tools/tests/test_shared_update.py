import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_shared_update():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("shared_update", TOOLS_DIR / "shared_update.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def make_repo_with_remote(root: Path) -> tuple[Path, Path]:
    remote = root / "remote.git"
    project = root / "kb"
    git(root, "init", "--bare", str(remote))
    git(root, "clone", str(remote), str(project))
    git(project, "checkout", "-b", "main")
    git(project, "config", "user.name", "Codex")
    git(project, "config", "user.email", "codex@example.com")
    (project / ".gitignore").write_text("raw/\nraw-code/\n", encoding="utf-8")
    (project / "wiki").mkdir()
    (project / "wiki" / "page.md").write_text("# page\n", encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-m", "baseline")
    git(project, "push", "-u", "origin", "main")
    return project, remote


class SharedUpdateTests(unittest.TestCase):
    def test_classifies_read_and_write_permission_errors(self):
        shared = load_shared_update()
        self.assertEqual(shared.classify_git_permission("Permission denied (publickey)", "pull"), "read_permission")
        self.assertEqual(shared.classify_git_permission("remote: You are not allowed", "push"), "write_permission")
        self.assertEqual(shared.classify_git_permission("fatal: not possible to fast-forward", "pull"), "none")

    def test_evidence_cache_hygiene_requires_raw_ignored(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")

            result = shared.check_evidence_cache_hygiene(project)

            self.assertEqual(result.status, "evidence_cache_ignore_failed")
            self.assertIn("raw/", result.message)
            self.assertIn("gitignore", result.message.lower())

    def test_evidence_cache_hygiene_rejects_tracked_raw(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            git(project, "config", "user.name", "Codex")
            git(project, "config", "user.email", "codex@example.com")
            (project / ".gitignore").write_text("raw/\nraw-code/\n", encoding="utf-8")
            (project / "raw").mkdir()
            (project / "raw" / "page.md").write_text("# page\n", encoding="utf-8")
            git(project, "add", "-f", "raw/page.md")
            git(project, "commit", "-m", "track raw")

            result = shared.check_evidence_cache_hygiene(project)

            self.assertEqual(result.status, "evidence_cache_tracked_failed")
            self.assertIn("raw/page.md", result.message)

    def test_evidence_cache_hygiene_checks_raw_code_when_declared(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            (project / ".gitignore").write_text("raw/\n", encoding="utf-8")
            (project / "upstream").mkdir()
            (project / "upstream" / "code-sources.json").write_text('{"version":1,"sources":[]}\n', encoding="utf-8")

            result = shared.check_evidence_cache_hygiene(project)

            self.assertEqual(result.status, "evidence_cache_ignore_failed")
            self.assertIn("raw-code/", result.message)

    def test_evidence_cache_hygiene_checks_raw_code_when_wiki_code_exists(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            (project / ".gitignore").write_text("raw/\n", encoding="utf-8")
            (project / "wiki" / "code" / "modules").mkdir(parents=True)

            result = shared.check_evidence_cache_hygiene(project)

            self.assertEqual(result.status, "evidence_cache_ignore_failed")
            self.assertIn("raw-code/", result.message)

    def test_classifies_allowed_and_excluded_paths(self):
        shared = load_shared_update()
        self.assertTrue(shared.is_publish_allowed("wiki/sources/demo.md"))
        self.assertTrue(shared.is_publish_allowed("BUSINESS_CONTEXT.md"))
        self.assertTrue(shared.is_publish_allowed("docs/retrieval-playbook.md"))
        self.assertTrue(shared.is_publish_allowed("docs/team-quality-audit.md"))
        self.assertTrue(shared.is_publish_allowed("staging/update/latest.json"))
        self.assertTrue(shared.is_publish_allowed("wiki/key-concepts.md"))
        self.assertFalse(shared.is_publish_allowed("raw/page/index.md"))
        self.assertFalse(shared.is_publish_allowed("docs/random.md"))
        self.assertFalse(shared.is_publish_allowed("staging/random.md"))
        self.assertFalse(shared.is_publish_allowed("config/api-token.json"))
        self.assertFalse(shared.is_publish_allowed("root-token.txt"))
        self.assertFalse(shared.is_publish_allowed("wiki/secrets/config.md"))
        self.assertFalse(shared.is_publish_allowed("certs/client.p12"))

    def test_parse_porcelain_z_handles_rename_paths(self):
        shared = load_shared_update()
        for data in [
            b"R  wiki/old.md\0wiki/new.md\0",
            b" R wiki/old.md\0wiki/new.md\0",
            b"C  wiki/source.md\0wiki/copy.md\0",
            b" C wiki/source.md\0wiki/copy.md\0",
        ]:
            with self.subTest(data=data):
                changes = shared.parse_porcelain_z(data)
                self.assertEqual(changes[0].paths, ("wiki/old.md", "wiki/new.md") if b"old" in data else ("wiki/source.md", "wiki/copy.md"))

    def test_publish_decision_blocks_mixed_allowed_and_unexpected_paths(self):
        shared = load_shared_update()
        decision = shared.decide_publish_paths(
            [
                shared.GitChange(" M", ("wiki/source.md",)),
                shared.GitChange("??", ("notes.md",)),
            ]
        )
        self.assertEqual(decision.status, "unexpected_local_changes")
        self.assertIn("notes.md", decision.message)


if __name__ == "__main__":
    unittest.main()
