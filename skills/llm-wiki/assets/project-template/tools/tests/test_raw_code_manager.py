import importlib.util
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


if __name__ == "__main__":
    unittest.main()
