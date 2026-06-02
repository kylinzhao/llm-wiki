import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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


def make_declared_checkout() -> tuple[Path, Path, Path, Path]:
    update_wiki = load_update_wiki()
    root, source, project = make_source_repo_and_kb()
    write_code_sources(project, repo_url=str(source), enabled=True)
    code = update_wiki.run_code_sync(project, shared_mode=False)
    if code != 0:
        raise AssertionError(f"failed to create declared checkout: {code}")
    return root, source, project, project / "raw-code" / "demo"


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


def normalize_cases(cases):
    for case in cases:
        if len(case) == 2:
            name, replacement = case
            remove_key = None
        else:
            name, replacement, remove_key = case
        yield name, replacement, remove_key


def corrupt_metadata(target: Path, replacement: str | None = None, remove_key: str | None = None) -> None:
    path = target / ".llm-wiki-codebase.yaml"
    if replacement is None and remove_key is None:
        path.unlink()
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if remove_key:
        lines = [line for line in lines if not line.startswith(remove_key + ":")]
    if replacement:
        key = replacement.split(":", 1)[0]
        lines = [replacement if line.startswith(key + ":") else line for line in lines]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def checkout_other_branch(target: Path) -> None:
    git(target, "checkout", "-b", "other")


def set_wrong_upstream(target: Path) -> None:
    git(target, "branch", "--unset-upstream")


def dirty_checkout(target: Path) -> None:
    (target / "README.md").write_text("# dirty\n", encoding="utf-8")


def commit_source_change(source: Path, content: str) -> None:
    (source / "README.md").write_text(content, encoding="utf-8")
    git(source, "commit", "-am", "update source")


@contextlib.contextmanager
def patched_specs_and_run_command(update_wiki, stderr: str):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        write_code_sources(project, sources=[])
        target = project / "raw-code" / "demo"
        target.mkdir(parents=True)
        stderr_buffer = io.StringIO()
        spec = {"label": "demo", "cwd": target, "command": ["git", "pull", "--ff-only"]}
        result = update_wiki.CommandResult(128, "", stderr)
        with (
            mock.patch.object(update_wiki, "declared_code_sync_specs", return_value=[spec]),
            mock.patch.object(update_wiki, "git_worktree_dirty", return_value=False),
            mock.patch.object(update_wiki, "run_captured_command", return_value=result),
            contextlib.redirect_stderr(stderr_buffer),
        ):
            yield project, stderr_buffer


@contextlib.contextmanager
def patched_specs_error(update_wiki, code: str, message: str):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        write_code_sources(project, sources=[])
        stderr_buffer = io.StringIO()
        error = update_wiki.RawCodeManagerError(code, message)
        with (
            mock.patch.object(update_wiki, "declared_code_sync_specs", side_effect=error),
            contextlib.redirect_stderr(stderr_buffer),
        ):
            yield project, stderr_buffer


def commit_code_page(project: Path, codebase_id: str = "demo", relative_path: str | None = None) -> None:
    git(project, "init", "-b", "main")
    git(project, "config", "user.name", "Codex")
    git(project, "config", "user.email", "codex@example.com")
    page = project / (relative_path or f"wiki/code/codebases/{codebase_id}/index.md")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Code\n", encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-m", "code evidence")


def run_disabled_source_with_code_page(update_wiki):
    root, source, project = make_source_repo_and_kb()
    write_code_sources(project, repo_url=str(source), enabled=False)
    commit_code_page(project, "demo")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = update_wiki.run_code_sync(project, shared_mode=False)
    return result, project, stderr


def run_legacy_raw_code_with_code_page(update_wiki):
    root, source, project = make_source_repo_and_kb()
    write_code_sources(project, sources=[])
    legacy = project / "raw-code" / "legacy"
    legacy.mkdir(parents=True)
    (legacy / "README.md").write_text("# legacy\n", encoding="utf-8")
    commit_code_page(project, "legacy")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = update_wiki.run_code_sync(project, shared_mode=False)
    return result, project, stderr


def run_code_page_without_source(update_wiki):
    root, source, project = make_source_repo_and_kb()
    write_code_sources(project, sources=[])
    commit_code_page(project, "missing")
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = update_wiki.run_code_sync(project, shared_mode=False)
    return result, project, stderr


