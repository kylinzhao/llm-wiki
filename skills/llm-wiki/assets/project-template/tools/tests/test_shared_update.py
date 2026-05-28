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


if __name__ == "__main__":
    unittest.main()
