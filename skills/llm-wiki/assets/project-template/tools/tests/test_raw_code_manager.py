import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_raw_code_manager():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("raw_code_manager", TOOLS_DIR / "raw_code_manager.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class ManagedRawCodeTests(unittest.TestCase):
    def test_add_managed_codebase_clones_repo_and_writes_metadata(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Codex")
            git(source, "config", "user.email", "codex@example.com")
            git(source, "remote", "add", "origin", "git@example.com:team/source-repo.git")
            (source / "README.md").write_text("# demo\n", encoding="utf-8")
            git(source, "add", "README.md")
            git(source, "commit", "-m", "init")

            project = root / "kb"
            project.mkdir()

            result = manager.add_managed_codebase(project, str(source))

            managed = project / "raw-code" / "source-repo"
            self.assertEqual(result["codebase_id"], "source-repo")
            self.assertTrue((managed / ".git").exists())
            metadata = (managed / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
            self.assertIn("managed: true", metadata)
            self.assertIn("codebase_id: source-repo", metadata)
            self.assertIn("created_by: llm-wiki-add-code", metadata)
            status = subprocess.run(["git", "status", "--porcelain"], cwd=managed, check=True, capture_output=True, text=True)
            self.assertEqual(status.stdout.strip(), "")

    def test_permission_failure_does_not_create_target(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "kb"
            project.mkdir()

            with mock.patch.object(manager, "probe_repo_access", return_value=(False, "missing_access")):
                with self.assertRaises(manager.RawCodeManagerError) as ctx:
                    manager.add_managed_codebase(project, "git@example.com:private/repo.git")

            self.assertEqual(ctx.exception.code, "missing_access")
            self.assertFalse((project / "raw-code" / "repo").exists())

    def test_dirty_existing_target_is_rejected(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Codex")
            git(source, "config", "user.email", "codex@example.com")
            git(source, "remote", "add", "origin", "git@example.com:team/source-repo.git")
            (source / "README.md").write_text("# demo\n", encoding="utf-8")
            git(source, "add", "README.md")
            git(source, "commit", "-m", "init")

            project = root / "kb"
            target = project / "raw-code" / "source-repo"
            target.mkdir(parents=True)
            (target / "local.txt").write_text("dirty\n", encoding="utf-8")

            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.add_managed_codebase(project, str(source))

            self.assertEqual(ctx.exception.code, "dirty_target")

    def test_metadata_writer_records_required_fields(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "raw-code" / "demo"
            managed.mkdir(parents=True)

            manager.write_codebase_metadata(
                managed,
                {
                    "codebase_id": "demo",
                    "repo_url": "/tmp/demo.git",
                    "origin_ref": "main",
                    "default_branch": "main",
                    "managed_path": str(managed),
                },
            )

            content = (managed / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
            self.assertIn("codebase_id: demo", content)
            self.assertIn("repo_url: /tmp/demo.git", content)
            self.assertIn("origin_ref: main", content)
            self.assertIn("default_branch: main", content)
            self.assertIn("managed: true", content)

    def test_derive_codebase_id_preserves_existing_underscore_names(self):
        manager = load_raw_code_manager()

        self.assertEqual(manager.derive_codebase_id("https://git.example.com/team/sell_car_miniprogram.git"), "sell_car_miniprogram")

    def test_add_managed_codebase_writes_code_sources_manifest(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.name", "Codex")
            git(source, "config", "user.email", "codex@example.com")
            git(source, "remote", "add", "origin", "git@example.com:team/source-repo.git")
            (source / "README.md").write_text("# demo\n", encoding="utf-8")
            git(source, "add", "README.md")
            git(source, "commit", "-m", "init")

            project = root / "kb"
            project.mkdir()

            manager.add_managed_codebase(project, str(source))

            manifest = manager.read_code_sources_manifest(project)
            self.assertEqual(manifest["version"], 1)
            [entry] = manifest["sources"]
            self.assertEqual(entry["codebase_id"], "source-repo")
            self.assertEqual(entry["repo_url"], "git@example.com:team/source-repo.git")
            self.assertEqual(entry["origin_ref"], "main")
            self.assertEqual(entry["default_branch"], "main")
            self.assertEqual(entry["target_dir"], "raw-code/source-repo")
            self.assertTrue(entry["enabled"])
            self.assertTrue(entry["managed"])
            self.assertEqual(entry["sync"]["mode"], "ff-only")
            metadata = (project / "raw-code" / "source-repo" / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
            self.assertIn("managed_path: raw-code/source-repo", metadata)
            self.assertTrue((project / "upstream" / "code-sources.json").is_file())

    def test_add_managed_codebase_requires_remote_for_shared_manifest(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-repo"
            source.mkdir()
            git(source, "init", "-b", "main")
            project = root / "kb"
            project.mkdir()
            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.add_managed_codebase(project, str(source))
            self.assertEqual(ctx.exception.code, "code_source_config_failed")
            self.assertIn("远程", ctx.exception.message)
            self.assertFalse((project / "upstream" / "code-sources.json").exists())
            self.assertFalse((project / "raw-code").exists())

    def test_write_code_source_manifest_replaces_existing_entry(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            manager.upsert_code_source(project, {
                "codebase_id": "demo",
                "repo_url": "git@example.com:team/demo.git",
                "origin_ref": "main",
                "default_branch": "main",
                "target_dir": "raw-code/demo",
                "enabled": True,
                "managed": True,
                "sync": {"mode": "ff-only"},
            })
            manager.upsert_code_source(project, {
                "codebase_id": "demo",
                "repo_url": "git@example.com:team/demo.git",
                "origin_ref": "release/1",
                "default_branch": "main",
                "target_dir": "raw-code/demo",
                "enabled": True,
                "managed": True,
                "sync": {"mode": "ff-only"},
            })
            manifest = manager.read_code_sources_manifest(project)
            self.assertEqual(len(manifest["sources"]), 1)
            self.assertEqual(manifest["sources"][0]["origin_ref"], "release/1")

    def test_upsert_code_source_reports_malformed_manifest_as_config_error(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "upstream").mkdir()
            (project / "upstream" / "code-sources.json").write_text(
                json.dumps({"version": 1, "sources": [{"repo_url": "git@example.com:team/demo.git"}]}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.upsert_code_source(
                    project,
                    {
                        "codebase_id": "demo",
                        "repo_url": "git@example.com:team/demo.git",
                        "origin_ref": "main",
                        "default_branch": "main",
                        "target_dir": "raw-code/demo",
                        "enabled": True,
                        "managed": True,
                        "sync": {"mode": "ff-only"},
                    },
                )

            self.assertEqual(ctx.exception.code, "code_source_config_failed")

    def test_validate_code_sources_rejects_invalid_entries(self):
        manager = load_raw_code_manager()
        valid = {
            "version": 1,
            "sources": [{
                "codebase_id": "demo",
                "repo_url": "git@example.com:team/demo.git",
                "origin_ref": "main",
                "default_branch": "main",
                "target_dir": "raw-code/demo",
                "enabled": True,
                "managed": True,
                "sync": {"mode": "ff-only"},
            }],
        }

        cases = [
            ("missing_version", {"version": None}),
            ("non_list_sources", {"sources": {"codebase_id": "demo"}}),
            ("non_object_source", {"sources": ["demo"]}),
            ("duplicate_id", {"sources": valid["sources"] * 2}),
            ("empty_codebase_id", {"sources": [{**valid["sources"][0], "codebase_id": ""}]}),
            ("unsafe_codebase_id", {"sources": [{**valid["sources"][0], "codebase_id": "../demo"}]}),
            ("dot_codebase_id", {"sources": [{**valid["sources"][0], "codebase_id": ".", "target_dir": "raw-code/."}]}),
            ("dotdot_codebase_id", {"sources": [{**valid["sources"][0], "codebase_id": "..", "target_dir": "raw-code/.."}]}),
            ("bad_target", {"sources": [{**valid["sources"][0], "target_dir": "../demo"}]}),
            ("target_mismatch", {"sources": [{**valid["sources"][0], "target_dir": "raw-code/other"}]}),
            ("absolute_target", {"sources": [{**valid["sources"][0], "target_dir": "/tmp/demo"}]}),
            ("bad_origin_ref", {"sources": [{**valid["sources"][0], "origin_ref": "origin/main"}]}),
            ("refs_origin_ref", {"sources": [{**valid["sources"][0], "origin_ref": "refs/heads/main"}]}),
            ("dotdot_origin_ref", {"sources": [{**valid["sources"][0], "origin_ref": "feature..bad"}]}),
            ("empty_path_origin_ref", {"sources": [{**valid["sources"][0], "origin_ref": "feature//bad"}]}),
            ("sha_origin_ref", {"sources": [{**valid["sources"][0], "origin_ref": "a" * 40}]}),
            ("missing_codebase_id", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "codebase_id"}]}),
            ("missing_repo_url", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "repo_url"}]}),
            ("missing_origin_ref", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "origin_ref"}]}),
            ("missing_default_branch", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "default_branch"}]}),
            ("missing_target_dir", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "target_dir"}]}),
            ("missing_enabled", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "enabled"}]}),
            ("missing_managed", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "managed"}]}),
            ("missing_sync", {"sources": [{key: value for key, value in valid["sources"][0].items() if key != "sync"}]}),
            ("bad_enabled", {"sources": [{**valid["sources"][0], "enabled": "yes"}]}),
            ("managed_false", {"sources": [{**valid["sources"][0], "managed": False}]}),
            ("bad_sync_mode", {"sources": [{**valid["sources"][0], "sync": {"mode": "reset-hard"}}]}),
            ("local_repo_in_shared", {"sources": [{**valid["sources"][0], "repo_url": "/tmp/demo"}]}),
            ("unsupported_url", {"sources": [{**valid["sources"][0], "repo_url": "ftp://example.com/demo.git"}]}),
        ]
        for name, patch in cases:
            manifest = {**valid, **patch}
            with self.subTest(name):
                with self.assertRaises(manager.RawCodeManagerError) as ctx:
                    manager.validate_code_sources_manifest(manifest, shared_mode=True)
                self.assertEqual(ctx.exception.code, "code_source_config_failed")

    def test_validate_code_sources_rejects_duplicate_target_dir_before_mismatch(self):
        manager = load_raw_code_manager()
        source = {
            "codebase_id": "demo",
            "repo_url": "git@example.com:team/demo.git",
            "origin_ref": "main",
            "default_branch": "main",
            "target_dir": "raw-code/demo",
            "enabled": True,
            "managed": True,
            "sync": {"mode": "ff-only"},
        }
        manifest = {"version": 1, "sources": [source, {**source, "codebase_id": "other"}]}
        with self.assertRaises(manager.RawCodeManagerError) as ctx:
            manager.validate_code_sources_manifest(manifest, shared_mode=True)
        self.assertEqual(ctx.exception.code, "code_source_config_failed")
        self.assertIn("重复", ctx.exception.message)

    def test_validate_code_sources_rejects_invalid_local_repo_url_in_local_mode(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            non_git = project / "non-git-dir"
            non_git.mkdir()
            source = {
                "codebase_id": "demo",
                "repo_url": "missing-repo",
                "origin_ref": "main",
                "default_branch": "main",
                "target_dir": "raw-code/demo",
                "enabled": True,
                "managed": True,
                "sync": {"mode": "ff-only"},
            }

            for repo_url in ["missing-repo", str(non_git), "../outside-repo"]:
                with self.subTest(repo_url=repo_url):
                    manifest = {"version": 1, "sources": [{**source, "repo_url": repo_url}]}
                    with self.assertRaises(manager.RawCodeManagerError) as ctx:
                        manager.validate_code_sources_manifest(manifest, shared_mode=False, project=project)
                    self.assertEqual(ctx.exception.code, "code_source_config_failed")

    def test_read_code_sources_rejects_malformed_json(self):
        manager = load_raw_code_manager()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "upstream").mkdir()
            (project / "upstream" / "code-sources.json").write_text("{not-json\n", encoding="utf-8")

            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.read_code_sources_manifest(project)

            self.assertEqual(ctx.exception.code, "code_source_config_failed")

    def test_validate_code_sources_returns_normalized_sources_sorted(self):
        manager = load_raw_code_manager()
        manifest = {
            "version": 1,
            "sources": [
                {
                    "codebase_id": "zeta",
                    "repo_url": "git@example.com:team/zeta.git",
                    "origin_ref": "main",
                    "default_branch": "main",
                    "target_dir": "raw-code/zeta",
                    "enabled": True,
                    "managed": True,
                    "sync": {"mode": "ff-only"},
                },
                {
                    "codebase_id": "alpha",
                    "repo_url": "https://example.com/team/alpha.git",
                    "origin_ref": "release/1",
                    "default_branch": "main",
                    "target_dir": "raw-code/alpha",
                    "enabled": False,
                    "managed": True,
                    "sync": {"mode": "ff-only"},
                },
            ],
        }

        sources = manager.validate_code_sources_manifest(manifest, shared_mode=True)

        self.assertEqual([source["codebase_id"] for source in sources], ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
