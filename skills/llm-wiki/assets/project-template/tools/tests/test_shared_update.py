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

    def test_local_mode_blocks_dirty_worktree(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            git(project, "config", "user.name", "Codex")
            git(project, "config", "user.email", "codex@example.com")
            (project / ".gitignore").write_text("raw/\nraw-code/\n", encoding="utf-8")
            (project / "wiki").mkdir()
            (project / "wiki" / "page.md").write_text("# v1\n", encoding="utf-8")
            git(project, "add", ".")
            git(project, "commit", "-m", "baseline")
            (project / "wiki" / "page.md").write_text("# v2\n", encoding="utf-8")

            result = shared.local_preflight(project)

            self.assertEqual(result.status, "dirty_worktree_blocked")
            self.assertIn("工作区", result.message)

    def test_local_mode_allows_non_git_project_with_warning(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            result = shared.local_preflight(Path(tmp))
        self.assertEqual(result.status, "ok")
        self.assertIn("不是 git 仓库", result.message)

    def test_shared_preflight_runs_hygiene_before_dirty_worktree(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / "raw" / "page.md").parent.mkdir(exist_ok=True)
            (project / "raw" / "page.md").write_text("# raw\n", encoding="utf-8")
            git(project, "add", "-f", "raw/page.md")
            result = shared.shared_preflight(project, no_auto_raw_sync=False, interactive=False)
        self.assertEqual(result.status, "evidence_cache_tracked_failed")

    def test_shared_mode_blocks_no_upstream(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            git(project, "config", "user.name", "Codex")
            git(project, "config", "user.email", "codex@example.com")
            (project / ".gitignore").write_text("raw/\nraw-code/\n", encoding="utf-8")
            (project / "wiki").mkdir()
            (project / "wiki" / "page.md").write_text("# page\n", encoding="utf-8")
            git(project, "add", ".")
            git(project, "commit", "-m", "baseline")

            result = shared.shared_preflight(project, no_auto_raw_sync=False, interactive=False)

            self.assertEqual(result.status, "shared_sync_failed")
            self.assertIn("上游", result.message)

    def test_shared_mode_no_upstream_interactive_offers_local_mode(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")
            (project / ".gitignore").write_text("raw/\nraw-code/\n", encoding="utf-8")
            result = shared.shared_preflight(project, no_auto_raw_sync=False, interactive=True)
            self.assertEqual(result.status, "offer_local_mode")
            self.assertIn("是否切换到本机模式", result.message)

    def test_shared_mode_non_git_interactive_offers_local_mode_before_hygiene(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            result = shared.shared_preflight(Path(tmp), no_auto_raw_sync=False, interactive=True)

        self.assertEqual(result.status, "offer_local_mode")
        self.assertIn("是否切换到本机模式", result.message)

    def test_shared_mode_dirty_worktree_blocks_before_pull(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / "wiki" / "page.md").write_text("# dirty\n", encoding="utf-8")
            calls = []

            def fake_git(args, cwd):
                calls.append(args[0])
                return shared.GitResult(0, "", "")

            result = shared.shared_preflight(project, False, False, git_runner=fake_git, divergence_reader=lambda cwd, upstream: (0, 1))

        self.assertEqual(result.status, "dirty_worktree_blocked")
        self.assertNotIn("pull", calls)

    def test_shared_mode_rejects_skip_flags(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            git(project, "init", "-b", "main")

            result = shared.shared_preflight(project, no_auto_raw_sync=True, interactive=False)

            self.assertEqual(result.status, "shared_sync_failed")
            self.assertIn("共享模式", result.message)
            self.assertIn("不能跳过 raw/raw-code 同步", result.message)

    def test_shared_mode_read_permission_failure_mentions_permission(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            git(project, "remote", "set-url", "origin", "git@example.invalid:no/read.git")

            result = shared.shared_preflight(
                project,
                no_auto_raw_sync=False,
                interactive=False,
                git_runner=lambda args, cwd: shared.GitResult(128, "", "Permission denied (publickey)"),
            )

            self.assertEqual(result.status, "shared_sync_failed")
            self.assertIn("读取权限", result.message)
            self.assertIn("请先获取 KB 仓库权限", result.message)

    def test_shared_mode_diverged_interactive_offers_local_mode(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            result = shared.shared_preflight(
                project,
                no_auto_raw_sync=False,
                interactive=True,
                git_runner=lambda args, cwd: shared.GitResult(0, "", ""),
                divergence_reader=lambda cwd, upstream: (1, 1),
            )
            self.assertEqual(result.status, "offer_local_mode")
            self.assertIn("是否切换到本机模式", result.message)

    def test_shared_mode_behind_pull_permission_failure_offers_local_mode_interactively(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))

            def fake_git(args, cwd):
                if args[0] == "pull":
                    return shared.GitResult(128, "", "Permission denied (publickey)")
                return shared.GitResult(0, "", "")

            result = shared.shared_preflight(project, False, True, git_runner=fake_git, divergence_reader=lambda cwd, upstream: (0, 1))
            self.assertEqual(result.status, "offer_local_mode")
            self.assertIn("读取权限", result.message)

    def test_shared_mode_behind_pull_non_permission_failure_fails_closed_noninteractive(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))

            def fake_git(args, cwd):
                if args[0] == "pull":
                    return shared.GitResult(1, "", "fatal: not possible to fast-forward")
                return shared.GitResult(0, "", "")

            result = shared.shared_preflight(project, False, False, git_runner=fake_git, divergence_reader=lambda cwd, upstream: (0, 1))
            self.assertEqual(result.status, "shared_sync_failed")
            self.assertNotIn("是否切换到本机模式", result.message)

    def test_shared_mode_ahead_unrecognized_commits_stop(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            result = shared.shared_preflight(
                project,
                no_auto_raw_sync=False,
                interactive=False,
                git_runner=lambda args, cwd: shared.GitResult(0, "", ""),
                divergence_reader=lambda cwd, upstream: (1, 0),
                ahead_is_recognized=lambda cwd, upstream: False,
            )
            self.assertEqual(result.status, "ahead_unrecognized_commits")

    def test_recognized_update_commits_require_actor_and_allowlisted_diff(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / "wiki" / "page.md").write_text("# changed\n", encoding="utf-8")
            git(project, "add", "wiki/page.md")
            git(project, "commit", "-m", f"Update {project.name} knowledge base", "-m", "Actor: local-skill")
            self.assertTrue(shared.recognized_update_commits_only(project, "origin/main"))

    def test_recognized_update_commits_reject_mixed_stack_missing_actor(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            for page, body in [("a.md", "Actor: local-skill"), ("b.md", "")]:
                (project / "wiki" / page).write_text("# changed\n", encoding="utf-8")
                git(project, "add", "wiki/" + page)
                git(project, "commit", "-m", f"Update {project.name} knowledge base", "-m", body)
            self.assertFalse(shared.recognized_update_commits_only(project, "origin/main"))

    def test_recognized_ahead_push_non_permission_failure_uses_generic_message(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))

            def fake_git(args, cwd):
                if args[0] == "push":
                    return shared.GitResult(1, "", "fatal: remote end hung up unexpectedly")
                return shared.GitResult(0, "", "")

            result = shared.shared_preflight(
                project,
                False,
                False,
                git_runner=fake_git,
                divergence_reader=lambda cwd, upstream: (1, 0),
                ahead_is_recognized=lambda cwd, upstream: True,
            )
            self.assertEqual(result.status, "unpublished_local_baseline")
            self.assertNotIn("写入权限", result.message)

    def test_shared_mode_blocks_remaining_divergence_after_recognized_push(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            states = iter([(1, 0), (1, 1)])
            result = shared.shared_preflight(
                project,
                no_auto_raw_sync=False,
                interactive=False,
                git_runner=lambda args, cwd: shared.GitResult(0, "", ""),
                divergence_reader=lambda cwd, upstream: next(states),
                ahead_is_recognized=lambda cwd, upstream: True,
            )
            self.assertEqual(result.status, "shared_sync_failed")

    def test_recognized_ahead_recovery_pulls_when_post_push_is_behind(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            calls = []
            states = iter([(1, 0), (0, 1)])

            def fake_git(args, cwd):
                calls.append(args[0])
                return shared.GitResult(0, "", "")

            result = shared.shared_preflight(
                project,
                False,
                False,
                git_runner=fake_git,
                divergence_reader=lambda cwd, upstream: next(states),
                ahead_is_recognized=lambda cwd, upstream: True,
            )
            self.assertEqual(result.status, "ok")
            self.assertIn("pull", calls)

    def test_recognized_update_commits_reject_excluded_diff(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / ".env").write_text("TOKEN=x\n", encoding="utf-8")
            git(project, "add", "-f", ".env")
            git(project, "commit", "-m", f"Update {project.name} knowledge base", "-m", "Actor: local-skill")
            self.assertFalse(shared.recognized_update_commits_only(project, "origin/main"))

    def test_recognized_update_commits_reject_rename_from_excluded_diff(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / ".env").write_text("TOKEN=x\n", encoding="utf-8")
            git(project, "add", "-f", ".env")
            git(project, "commit", "-m", "seed env")
            git(project, "push")
            git(project, "mv", ".env", "wiki/env.md")
            git(project, "commit", "-m", f"Update {project.name} knowledge base", "-m", "Actor: local-skill")

            self.assertFalse(shared.recognized_update_commits_only(project, "origin/main"))

    def test_publish_no_changes_returns_no_changes(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))

            result = shared.publish_shared_baseline(project, actor="local-skill")

            self.assertEqual(result.status, "no_changes")

    def test_publish_commits_allowlisted_changes_with_actor(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / "wiki" / "page.md").write_text("# changed\n", encoding="utf-8")

            result = shared.publish_shared_baseline(project, actor="local-skill")

            self.assertEqual(result.status, "published")
            message = git(project, "log", "-1", "--format=%B").stdout
            self.assertIn("Update", message)
            self.assertIn("Actor: local-skill", message)

    def test_commit_failed_dirty_result_blocks_next_local_and_shared_preflight(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            hook = project / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            (project / "wiki" / "page.md").write_text("# changed\n", encoding="utf-8")

            result = shared.publish_shared_baseline(project, actor="local-skill")

            self.assertEqual(result.status, "commit_failed_dirty_result")
            self.assertEqual(shared.local_preflight(project).status, "dirty_worktree_blocked")
            self.assertEqual(shared.shared_preflight(project, no_auto_raw_sync=False, interactive=False).status, "dirty_worktree_blocked")

    def test_push_permission_failure_mentions_write_permission(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            (project / "wiki" / "page.md").write_text("# changed\n", encoding="utf-8")

            def fake_run_git(args, cwd):
                if args[0] == "push":
                    return shared.GitResult(128, "", "remote: You are not allowed")
                return shared.run_git(args, cwd)

            result = shared.publish_shared_baseline(project, actor="local-skill", git_runner=fake_run_git)

            self.assertEqual(result.status, "unpublished_local_baseline")
            self.assertIn("写入权限", result.message)
            self.assertIn("请先获取 KB 仓库权限", result.message)

    def test_publish_status_failure_fails_closed(self):
        shared = load_shared_update()
        with tempfile.TemporaryDirectory() as tmp:
            project, remote = make_repo_with_remote(Path(tmp))
            result = shared.publish_shared_baseline(
                project,
                actor="local-skill",
                status_runner=lambda args, cwd: shared.GitBytesResult(128, b"", "fatal: status failed"),
            )
            self.assertEqual(result.status, "shared_sync_failed")
            self.assertNotEqual(result.status, "no_changes")

    def test_resolve_update_mode_defaults_to_shared(self):
        shared = load_shared_update()
        self.assertEqual(shared.resolve_update_mode(local_flag=False, shared_flag=False, env={}), "shared")
        self.assertEqual(shared.resolve_update_mode(local_flag=True, shared_flag=False, env={}), "local")
        self.assertEqual(shared.resolve_update_mode(local_flag=False, shared_flag=False, env={"LLM_WIKI_UPDATE_MODE": "local"}), "local")

    def test_shared_protocol_rejects_skip_flags_before_update_callback(self):
        shared = load_shared_update()
        for kwargs in [
            {"no_auto_raw_sync": True, "env": {}},
            {"no_auto_raw_sync": False, "env": {"LLM_WIKI_NO_AUTO_RAW_SYNC": "1"}},
        ]:
            with self.subTest(kwargs=kwargs):
                calls = []
                result = shared.begin_update(project=Path("."), mode="shared", interactive=False, update_callback=lambda: calls.append("update"), **kwargs)
                self.assertEqual(result.status, "shared_sync_failed")
                self.assertIn("共享模式不能跳过 raw/raw-code 同步", result.message)
                self.assertEqual(calls, [])

    def test_shared_protocol_does_not_publish_before_semantic_callback_finishes(self):
        shared = load_shared_update()
        events = []
        result = shared.complete_shared_update(
            project=Path("."),
            semantic_validation=lambda: events.append("semantic") or shared.PublishResult("ok"),
            publisher=lambda project: events.append("publish") or shared.PublishResult("published"),
        )
        self.assertEqual(result.status, "published")
        self.assertEqual(events, ["semantic", "publish"])

    def test_accept_local_fallback_restarts_local_preflight(self):
        shared = load_shared_update()
        events = []
        result = shared.accept_local_fallback(
            project=Path("."),
            local_preflight_fn=lambda project: events.append("local_preflight") or shared.PreflightResult("ok"),
            update_callback=lambda: events.append("update") or 0,
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(events, ["local_preflight", "update"])


if __name__ == "__main__":
    unittest.main()
