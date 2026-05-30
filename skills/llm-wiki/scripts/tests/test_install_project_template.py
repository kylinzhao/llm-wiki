import importlib.util
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "install_project_template.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("install_project_template", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InstallProjectTemplateTest(unittest.TestCase):
    def test_main_registers_project_in_local_registry(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            registry_path = root / "projects.json"
            stdout = io.StringIO()
            original_argv = sys.argv
            old_registry = os.environ.get("LLM_WIKI_PROJECT_REGISTRY")
            try:
                os.environ["LLM_WIKI_PROJECT_REGISTRY"] = str(registry_path)
                sys.argv = [str(SCRIPT), "--project", str(project)]
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(installer.main(), 0)
            finally:
                sys.argv = original_argv
                if old_registry is None:
                    os.environ.pop("LLM_WIKI_PROJECT_REGISTRY", None)
                else:
                    os.environ["LLM_WIKI_PROJECT_REGISTRY"] = old_registry

            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["projects"][0]["path"], str(project.resolve()))
            self.assertIn("registry=registered", stdout.getvalue())

    def test_engine_only_overwrites_engine_owned_files_without_force(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            tool = project / "tools" / "update_wiki.py"
            raw = project / "raw" / "evidence.md"
            wiki = project / "wiki" / "manual.md"
            tool.parent.mkdir(parents=True)
            raw.parent.mkdir(parents=True)
            wiki.parent.mkdir(parents=True)
            tool.write_text("old tool\n", encoding="utf-8")
            raw.write_text("raw evidence\n", encoding="utf-8")
            wiki.write_text("manual wiki\n", encoding="utf-8")

            copied, skipped = installer.copy_tree(installer.TEMPLATE_ROOT, project, force=False, engine_only=True)

            self.assertIn("tools/update_wiki.py", copied)
            self.assertNotIn("tools/update_wiki.py", skipped)
            self.assertNotEqual(tool.read_text(encoding="utf-8"), "old tool\n")
            self.assertEqual(raw.read_text(encoding="utf-8"), "raw evidence\n")
            self.assertEqual(wiki.read_text(encoding="utf-8"), "manual wiki\n")

    def test_refresh_agent_rules_replaces_legacy_cookie_auth_section(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir(parents=True)
            agents = project / "AGENTS.md"
            agents.write_text(
                "# Rules\n\n"
                "## Cwiki 原始文档同步\n\n"
                "在已登录 cwiki 的浏览器中复制 Cookie 请求头后：\n\n"
                "```bash\nexport COOKIE_HEADER='...'\n./scripts/import_cwiki_raw.sh\n```\n\n"
                "## Other\n\nKeep this.\n",
                encoding="utf-8",
            )

            status = installer.refresh_agent_rules(project)
            text = agents.read_text(encoding="utf-8")

        self.assertEqual(status, "updated")
        self.assertIn("## Cwiki Authentication", text)
        self.assertIn("bash tools/confluence_sync/init_auth_env.sh", text)
        self.assertIn("JIRA_TOKEN", text)
        self.assertNotIn("directory containing run.sh", text)
        self.assertNotIn("read -r -p", text)
        self.assertIn("## Other", text)
        self.assertNotIn("export COOKIE_HEADER='...'", text)
        self.assertNotIn("import_cwiki_raw.sh", text)

    def test_project_template_installs_auth_init_script(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            stdout = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--project", str(project)]
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(installer.main(), 0)
            finally:
                sys.argv = original_argv

            script = project / "tools" / "confluence_sync" / "init_auth_env.sh"
            text = script.read_text(encoding="utf-8")
            self.assertTrue(script.is_file())
            self.assertIn("#!/usr/bin/env bash", text)
            self.assertIn("GUAZI_SSO_USER_NAME", text)
            self.assertIn("COOKIE_HEADER", text)
            self.assertIn("Choose auth mode", text)
            self.assertIn(".llm-wiki/guazi-sso.env", text)

    def test_skill_level_auth_init_script_supports_cookie_mode(self):
        script = Path(__file__).resolve().parents[1] / "init_auth_env.sh"
        text = script.read_text(encoding="utf-8")

        self.assertIn("GUAZI_SSO_USER_NAME", text)
        self.assertIn("COOKIE_HEADER", text)
        self.assertIn("Choose auth mode", text)
        self.assertIn(".llm-wiki/guazi-sso.env", text)

    def test_project_template_ignores_evidence_caches(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            stdout = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--project", str(project)]
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(installer.main(), 0)
            finally:
                sys.argv = original_argv

            gitignore = (project / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("raw/\n", gitignore)
            self.assertIn("raw-code/\n", gitignore)
            self.assertIn("uv.lock\n", gitignore)

    def test_main_recommends_llm_wiki_commands_not_internal_script_chain(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            stdout = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--project", str(project)]
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(installer.main(), 0)
            finally:
                sys.argv = original_argv

        output = stdout.getvalue()
        self.assertIn("llm-wiki update", output)
        self.assertIn("llm-wiki image", output)
        self.assertNotIn("uv run python tools/health.py --json", output)
        self.assertNotIn("uv run python tools/build_graph.py", output)


if __name__ == "__main__":
    unittest.main()
