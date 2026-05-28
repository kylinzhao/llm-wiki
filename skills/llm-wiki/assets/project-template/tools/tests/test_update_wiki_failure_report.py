import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_update_wiki():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("update_wiki", TOOLS_DIR / "update_wiki.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@contextlib.contextmanager
def capture_stderr():
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        yield buffer


def make_source_repo_and_kb(extra_branch: str | None = None) -> tuple[Path, Path, Path]:
    root = Path(tempfile.mkdtemp())
    source = root / "source"
    project = root / "kb"
    source.mkdir()
    project.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Codex")
    git(source, "config", "user.email", "codex@example.com")
    (source / "README.md").write_text("# demo\n", encoding="utf-8")
    git(source, "add", "README.md")
    git(source, "commit", "-m", "init")
    if extra_branch:
        git(source, "checkout", "-b", extra_branch)
        (source / "README.md").write_text("# release\n", encoding="utf-8")
        git(source, "commit", "-am", f"prepare {extra_branch}")
        git(source, "checkout", "main")
    return root, source, project


def valid_source(
    repo_url: str,
    codebase_id: str = "demo",
    target_dir: str = "raw-code/demo",
    origin_ref: str = "main",
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "codebase_id": codebase_id,
        "repo_url": repo_url,
        "origin_ref": origin_ref,
        "default_branch": "main",
        "target_dir": target_dir,
        "enabled": enabled,
        "managed": True,
        "sync": {"mode": "ff-only"},
    }


def write_code_sources(
    project: Path,
    repo_url: str | None = None,
    origin_ref: str = "main",
    enabled: bool = True,
    sources: list[dict[str, object]] | None = None,
) -> None:
    payload = {"version": 1, "sources": sources if sources is not None else [valid_source(repo_url or "", origin_ref=origin_ref, enabled=enabled)]}
    path = project / "upstream" / "code-sources.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class UpdateFailureReportTest(unittest.TestCase):
    def test_run_code_sync_blocks_legacy_unmanaged_raw_code_directory(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "legacy-app"
            codebase.mkdir(parents=True)
            (codebase / "README.md").write_text("# legacy\n", encoding="utf-8")

            code = update_wiki.run_code_sync(project)

            self.assertEqual(code, 2)

    def test_run_code_sync_blocks_metadata_without_git_checkout(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "broken-app"
            codebase.mkdir(parents=True)
            (codebase / ".llm-wiki-codebase.yaml").write_text(
                "codebase_id: broken-app\nmanaged: true\nrepo_url: /tmp/broken.git\norigin_ref: main\ndefault_branch: main\nmanaged_path: raw-code/broken-app\ncreated_by: llm-wiki-add-code\n",
                encoding="utf-8",
            )

            code = update_wiki.run_code_sync(project)

            self.assertEqual(code, 2)

    def test_run_code_sync_clones_missing_enabled_source(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        write_code_sources(project, repo_url=str(source), enabled=True)

        code = update_wiki.run_code_sync(project, shared_mode=False)

        self.assertEqual(code, 0)
        metadata = (project / "raw-code" / "demo" / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
        for expected in [
            "codebase_id: demo",
            "repo_url: " + str(source),
            "origin_ref: main",
            "default_branch: main",
            "managed_path: raw-code/demo",
            "managed: true",
            "created_by: llm-wiki-add-code",
        ]:
            self.assertIn(expected, metadata)

    def test_run_code_sync_rejects_local_repo_url_in_shared_mode(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        write_code_sources(project, repo_url=str(source), enabled=True)

        with capture_stderr() as stderr:
            code = update_wiki.run_code_sync(project, shared_mode=True)

        self.assertEqual(code, 2)
        self.assertIn("code_source_config_failed", stderr.getvalue())
        self.assertIn("共享模式不允许使用本机 repo_url", stderr.getvalue())
        self.assertNotIn("是否切换到本机模式", stderr.getvalue())
        self.assertFalse((project / "raw-code" / "demo").exists())

    def test_run_code_sync_validates_all_sources_before_clone(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        write_code_sources(
            project,
            sources=[
                valid_source(repo_url=str(source), codebase_id="first", target_dir="raw-code/first"),
                {**valid_source(repo_url="git@example.com:team/bad.git"), "target_dir": "../bad"},
            ],
        )

        self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 2)
        self.assertFalse((project / "raw-code").exists())

    def test_run_code_sync_clones_origin_ref_branch_not_default_branch(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb(extra_branch="release/1")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        write_code_sources(project, repo_url=str(source), origin_ref="release/1", enabled=True)

        self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 0)
        branch = git(project / "raw-code" / "demo", "branch", "--show-current").stdout.strip()
        upstream = git(project / "raw-code" / "demo", "rev-parse", "--abbrev-ref", "@{u}").stdout.strip()
        self.assertEqual((branch, upstream), ("release/1", "origin/release/1"))

    def test_deterministic_steps_include_cjira_refresh_after_build(self):
        update_wiki = load_update_wiki()
        tools = TOOLS_DIR

        steps = update_wiki.deterministic_steps(tools, graphify=True)

        self.assertEqual(
            [(script.name, extra) for script, extra in steps],
            [
                ("build_wiki.py", []),
                ("cjira_registry.py", ["--refresh"]),
                ("scan_code.py", []),
                ("graphify_code.py", ["--all"]),
                ("build_traceability.py", []),
                ("health.py", ["--json"]),
                ("build_graph.py", []),
                ("anchor_check.py", []),
            ],
        )

    def test_drawio_repair_runs_before_code_sync(self):
        import tempfile
        from unittest import mock

        update_wiki = load_update_wiki()
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            script = project / "tools" / "drawio_repair.py"
            script.parent.mkdir(parents=True)
            script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            with mock.patch.object(update_wiki, "run_python_script", side_effect=lambda path, _project, extra=None: calls.append(path.name) or 0):
                code = update_wiki.run_drawio_repair(project)

        self.assertEqual(code, 0)
        self.assertEqual(calls, ["drawio_repair.py"])

    def test_prepare_raw_evidence_runs_confluence_sync_before_raw_preflight(self):
        import tempfile
        from unittest import mock

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw").mkdir()
            (project / "wiki" / "sources").mkdir(parents=True)
            (project / "wiki" / "sources" / "existing.md").write_text("# Existing\n", encoding="utf-8")

            self.assertIsNotNone(update_wiki.raw_evidence_preflight_failed(project))

            def sync_raw(_project):
                (project / "raw" / "index.md").write_text("# Synced\n", encoding="utf-8")
                return 0

            with mock.patch.object(update_wiki, "run_confluence_sync", side_effect=sync_raw):
                code, failed_step = update_wiki.prepare_raw_evidence(project, "", False)

            self.assertEqual(code, 0)
            self.assertIsNone(failed_step)
            self.assertIsNone(update_wiki.raw_evidence_preflight_failed(project))

    def test_prepare_raw_evidence_keeps_no_sync_preflight_blocker_visible(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw").mkdir()
            (project / "wiki" / "sources").mkdir(parents=True)
            (project / "wiki" / "sources" / "existing.md").write_text("# Existing\n", encoding="utf-8")

            code, failed_step = update_wiki.prepare_raw_evidence(project, "", True)

            self.assertEqual(code, 0)
            self.assertIsNone(failed_step)
            self.assertIn("empty_raw_evidence", update_wiki.raw_evidence_preflight_failed(project) or "")

    def test_failure_report_replaces_previous_success_report(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            report_dir = project / "staging" / "update"
            report_dir.mkdir(parents=True)
            (report_dir / "latest.json").write_text('{"status":"old-success"}\n', encoding="utf-8")

            update_wiki.write_failure_report(
                project,
                failed_step="health",
                returncode=1,
                details={
                    "status": "fail",
                    "stale_sources": 241,
                    "orphan_source_pages": 242,
                    "broken_wikilinks": 0,
                },
            )

            latest = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["status"], "failed")
            self.assertEqual(latest["failed_step"], "health")
            self.assertEqual(latest["details"]["stale_sources"], 241)
            self.assertIn("health", (report_dir / "latest.md").read_text(encoding="utf-8"))

    def test_success_report_replaces_previous_failure_report(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            report_dir = project / "staging" / "update"
            report_dir.mkdir(parents=True)
            (report_dir / "latest.json").write_text('{"status":"failed","failed_step":"confluence_sync"}\n', encoding="utf-8")
            (report_dir / "latest.md").write_text("# old failed report\n", encoding="utf-8")

            update_wiki.write_success_report(project, skipped_steps=["raw_sync"])

            latest = json.loads((report_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["status"], "ok")
            self.assertNotIn("failed_step", latest)
            self.assertEqual(latest["skipped_steps"], ["raw_sync"])
            self.assertIn("Status: `ok`", (report_dir / "latest.md").read_text(encoding="utf-8"))

    def test_rss_sync_enabled_defaults_on_and_respects_false_manifest_flag(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            config = project / "config" / "rss-feeds.yaml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "feeds:\n"
                "  - id: docs\n"
                "    url: https://example.com/feed.xml\n",
                encoding="utf-8",
            )

            self.assertTrue(update_wiki.rss_sync_enabled(project))

            (project / "kb.manifest.yaml").write_text("phases:\n  rss_sync: false\n", encoding="utf-8")
            self.assertFalse(update_wiki.rss_sync_enabled(project))

            (project / "kb.manifest.yaml").write_text("phases:\n  rss_sync: true\n", encoding="utf-8")
            self.assertTrue(update_wiki.rss_sync_enabled(project))

    def test_confluence_upstream_config_migrates_from_export_state(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            state_dir = project / "staging" / "wiki-export"
            state_dir.mkdir(parents=True)
            (state_dir / "export-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "roots": [
                            {
                                "page_id": "638576143",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=638576143",
                                "site_base": "https://cwiki.guazi.com",
                                "depth_limit": 3,
                                "space_key": "ztcpb",
                                "rss_url": "https://cwiki.guazi.com/spaces/createrssfeed.action?x=1",
                                "rss_max_results": 200,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            progress_dir = state_dir / "progress"
            progress_dir.mkdir(parents=True)
            (progress_dir / "638576143.json").write_text(
                json.dumps(
                    {
                        "root_page_id": "638576143",
                        "depth_limit": 3,
                        "pages": {},
                        "queue": [],
                        "enqueued": [],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)
            config = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))

            self.assertEqual(config["sources"][0]["page_id"], "638576143")
            self.assertEqual(config["sources"][0]["depth"], 3)
            self.assertEqual(len(commands), 1)
            self.assertIn("--update", commands[0])
            self.assertIn("--rss-include-new", commands[0])
            self.assertIn("638576143=https://cwiki.guazi.com/spaces/createrssfeed.action?x=1", commands[0])

    def test_confluence_sync_uses_normal_export_when_progress_state_is_missing(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            state_dir = project / "staging" / "wiki-export"
            state_dir.mkdir(parents=True)
            (state_dir / "export-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "roots": [
                            {
                                "page_id": "638576143",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=638576143",
                                "site_base": "https://cwiki.guazi.com",
                                "depth_limit": 3,
                                "space_key": "ztcpb",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)

            self.assertIn("--url", commands[0])
            self.assertNotIn("--update", commands[0])

    def test_rss_upstream_config_migrates_from_legacy_config(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            config = project / "config" / "rss-feeds.yaml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "feeds:\n"
                "  - id: docs\n"
                "    url: https://example.com/feed.xml\n"
                "    source_url: https://example.com/root\n"
                "    target_dir: raw/rss/docs\n"
                "    enabled: true\n"
                "rate_limits:\n"
                "  default_min_interval_seconds: 7\n",
                encoding="utf-8",
            )

            self.assertTrue(update_wiki.rss_sync_enabled(project))
            command = update_wiki.auto_raw_sync_command(project)
            upstream = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))
            generated = (project / "staging" / "update" / "rss-feeds.generated.yaml").read_text(encoding="utf-8")

            self.assertEqual(upstream["sources"][0]["type"], "rss")
            self.assertEqual(upstream["sources"][0]["id"], "docs")
            self.assertIn("rss-feeds.generated.yaml", command)
            self.assertIn("https://example.com/feed.xml", generated)
            self.assertIn("default_min_interval_seconds: 7", generated)

    def test_legacy_raw_export_state_migrates_to_confluence_upstream_config(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            state_dir = project / "raw"
            state_dir.mkdir(parents=True)
            (state_dir / "export-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "roots": [
                            {
                                "page_id": "642319072",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=642319072",
                                "site_base": "https://cwiki.guazi.com",
                                "depth_limit": 3,
                                "space_key": "C2CPM",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)
            config = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))

            self.assertEqual(config["sources"][0]["page_id"], "642319072")
            self.assertEqual(config["sources"][0]["metadata_dir"], "raw")
            self.assertEqual(config["sources"][0]["source_id"], "cwiki-642319072")
            self.assertEqual(config["sources"][0]["relationship"]["role"], "primary")
            self.assertIn(str(project / "raw"), commands[0])

    def test_cwiki_rss_with_source_url_migrates_to_confluence_source(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            config = project / "config" / "rss-feeds.yaml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "feeds:\n"
                "  - id: '605842244'\n"
                "    url: https://cwiki.guazi.com/spaces/createrssfeed.action?x=1\n"
                "    source_url: https://cwiki.guazi.com/pages/viewpage.action?pageId=605842244\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)
            upstream = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))

            self.assertEqual(upstream["sources"][0]["type"], "confluence")
            self.assertEqual(upstream["sources"][0]["page_id"], "605842244")
            self.assertIn("--url", commands[0])
            self.assertNotIn("--update", commands[0])

    def test_confluence_filter_config_is_read_from_filters_object(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (project / "upstream").mkdir(parents=True)
            (project / "upstream" / "wiki-sources.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {
                                "type": "confluence",
                                "enabled": True,
                                "source_id": "cwiki-1",
                                "relationship": {"role": "primary"},
                                "page_id": "1",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                                "depth": 2,
                                "filters": {"updated_since": "2026-01-01"},
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)

            self.assertIn("--updated-since", commands[0])
            self.assertIn("2026-01-01", commands[0])

    def test_confluence_sync_allows_interactive_auth_by_default(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (project / "upstream").mkdir(parents=True)
            (project / "upstream" / "wiki-sources.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {
                                "type": "confluence",
                                "enabled": True,
                                "source_id": "cwiki-1",
                                "relationship": {"role": "primary"},
                                "page_id": "1",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                                "depth": 2,
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)

            self.assertNotIn("--no-cookie-prompt", commands[0])
            self.assertIn("--auto-cookie-from-sso", commands[0])


if __name__ == "__main__":
    unittest.main()