class UpdateFailureReportTest(unittest.TestCase):
    def test_shared_main_preflights_and_publishes_success_report_even_with_refinement_pending(self):
        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            calls = []

            def fake_success_report(*args, **kwargs):
                calls.append("success_report")
                report_dir = project / "staging" / "update"
                report_dir.mkdir(parents=True, exist_ok=True)
                (report_dir / "latest.json").write_text(
                    json.dumps(
                        {
                            "status": "ok",
                            "refinement_contract": {
                                "status": "needs_refinement",
                                "pending_count": 2,
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with (
                mock.patch.object(update_wiki, "refresh_agent_rules", return_value="skipped"),
                mock.patch.object(update_wiki, "best_effort_register_current_project"),
                mock.patch.object(update_wiki.shared_update, "shared_preflight", side_effect=lambda *a, **k: calls.append("preflight") or update_wiki.shared_update.PreflightResult("ok")),
                mock.patch.object(update_wiki, "run_code_sync", side_effect=lambda *a, **k: calls.append("code_sync") or 0),
                mock.patch.object(update_wiki, "prepare_raw_evidence", side_effect=lambda *a, **k: calls.append("raw_sync") or (0, None)),
                mock.patch.object(update_wiki, "raw_evidence_preflight_failed", return_value=None),
                mock.patch.object(update_wiki, "run_drawio_repair", return_value=0),
                mock.patch.object(update_wiki, "deterministic_steps", return_value=[]),
                mock.patch.object(update_wiki, "write_success_report", side_effect=fake_success_report),
                mock.patch.object(update_wiki.shared_update, "publish_shared_baseline", side_effect=lambda *a, **k: calls.append("publish") or update_wiki.shared_update.PublishResult("published", "ok")),
                mock.patch.object(sys, "argv", ["update_wiki.py", "--project", str(project), "--no-agent-rules-refresh"]),
            ):
                self.assertEqual(update_wiki.main(), 0)

            self.assertEqual(calls, ["preflight", "code_sync", "raw_sync", "success_report", "publish"])

    def test_shared_main_rejects_cwiki_smoke_limit_before_preflight(self):
        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with (
                mock.patch.dict(update_wiki.os.environ, {"LLM_WIKI_CWIKI_SMOKE_MAX_PAGES": "3"}),
                mock.patch.object(update_wiki.shared_update, "shared_preflight") as preflight,
                mock.patch.object(sys, "argv", ["update_wiki.py", "--project", str(project)]),
            ):
                self.assertEqual(update_wiki.main(), 2)

            preflight.assert_not_called()

    def test_main_registers_current_project_best_effort(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with mock.patch.object(update_wiki, "best_effort_register_current_project", create=True) as register, mock.patch.object(
                update_wiki, "prepare_raw_evidence", return_value=(0, None)
            ), mock.patch.object(update_wiki, "raw_evidence_preflight_failed", return_value=None), mock.patch.object(
                update_wiki, "run_drawio_repair", return_value=0
            ), mock.patch.object(update_wiki, "run_code_sync", return_value=0), mock.patch.object(
                update_wiki, "deterministic_steps", return_value=[]
            ), mock.patch.object(update_wiki, "write_success_report"):
                original_argv = sys.argv
                try:
                    sys.argv = ["update_wiki.py", "--project", str(project), "--local", "--no-agent-rules-refresh"]
                    self.assertEqual(update_wiki.main(), 0)
                finally:
                    sys.argv = original_argv

            register.assert_called_once_with(project.resolve())

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

    def test_run_code_sync_blocks_invalid_existing_checkout_metadata(self):
        update_wiki = load_update_wiki()
        cases = [
            ("missing_metadata", None),
            ("managed_false", "managed: false"),
            ("wrong_origin_ref", "origin_ref: other"),
            ("missing_default_branch", None, "default_branch"),
            ("wrong_managed_path", "managed_path: raw-code/other"),
            ("missing_created_by", None, "created_by"),
        ]
        for name, replacement, remove_key in normalize_cases(cases):
            with self.subTest(name=name):
                root, source, project, target = make_declared_checkout()
                self.addCleanup(lambda root=root: subprocess.run(["rm", "-rf", str(root)], check=False))
                corrupt_metadata(target, replacement=replacement, remove_key=remove_key)
                with capture_stderr() as stderr:
                    self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 2)
                self.assertIn("代码证据", stderr.getvalue())

    def test_run_code_sync_blocks_wrong_branch_and_upstream_and_dirty_checkout(self):
        update_wiki = load_update_wiki()
        for corruptor in [checkout_other_branch, set_wrong_upstream, dirty_checkout]:
            root, source, project, target = make_declared_checkout()
            self.addCleanup(lambda root=root: subprocess.run(["rm", "-rf", str(root)], check=False))
            corruptor(target)
            with capture_stderr() as stderr:
                self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 2)
            self.assertIn("代码证据", stderr.getvalue())

    def test_run_code_sync_blocks_disabled_legacy_or_missing_code_source(self):
        update_wiki = load_update_wiki()
        for runner, expected in [
            (run_disabled_source_with_code_page, "禁用"),
            (run_legacy_raw_code_with_code_page, "未声明"),
            (run_code_page_without_source, "缺少代码证据源"),
        ]:
            with self.subTest(expected=expected):
                result, project, stderr = runner(update_wiki)
                self.assertTrue((project / "wiki" / "code" / "codebases").exists())
                self.assertEqual(result, 2)
                self.assertIn(expected, stderr.getvalue())

    def test_run_code_sync_scans_all_wiki_code_paths_for_conflicts(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        write_code_sources(project, repo_url=str(source), enabled=False)
        commit_code_page(project, "demo", relative_path="wiki/code/capabilities/demo.md")

        with capture_stderr() as stderr:
            result = update_wiki.run_code_sync(project, shared_mode=False)

        self.assertEqual(result, 2)
        self.assertIn("禁用", stderr.getvalue())

    def test_run_code_sync_blocks_wiki_code_without_manifest_source(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        commit_code_page(project, "demo", relative_path="wiki/code/codebases/demo/index.md")

        with capture_stderr() as stderr:
            result = update_wiki.run_code_sync(project, shared_mode=False)

        self.assertEqual(result, 2)
        self.assertIn("缺少代码证据源", stderr.getvalue())

    def test_run_code_sync_ignores_capability_page_stem_without_manifest_source(self):
        update_wiki = load_update_wiki()
        root, source, project = make_source_repo_and_kb()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        commit_code_page(project, "demo", relative_path="wiki/code/capabilities/activity-coupon-marketing.md")

        with capture_stderr() as stderr:
            result = update_wiki.run_code_sync(project, shared_mode=False)

        self.assertEqual(result, 0)
        self.assertNotIn("缺少代码证据源", stderr.getvalue())

    def test_run_code_sync_reports_permission_pull_failure_in_chinese(self):
        update_wiki = load_update_wiki()
        with patched_specs_and_run_command(update_wiki, stderr="Permission denied (publickey)") as (project, stderr):
            code = update_wiki.run_code_sync(project, shared_mode=True)
        self.assertEqual(code, 128)
        self.assertIn("请先获取代码仓库读取权限", stderr.getvalue())
        self.assertIn("共享模式已阻断", stderr.getvalue())
        self.assertIn("LLM_WIKI_UPDATE_MODE=local", stderr.getvalue())

    def test_run_code_sync_reports_non_permission_pull_failure_without_permission_claim(self):
        update_wiki = load_update_wiki()
        with patched_specs_and_run_command(update_wiki, stderr="fatal: not possible to fast-forward") as (project, stderr):
            code = update_wiki.run_code_sync(project, shared_mode=True)
        self.assertEqual(code, 128)
        self.assertIn("代码仓库同步失败", stderr.getvalue())
        self.assertNotIn("获取代码仓库读取权限", stderr.getvalue())

    def test_run_code_sync_reports_invalid_config_without_local_fallback_prompt(self):
        update_wiki = load_update_wiki()
        with patched_specs_error(update_wiki, code="code_source_config_failed", message="target_dir 必须是 raw-code/demo") as (project, stderr):
            code = update_wiki.run_code_sync(project, shared_mode=True)
        self.assertEqual(code, 2)
        self.assertIn("代码证据源配置无效", stderr.getvalue())
        self.assertNotIn("是否切换到本机模式", stderr.getvalue())

    def test_main_blocks_raw_code_sync_before_raw_sync_writes_outputs(self):
        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            calls = []
            args = mock.Mock(
                project=str(project),
                raw_sync_command="",
                no_auto_raw_sync=False,
                graphify=False,
                no_agent_rules_refresh=True,
                local=False,
                shared=False,
            )

            with mock.patch.object(update_wiki.argparse.ArgumentParser, "parse_args", return_value=args), mock.patch.object(
                update_wiki, "best_effort_register_current_project"
            ), mock.patch.object(
                update_wiki.shared_update, "shared_preflight", return_value=update_wiki.shared_update.PreflightResult("ok")
            ), mock.patch.object(
                update_wiki, "prepare_raw_evidence", side_effect=lambda *a, **k: calls.append("raw") or (0, None)
            ), mock.patch.object(
                update_wiki, "run_code_sync", side_effect=lambda *a, **k: calls.append("code") or 2
            ), mock.patch.object(
                update_wiki, "write_failure_report"
            ) as failure_report:
                code = update_wiki.main()

        self.assertEqual(code, 2)
        self.assertEqual(calls, ["code"])
        failure_report.assert_not_called()

    def test_run_code_sync_pulls_existing_declared_checkout(self):
        update_wiki = load_update_wiki()
        root, source, project, target = make_declared_checkout()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        commit_source_change(source, "# v2\n")
        self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 0)
        self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "# v2\n")

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

    def test_success_report_records_graphify_decisions(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            update_wiki.write_success_report(
                project,
                graphify_decisions=[
                    {
                        "codebase_id": "demo",
                        "decision": "skipped_upstream_sufficient",
                        "should_run": False,
                        "reason": "upstream docs/wiki and scan anchors are sufficient",
                    }
                ],
            )

            latest = json.loads((project / "staging" / "update" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["graphify_decisions"][0]["decision"], "skipped_upstream_sufficient")
            latest_md = (project / "staging" / "update" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("## Graphify Decisions", latest_md)
            self.assertIn("skipped_upstream_sufficient", latest_md)

    def test_update_auto_reconciles_historical_refinement_state_before_success_report(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# Product Rules\n\nRule A.\n", encoding="utf-8")
            source_page = project / "wiki" / "sources" / "product-index.md"
            source_page.parent.mkdir(parents=True)
            source_page.write_text(
                "# Product Rules\n\n"
                "## Summary\n\n"
                "Product rules are already summarized from raw/product/index.md.\n\n"
                "## Key Facts\n\n"
                "- Rule A is active.\n\n"
                "## Business Links\n\n"
                "- Concepts: [[concepts/rules|Rules]]\n\n"
                "## Evidence Notes\n\n"
                "- Evidence path: `raw/product/index.md`\n\n"
                "## Source Metadata\n"
                "```json\n"
                '{"raw_rel": "raw/product/index.md", "ai_refinement_state": "pending"}\n'
                "```\n",
                encoding="utf-8",
            )
            plan_path = project / "staging" / "refinement-plan.json"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text(
                json.dumps(
                    {
                        "semantic_update_required": True,
                        "required_source_pages": [
                            {
                                "wiki_path": "wiki/sources/product-index.md",
                                "raw_path": "raw/product/index.md",
                                "required": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(update_wiki, "refresh_agent_rules", return_value="skipped"),
                mock.patch.object(update_wiki, "deterministic_steps", return_value=[]),
                mock.patch.object(sys, "argv", ["update_wiki.py", "--project", str(project), "--local", "--no-auto-raw-sync"]),
            ):
                self.assertEqual(update_wiki.main(), 0)

            latest = json.loads((project / "staging" / "update" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["auto_reconcile"]["metadata_changed_count"], 1)
            self.assertEqual(latest["auto_reconcile"]["status_record_added_count"], 1)
            self.assertEqual(latest["refinement_contract"]["status"], "ok")
            self.assertIn('"ai_refinement_state": "refined"', source_page.read_text(encoding="utf-8"))

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
            raw_page = project / "raw" / "638576143-demo"
            raw_page.mkdir(parents=True)
            (raw_page / "index.md").write_text("# demo\n", encoding="utf-8")
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
            self.assertEqual(config["sources"][0]["metadata_dir"], "staging/wiki-export-state")
            self.assertEqual(len(commands), 1)
            self.assertIn("--update", commands[0])
            self.assertIn("--rss-include-new", commands[0])
            self.assertIn(str(project / "staging" / "wiki-export-state"), commands[0])
            self.assertIn("638576143=https://cwiki.guazi.com/spaces/createrssfeed.action?x=1", commands[0])

    def test_confluence_sync_uses_normal_export_when_raw_cache_missing(self):
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
                                "page_id": "638576143",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=638576143",
                                "depth": 3,
                                "metadata_dir": "staging/wiki-export-state",
                                "output_dir": "raw",
                                "rss_url": "https://cwiki.guazi.com/spaces/createrssfeed.action?x=1",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            progress_dir = project / "staging" / "wiki-export-state" / "progress"
            progress_dir.mkdir(parents=True)
            (progress_dir / "638576143.json").write_text(
                json.dumps(
                    {
                        "root_page_id": "638576143",
                        "depth_limit": 3,
                        "pages": {"638576143": {}},
                        "queue": [],
                        "enqueued": [],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)

            self.assertEqual(len(commands), 1)
            self.assertIn("--url", commands[0])
            self.assertNotIn("--update", commands[0])

    def test_upstream_wiki_sources_normalizes_metadata_dir(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = {
                "type": "confluence",
                "page_id": "123",
                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=123",
                "depth": 2,
            }

            update_wiki.write_upstream_wiki_sources(project, [source])

            payload = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["sources"][0]["metadata_dir"], "staging/wiki-export-state")

    def test_upstream_wiki_sources_converts_project_absolute_metadata_dir(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = {
                "type": "confluence",
                "page_id": "123",
                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=123",
                "depth": 2,
                "metadata_dir": str(project / "staging" / "wiki-export-state"),
            }

            update_wiki.write_upstream_wiki_sources(project, [source])

            payload = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["sources"][0]["metadata_dir"], "staging/wiki-export-state")

    def test_upstream_wiki_sources_rejects_external_absolute_metadata_dir(self):
        import tempfile

        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = {
                "type": "confluence",
                "page_id": "123",
                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=123",
                "depth": 2,
                "metadata_dir": "/tmp/outside-wiki-export-state",
            }

            with self.assertRaises(ValueError):
                update_wiki.write_upstream_wiki_sources(project, [source])

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
            self.assertEqual(config["sources"][0]["metadata_dir"], "staging/wiki-export-state")
            self.assertEqual(config["sources"][0]["source_id"], "cwiki-642319072")
            self.assertEqual(config["sources"][0]["relationship"]["role"], "primary")
            self.assertIn(str(project / "staging" / "wiki-export-state"), commands[0])

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

    def test_confluence_sync_smoke_limit_adds_max_pages_without_changing_default(self):
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

            default_command = update_wiki.confluence_sync_commands(project)[0]
            with mock.patch.dict(update_wiki.os.environ, {"LLM_WIKI_CWIKI_SMOKE_MAX_PAGES": "3"}):
                smoke_command = update_wiki.confluence_sync_commands(project)[0]

            self.assertNotIn("--max-pages", default_command)
            self.assertIn("--max-pages", smoke_command)
            self.assertIn("3", smoke_command)

    def test_repair_wiki_export_state_depth_safely_loads_exporter_module(self):
        update_wiki = load_update_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            tools_dir = project / "tools"
            confluence_dir = tools_dir / "confluence_sync"
            confluence_dir.mkdir(parents=True)
            (confluence_dir / "export_confluence_tree.py").write_text(
                (TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (tools_dir / "drawio_diagram.py").write_text(
                "def drawio_to_mermaid(*_args, **_kwargs):\n    return ''\n",
                encoding="utf-8",
            )
            metadata_dir = project / "staging" / "wiki-export-state"
            progress_dir = metadata_dir / "progress"
            progress_dir.mkdir(parents=True)
            (metadata_dir / "export-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "roots": [
                            {
                                "page_id": "638576143",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=638576143",
                                "site_base": "https://cwiki.guazi.com",
                                "depth_limit": 0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (progress_dir / "638576143.json").write_text(
                json.dumps({"root_page_id": "638576143", "depth_limit": 3, "pages": {}, "queue": [], "enqueued": []}),
                encoding="utf-8",
            )

            self.assertTrue(update_wiki.repair_wiki_export_state_depth(project))

            payload = json.loads((metadata_dir / "export-state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["roots"][0]["depth_limit"], 3)


if __name__ == "__main__":
    unittest.main()
