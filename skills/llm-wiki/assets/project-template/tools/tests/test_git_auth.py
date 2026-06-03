import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_git_auth():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("git_auth", TOOLS_DIR / "git_auth.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GitAuthTest(unittest.TestCase):
    def test_reads_gitlab_token_from_auth_env_file(self):
        auth = load_git_auth()
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "guazi-sso.env"
            env_file.write_text("GUAZI_GITLAB_TOKEN='token with spaces'\n", encoding="utf-8")
            with mock.patch.object(auth, "AUTH_ENV_FILE", env_file), mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "")}, clear=True):
                self.assertEqual(auth.gitlab_token(), "token with spaces")

    def test_retries_https_gitlab_command_with_askpass_token(self):
        auth = load_git_auth()
        calls = []

        def fake_run(args, cwd, env=None):
            calls.append(env)
            if env is None:
                return auth.GitCommandResult(128, "", "Authentication failed")
            return auth.GitCommandResult(0, "ok\n", "")

        with mock.patch.object(auth, "_run_git", side_effect=fake_run), mock.patch.object(auth, "gitlab_token", return_value="token-123"):
            result = auth.run_git(["ls-remote", "https://git.guazi-corp.com/c2b-fe/llm-wiki.git"])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertIsNone(calls[0])
        self.assertEqual(calls[1]["GUAZI_GITLAB_TOKEN"], "token-123")

    def test_does_not_retry_non_gitlab_urls(self):
        auth = load_git_auth()
        calls = []

        def fake_run(args, cwd, env=None):
            calls.append(env)
            return auth.GitCommandResult(128, "", "Authentication failed")

        with mock.patch.object(auth, "_run_git", side_effect=fake_run), mock.patch.object(auth, "gitlab_token", return_value="token-123"):
            result = auth.run_git(["ls-remote", "https://example.com/repo.git"])

        self.assertEqual(result.returncode, 128)
        self.assertEqual(calls, [None])


if __name__ == "__main__":
    unittest.main()
