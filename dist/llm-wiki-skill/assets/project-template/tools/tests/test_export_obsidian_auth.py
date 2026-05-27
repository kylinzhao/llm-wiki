import importlib.util
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
import tempfile


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS_DIR / "confluence_sync" / "export_obsidian_wiki.py"


def load_export_obsidian():
    spec = importlib.util.spec_from_file_location("export_obsidian_wiki", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportObsidianAuthTest(unittest.TestCase):
    def test_interactive_missing_cookie_prompts_for_sso_credentials(self):
        export_obsidian = load_export_obsidian()
        args = export_obsidian.parse_args(
            ["--update", "--project-dir", "/tmp/kb"]
        )
        class InteractiveStderr(io.StringIO):
            def isatty(self):
                return True

        stderr = InteractiveStderr()

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(export_obsidian, "AUTH_ENV_FILE", Path(tmp) / "guazi-sso.env"), mock.patch.object(export_obsidian, "discover_sso_skill_root", return_value="/tmp/guazi-sso-login"), mock.patch.object(sys.stdin, "isatty", return_value=True), mock.patch(
            "builtins.input", side_effect=["sso", "zhangsan", "13800138000"]
        ), mock.patch(
            "getpass.getpass", side_effect=["secret-password", "jira-token-123"]
        ), mock.patch.object(sys, "stderr", stderr):
            env_updates = export_obsidian.maybe_prompt_for_auth(args)

        self.assertTrue(args.auto_cookie_from_sso)
        self.assertEqual(env_updates["GUAZI_SSO_USER_NAME"], "zhangsan")
        self.assertEqual(env_updates["GUAZI_SSO_PASSWORD"], "secret-password")
        self.assertEqual(env_updates["GUAZI_SSO_APPLY_PHONE"], "13800138000")
        self.assertEqual(env_updates["GUAZI_SSO_SKILL_ROOT"], "/tmp/guazi-sso-login")
        self.assertEqual(env_updates["JIRA_TOKEN"], "jira-token-123")
        self.assertEqual(args.jira_token, "jira-token-123")
        self.assertIn("does not upload your username", stderr.getvalue())
        self.assertIn("agent chat window", stderr.getvalue())
        self.assertIn("bash tools/confluence_sync/init_auth_env.sh", stderr.getvalue())
        self.assertNotIn("GUAZI_SSO_SKILL_ROOT", stderr.getvalue())
        self.assertNotIn("/path/to/guazi-sso-login", stderr.getvalue())

    def test_vendored_sso_login_is_discovered_by_default(self):
        export_obsidian = load_export_obsidian()

        root = Path(export_obsidian.discover_sso_skill_root({}))

        self.assertEqual(root.name, "guazi-sso-login")
        self.assertTrue((root / "run.sh").is_file())

    def test_interactive_sso_credentials_block_when_login_tool_is_missing(self):
        export_obsidian = load_export_obsidian()
        args = export_obsidian.parse_args(["--update", "--project-dir", "/tmp/kb"])

        class InteractiveStderr(io.StringIO):
            def isatty(self):
                return True

        stderr = InteractiveStderr()

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(export_obsidian, "AUTH_ENV_FILE", Path(tmp) / "guazi-sso.env"), mock.patch.object(export_obsidian, "discover_sso_skill_root", return_value=""), mock.patch.object(sys.stdin, "isatty", return_value=True), mock.patch(
            "builtins.input", side_effect=["sso", "zhangsan"]
        ), mock.patch.object(sys, "stderr", stderr):
            env_updates = export_obsidian.maybe_prompt_for_auth(args)

        self.assertEqual(env_updates, {})
        self.assertIn("llm-wiki 安装不完整", stderr.getvalue())

    def test_sso_password_and_jira_token_are_not_added_to_command_arguments(self):
        export_obsidian = load_export_obsidian()
        args = export_obsidian.parse_args(
            ["--update", "--project-dir", "/tmp/kb", "--sso-skill-root", "/tmp/guazi-sso-login", "--jira-token", "jira-token-123"]
        )
        args.auto_cookie_from_sso = True
        command = export_obsidian.build_command(args)

        self.assertIn("--auto-cookie-from-sso", command)
        self.assertNotIn("secret-password", command)
        self.assertNotIn("--jira-token", command)
        self.assertNotIn("jira-token-123", command)

    def test_auth_env_file_persists_sso_credentials_for_future_runs(self):
        export_obsidian = load_export_obsidian()
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "guazi-sso.env"
            export_obsidian.write_auth_env_file(
                env_file,
                {
                    "GUAZI_SSO_SKILL_ROOT": "/tmp/guazi-sso-login",
                    "GUAZI_SSO_USER_NAME": "zhangsan",
                    "GUAZI_SSO_PASSWORD": "secret-password",
                    "GUAZI_SSO_APPLY_PHONE": "13800138000",
                    "JIRA_TOKEN": "jira-token-123",
                },
            )

            loaded = export_obsidian.load_auth_env_file(env_file)

        self.assertEqual(loaded["GUAZI_SSO_USER_NAME"], "zhangsan")
        self.assertEqual(loaded["GUAZI_SSO_PASSWORD"], "secret-password")
        self.assertEqual(loaded["GUAZI_SSO_APPLY_PHONE"], "13800138000")
        self.assertEqual(loaded["GUAZI_SSO_SKILL_ROOT"], "/tmp/guazi-sso-login")
        self.assertEqual(loaded["JIRA_TOKEN"], "jira-token-123")

    def test_auth_env_file_applies_jira_token_default(self):
        export_obsidian = load_export_obsidian()
        with mock.patch.dict(os.environ, {}, clear=True):
            args = export_obsidian.parse_args(["--update", "--project-dir", "/tmp/kb"])
        env = {
            "GUAZI_SSO_SKILL_ROOT": "/tmp/guazi-sso-login",
            "GUAZI_SSO_USER_NAME": "zhangsan",
            "GUAZI_SSO_PASSWORD": "secret-password",
            "GUAZI_SSO_APPLY_PHONE": "13800138000",
            "JIRA_TOKEN": "jira-token-123",
        }

        export_obsidian.apply_auth_env_defaults(args, env)

        self.assertTrue(args.auto_cookie_from_sso)
        self.assertEqual(args.jira_token, "jira-token-123")


if __name__ == "__main__":
    unittest.main()
