import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "update_installed_skill.py"


def load_updater():
    spec = importlib.util.spec_from_file_location("update_installed_skill", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UpdateInstalledSkillTest(unittest.TestCase):
    def test_successful_update_suggests_maintain_all(self):
        updater = load_updater()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            stdout = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--source", str(bundle), "--no-pull"]
                with mock.patch.object(updater, "resolve_bundle_root", return_value=bundle), mock.patch.object(
                    updater, "run", return_value=0
                ), mock.patch.object(
                    updater, "update_prd_review_max", return_value=0
                ) as prd_update, contextlib.redirect_stdout(stdout):
                    self.assertEqual(updater.main(), 0)
            finally:
                sys.argv = original_argv

        output = stdout.getvalue()
        self.assertIn("maintain-all", output)
        self.assertIn("Existing KB projects keep their project-local tools", output)
        self.assertIn("prd-review-max was refreshed", output)
        prd_update.assert_called_once()

    def test_skip_prd_review_max(self):
        updater = load_updater()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--source", str(bundle), "--no-pull", "--skip-prd-review-max"]
                with mock.patch.object(updater, "resolve_bundle_root", return_value=bundle), mock.patch.object(
                    updater, "run", return_value=0
                ), mock.patch.object(
                    updater, "update_prd_review_max", return_value=0
                ) as prd_update:
                    self.assertEqual(updater.main(), 0)
            finally:
                sys.argv = original_argv

        prd_update.assert_not_called()

    def test_gitlab_clone_retries_with_local_token_after_system_git_fails(self):
        updater = load_updater()
        calls = []

        def fake_call(command, cwd, env=None):
            calls.append((command, env))
            return 128 if env is None else 0

        with mock.patch.object(updater, "call", side_effect=fake_call), mock.patch.object(
            updater, "gitlab_token", return_value="token-123"
        ):
            code = updater.run(
                ["git", "clone", "https://git.guazi-corp.com/c2b-fe/llm-wiki.git", "/tmp/llm-wiki"],
                Path("/tmp"),
            )

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(calls[0][1])
        self.assertEqual(calls[1][1]["GUAZI_GITLAB_TOKEN"], "token-123")
        self.assertIn("GIT_ASKPASS", calls[1][1])

    def test_gitlab_clone_does_not_retry_without_token(self):
        updater = load_updater()
        calls = []

        def fake_call(command, cwd, env=None):
            calls.append((command, env))
            return 128

        with mock.patch.object(updater, "call", side_effect=fake_call), mock.patch.object(updater, "gitlab_token", return_value=""):
            code = updater.run(
                ["git", "clone", "https://git.guazi-corp.com/c2b-fe/llm-wiki.git", "/tmp/llm-wiki"],
                Path("/tmp"),
            )

        self.assertEqual(code, 128)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
