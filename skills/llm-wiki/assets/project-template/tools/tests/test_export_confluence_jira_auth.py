import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py"


def load_export_confluence_tree():
    spec = importlib.util.spec_from_file_location("export_confluence_tree", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["export_confluence_tree"] = module
    spec.loader.exec_module(module)
    return module


class ExportConfluenceJiraAuthTest(unittest.TestCase):
    def test_jira_chdsso_is_not_auto_resolved_unless_enabled(self):
        export_confluence = load_export_confluence_tree()

        with mock.patch.object(export_confluence, "run_guazi_sso_skill") as run_sso:
            token = export_confluence.resolve_jira_chdsso(
                "",
                sso_skill_root="/tmp/guazi-sso-login",
                auto_jira_chdsso_from_sso=False,
                jira_chdsso_env="test",
            )

        self.assertEqual(token, "")
        run_sso.assert_not_called()

    def test_jira_chdsso_auto_resolves_when_enabled(self):
        export_confluence = load_export_confluence_tree()

        with mock.patch.object(export_confluence, "run_guazi_sso_skill", return_value="chdsso-token") as run_sso:
            token = export_confluence.resolve_jira_chdsso(
                "",
                sso_skill_root="/tmp/guazi-sso-login",
                auto_jira_chdsso_from_sso=True,
                jira_chdsso_env="test",
            )

        self.assertEqual(token, "chdsso-token")
        run_sso.assert_called_once()


if __name__ == "__main__":
    unittest.main()
