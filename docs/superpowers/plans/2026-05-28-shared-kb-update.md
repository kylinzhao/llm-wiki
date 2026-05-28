# Shared KB Update Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `llm-wiki update` default to shared git baseline sync/publish while restoring `raw/` and `raw-code/` from committed declarations.

**Architecture:** Keep deterministic KB maintenance in `tools/update_wiki.py`, and add focused helpers around it: raw-code source declaration management, evidence-cache git hygiene, and shared git orchestration. The skill docs describe the user-facing protocol; template tools provide testable primitives that gateway/local wrappers can call.

**Tech Stack:** Python 3.10+, stdlib `subprocess`/`json`/`fnmatch`, PyYAML already in the project template, `pytest` tests under `skills/llm-wiki/assets/project-template/tools/tests`.

---

Spec: `docs/superpowers/specs/2026-05-28-shared-kb-update-design.md`

## Chunk 1: Template Evidence Cache Ignore

### File Structure

- Modify `skills/llm-wiki/assets/project-template/.gitignore`: add `raw-code/`.

### Task 1: Template Ignores Raw-Code

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/.gitignore`
- Test: `skills/llm-wiki/scripts/tests/test_install_project_template.py`

- [ ] **Step 1: Write the failing installer test**

Add a test proving installed project templates ignore both evidence caches:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest skills/llm-wiki/scripts/tests/test_install_project_template.py::InstallProjectTemplateTest::test_project_template_ignores_evidence_caches -q
```

Expected: FAIL because `raw-code/` is absent.

- [ ] **Step 3: Add `raw-code/` to the template `.gitignore`**

Update `skills/llm-wiki/assets/project-template/.gitignore`:

```gitignore
raw/
raw-code/
.DS_Store
**/.DS_Store
__pycache__/
.pytest_cache/
graphify-out/
```

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/.gitignore skills/llm-wiki/scripts/tests/test_install_project_template.py
git commit -m "Add raw-code to template gitignore"
```

## Chunk 2: Code Source Manifest Writer

### File Structure

- Create `skills/llm-wiki/assets/project-template/upstream/code-sources.json`: empty committed manifest with `version: 1`.
- Modify `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`: write/update `upstream/code-sources.json` from `llm-wiki add-code` and keep `.llm-wiki-codebase.yaml` local metadata.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`: cover manifest write/update.

### Task 2: Add Code Source Manifest Writer

**Files:**
- Create: `skills/llm-wiki/assets/project-template/upstream/code-sources.json`
- Modify: `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`

- [ ] **Step 1: Write failing tests for manifest creation and update**

Add tests:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_add_managed_codebase_writes_code_sources_manifest tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_add_managed_codebase_requires_remote_for_shared_manifest tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_write_code_source_manifest_replaces_existing_entry -q
```

Expected: FAIL because manifest helpers do not exist and the remote-less path is not yet all-or-nothing.

- [ ] **Step 3: Add manifest helpers**

Implement in `raw_code_manager.py`:

```python
CODE_SOURCES_PATH = Path("upstream/code-sources.json")

def read_code_sources_manifest(project: Path) -> dict[str, object]:
    path = project / CODE_SOURCES_PATH
    if not path.is_file():
        return {"version": 1, "sources": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RawCodeManagerError("code_source_config_failed", f"upstream/code-sources.json 不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 必须是对象")
    return data

def write_code_sources_manifest(project: Path, manifest: dict[str, object]) -> Path:
    path = project / CODE_SOURCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path

def upsert_code_source(project: Path, entry: dict[str, object]) -> Path:
    manifest = read_code_sources_manifest(project)
    sources = [s for s in manifest.get("sources", []) if isinstance(s, dict) and s.get("codebase_id") != entry["codebase_id"]]
    sources.append(entry)
    manifest = {"version": 1, "sources": sorted(sources, key=lambda item: str(item["codebase_id"]))}
    return write_code_sources_manifest(project, manifest)
```

Also import `json`. Do not add validation in this task; Task 3 adds the validator and then wires `upsert_code_source(...)` to call it.

- [ ] **Step 4: Update `add_managed_codebase` to call `upsert_code_source`**

After writing `.llm-wiki-codebase.yaml`, add:

```python
upsert_code_source(project, {
    "codebase_id": resolved_codebase_id,
    "repo_url": remote_origin_url,
    "origin_ref": default_branch,
    "default_branch": default_branch,
    "target_dir": f"raw-code/{resolved_codebase_id}",
    "enabled": True,
    "managed": True,
    "sync": {"mode": "ff-only"},
})
```

Also change the existing metadata payload in `add_managed_codebase` so `.llm-wiki-codebase.yaml` records a repo-relative path:

```python
"managed_path": f"raw-code/{resolved_codebase_id}",
```

If the source checkout has no remote URL, stop with a Chinese `code_source_config_failed` message and do not write `upstream/code-sources.json`; shared declarations must be cross-machine restorable.
Validate the remote origin before creating `raw-code/<codebase_id>` or writing `.llm-wiki-codebase.yaml`, so a failed shared declaration leaves no local evidence cache that another machine cannot restore.

- [ ] **Step 5: Add empty template manifest**

Create `skills/llm-wiki/assets/project-template/upstream/code-sources.json`:

```json
{
  "version": 1,
  "sources": []
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run the same `uv run pytest` command.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/llm-wiki/assets/project-template/upstream/code-sources.json skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py
git commit -m "Track raw-code source declarations"
```

## Chunk 3: Code Source Manifest Validation

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`: fully validate code source records.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`: cover manifest validation.

### Task 3: Validate Code Source Manifest

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`

- [ ] **Step 1: Write validation tests**

Add table-driven tests for invalid config:

```python
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
    for _name, patch in cases:
        manifest = {**valid, **patch}
        with self.subTest(_name):
            with self.assertRaises(manager.RawCodeManagerError) as ctx:
                manager.validate_code_sources_manifest(manifest, shared_mode=True)
            self.assertEqual(ctx.exception.code, "code_source_config_failed")

def test_validate_code_sources_rejects_duplicate_target_dir_before_mismatch(self):
    manager = load_raw_code_manager()
    source = {"codebase_id": "demo", "repo_url": "git@example.com:team/demo.git", "origin_ref": "main", "default_branch": "main", "target_dir": "raw-code/demo", "enabled": True, "managed": True, "sync": {"mode": "ff-only"}}
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
        source = {"codebase_id": "demo", "repo_url": "missing-repo", "origin_ref": "main", "default_branch": "main", "target_dir": "raw-code/demo", "enabled": True, "managed": True, "sync": {"mode": "ff-only"}}

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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_validate_code_sources_rejects_invalid_entries tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_validate_code_sources_rejects_duplicate_target_dir_before_mismatch tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_validate_code_sources_rejects_invalid_local_repo_url_in_local_mode tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_read_code_sources_rejects_malformed_json tools/tests/test_raw_code_manager.py::ManagedRawCodeTests::test_validate_code_sources_returns_normalized_sources_sorted -q
```

Expected: FAIL until validator is fully hardened.

- [ ] **Step 3: Implement one canonical validator**

In `raw_code_manager.py`, add `import re` and implement:

```python
def validate_code_sources_manifest(manifest: dict[str, object], shared_mode: bool, project: Path | None = None) -> list[dict[str, object]]:
    if manifest.get("version") != 1:
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 的 version 必须是 1")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise RawCodeManagerError("code_source_config_failed", "upstream/code-sources.json 的 sources 必须是列表")

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict):
            raise RawCodeManagerError("code_source_config_failed", "每个代码证据源必须是对象")
        codebase_id = str(raw.get("codebase_id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", codebase_id) or codebase_id in {".", ".."}:
            raise RawCodeManagerError("code_source_config_failed", f"无效的 codebase_id：{codebase_id}")
        target_dir = str(raw.get("target_dir", ""))
        if codebase_id in seen_ids or target_dir in seen_targets:
            raise RawCodeManagerError("code_source_config_failed", "重复的 codebase_id 或 target_dir")
        if target_dir != f"raw-code/{codebase_id}":
            raise RawCodeManagerError("code_source_config_failed", f"target_dir 必须是 raw-code/{codebase_id}")
        seen_ids.add(codebase_id)
        seen_targets.add(target_dir)

        repo_url = str(raw.get("repo_url", ""))
        if not repo_url:
            raise RawCodeManagerError("code_source_config_failed", "缺少必填字段 repo_url")
        if is_local_repo_url(repo_url):
            if shared_mode:
                raise RawCodeManagerError("code_source_config_failed", "共享模式不允许使用本机 repo_url")
            if project is None:
                raise RawCodeManagerError("code_source_config_failed", "校验本机 repo_url 时必须提供项目目录")
            local_path = (project / repo_url).resolve() if not Path(repo_url).is_absolute() else Path(repo_url).resolve()
            if ".." in Path(repo_url).parts or not local_path.exists() or run_git(["rev-parse", "--is-inside-work-tree"], cwd=local_path).returncode != 0:
                raise RawCodeManagerError("code_source_config_failed", "本机 repo_url 必须指向已存在的 git 仓库")
        elif not (repo_url.startswith("git@") or repo_url.startswith("ssh://") or repo_url.startswith("http://") or repo_url.startswith("https://")):
            raise RawCodeManagerError("code_source_config_failed", f"不支持的 repo_url：{repo_url}")

        origin_ref = str(raw.get("origin_ref", ""))
        bad_ref = origin_ref.startswith(("origin/", "refs/")) or ".." in origin_ref or "//" in origin_ref or re.fullmatch(r"[0-9a-fA-F]{40}", origin_ref)
        if bad_ref or run_git(["check-ref-format", "--branch", origin_ref]).returncode != 0:
            raise RawCodeManagerError("code_source_config_failed", f"无效的 origin_ref：{origin_ref}")
        if not isinstance(raw.get("enabled"), bool) or raw.get("managed") is not True or raw.get("sync") != {"mode": "ff-only"}:
            raise RawCodeManagerError("code_source_config_failed", "enabled、managed 或 sync.mode 配置无效")

        default_branch = raw.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise RawCodeManagerError("code_source_config_failed", "缺少必填字段 default_branch")
        normalized.append({
            "codebase_id": codebase_id,
            "repo_url": repo_url,
            "origin_ref": origin_ref,
            "default_branch": default_branch,
            "target_dir": target_dir,
            "enabled": raw["enabled"],
            "managed": True,
            "sync": {"mode": "ff-only"},
        })
    return sorted(normalized, key=lambda source: str(source["codebase_id"]))
```

Use a small helper:

```python
def is_local_repo_url(value: str) -> bool:
    return value.startswith("/") or value.startswith("./") or value.startswith("../") or not ("://" in value or "@" in value)
```

Update `upsert_code_source(...)` to call `validate_code_sources_manifest(manifest, shared_mode=False, project=project)` before writing the manifest.

- [ ] **Step 4: Run validation tests**

Run the same focused pytest command.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py
git commit -m "Validate raw-code source declarations"
```

## Chunk 4: Raw-Code Clone Restore

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`: clone missing managed raw-code checkouts and write complete local metadata.
- Modify `skills/llm-wiki/assets/project-template/tools/update_wiki.py`: expose `run_code_sync(project, shared_mode=...)` over manifest-backed sync specs.
- Test `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`: missing checkout restore and shared-mode local `repo_url` rejection.

### Task 4: Restore Missing Declared Raw-Code

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`

- [ ] **Step 1: Write clone/restore tests**

Add focused tests:

```python
def test_run_code_sync_clones_missing_enabled_source(self):
    update_wiki = load_update_wiki()
    root, source, project = make_source_repo_and_kb()
    write_code_sources(project, repo_url=str(source), enabled=True)
    code = update_wiki.run_code_sync(project, shared_mode=False)
    self.assertEqual(code, 0)
    metadata = (project / "raw-code" / "demo" / ".llm-wiki-codebase.yaml").read_text(encoding="utf-8")
    for expected in ["codebase_id: demo", "repo_url: " + str(source), "origin_ref: main", "default_branch: main", "managed_path: raw-code/demo", "managed: true", "created_by: llm-wiki-add-code"]:
        self.assertIn(expected, metadata)

def test_run_code_sync_rejects_local_repo_url_in_shared_mode(self):
    update_wiki = load_update_wiki()
    root, source, project = make_source_repo_and_kb()
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
    write_code_sources(project, sources=[
        valid_source(repo_url=str(source), codebase_id="first", target_dir="raw-code/first"),
        {**valid_source(repo_url="git@example.com:team/bad.git"), "target_dir": "../bad"},
    ])
    self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 2)
    self.assertFalse((project / "raw-code").exists())

def test_run_code_sync_clones_origin_ref_branch_not_default_branch(self):
    update_wiki = load_update_wiki()
    root, source, project = make_source_repo_and_kb(extra_branch="release/1")
    write_code_sources(project, repo_url=str(source), origin_ref="release/1", enabled=True)
    self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 0)
    branch = git(project / "raw-code" / "demo", "branch", "--show-current").stdout.strip()
    upstream = git(project / "raw-code" / "demo", "rev-parse", "--abbrev-ref", "@{u}").stdout.strip()
    self.assertEqual((branch, upstream), ("release/1", "origin/release/1"))
```

`make_source_repo_and_kb()` creates a temp git repo on branch `main`, commits `README.md`, and returns `(root, source, project)`. `write_code_sources(...)` writes a valid `upstream/code-sources.json` for `raw-code/demo`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_clones_missing_enabled_source tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_rejects_local_repo_url_in_shared_mode tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_validates_all_sources_before_clone tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_clones_origin_ref_branch_not_default_branch -q
```

Expected: FAIL.

- [ ] **Step 3: Implement missing checkout restore**

Add `ensure_managed_checkout(project, source)` in `raw_code_manager.py`:

```python
CODE_REPO_PERMISSION_PATTERNS = (
    "permission denied",
    "authentication failed",
    "repository not found",
    "403",
    "you are not allowed",
    "could not read from remote repository",
    "http basic: access denied",
)

def is_permission_error(message: str) -> bool:
    lowered = message.lower()
    return any(pattern in lowered for pattern in CODE_REPO_PERMISSION_PATTERNS)

def ensure_managed_checkout(project: Path, source: dict[str, object]) -> Path:
    target = project / str(source["target_dir"])
    if target.exists():
        return target
    try:
        clone_repo(str(source["repo_url"]), target)
    except RawCodeManagerError as exc:
        if is_permission_error(exc.message):
            raise RawCodeManagerError("evidence_failed", f"无法访问代码证据仓库。请先获取代码仓库读取权限后重试。详情：{exc.message}") from exc
        raise RawCodeManagerError("evidence_failed", f"代码证据仓库克隆失败。请检查仓库地址、网络或分支配置。详情：{exc.message}") from exc
    for args, message in [(["checkout", str(source["origin_ref"])], "无法切换到声明的代码分支。请检查代码仓库分支权限和 origin_ref 配置。"), (["branch", "--set-upstream-to", f"origin/{source['origin_ref']}"], "无法配置代码仓库上游分支。请检查代码仓库读取权限和分支配置。")]:
        if run_git(args, cwd=target).returncode != 0:
            raise RawCodeManagerError("evidence_failed", message)
    write_codebase_metadata(target, {"codebase_id": str(source["codebase_id"]), "repo_url": str(source["repo_url"]), "origin_ref": str(source["origin_ref"]), "default_branch": str(source["default_branch"]), "managed_path": str(source["target_dir"]), "managed": True, "created_by": "llm-wiki-add-code"})
    return target
```

Wire `managed_code_sync_specs(project, shared_mode)` to read and validate `upstream/code-sources.json`, reject local `repo_url` in shared mode through the validator, call `ensure_managed_checkout` for enabled sources, and return pull specs.
Keep this local `is_permission_error(...)` in `raw_code_manager.py`; the shared git classifier added later handles KB repository pull/push errors, while this helper keeps code repository clone/checkout errors self-contained for this chunk.

- [ ] **Step 4: Run clone/restore tests**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py
git commit -m "Restore missing raw-code checkouts"
```

## Chunk 5: Existing Raw-Code Checkout Validation

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`: validate existing managed raw-code checkouts and globally scan code evidence conflicts before returning pull specs.
- Test `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`: metadata, branch, upstream, dirty checkout, disabled/legacy code evidence blockers.

### Task 5: Validate Existing Declared Checkouts and Code Evidence Conflicts

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`

- [ ] **Step 1: Write existing-checkout validation tests**

Add helper-driven tests:

```python
def test_run_code_sync_blocks_invalid_existing_checkout_metadata(self):
    update_wiki = load_update_wiki()
    cases = [("missing_metadata", None), ("managed_false", "managed: false"), ("wrong_origin_ref", "origin_ref: other"), ("missing_default_branch", None, "default_branch"), ("wrong_managed_path", "managed_path: raw-code/other"), ("missing_created_by", None, "created_by")]
    for name, replacement, remove_key in normalize_cases(cases):
        with self.subTest(name=name):
            root, source, project, target = make_declared_checkout()
            corrupt_metadata(target, replacement=replacement, remove_key=remove_key)
            with capture_stderr() as stderr:
                self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 2)
            self.assertIn("代码证据", stderr.getvalue())

def test_run_code_sync_blocks_wrong_branch_and_upstream_and_dirty_checkout(self):
    update_wiki = load_update_wiki()
    for corruptor in [checkout_other_branch, set_wrong_upstream, dirty_checkout]:
        root, source, project, target = make_declared_checkout()
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
```

The helpers must create real git repos before corrupting metadata or branch/upstream state.
`run_disabled_source_with_code_page`, `run_legacy_raw_code_with_code_page`, and `run_code_page_without_source` return `(result, project, stderr)`. They must create committed `wiki/code/codebases/<codebase_id>/` evidence in a git repo before invoking `run_code_sync`, so they exercise the spec's "code evidence expected" condition.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_blocks_invalid_existing_checkout_metadata tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_blocks_wrong_branch_and_upstream_and_dirty_checkout tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_blocks_disabled_legacy_or_missing_code_source -q
```

Expected: FAIL.

- [ ] **Step 3: Implement existing-checkout validation**

Add `validate_existing_checkout(project, source, target)` and call it before returning each pull spec. It must verify metadata equality for `codebase_id`, `repo_url`, `origin_ref`, `default_branch`, `managed_path`, plus `managed: true` and `created_by: llm-wiki-add-code`; the target is a clean git checkout; current branch is `origin_ref`; and upstream is `origin/<origin_ref>`.

- [ ] **Step 4: Implement global code evidence conflict scan**

Add `validate_code_evidence_conflicts(project, sources)` and call it once after manifest validation and before per-source pull specs. This global scan owns cross-source checks that are not properties of one existing checkout: disabled sources cannot have committed `wiki/code/**` evidence; `raw-code/<id>` or `wiki/code/**` evidence without a manifest source blocks as undeclared; and committed code pages that imply a missing enabled source block with `缺少代码证据源`. It must scan all `wiki/code/**`, not only `wiki/code/codebases/**`. All `RawCodeManagerError` messages must be Chinese.

- [ ] **Step 5: Run existing-checkout tests**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py
git commit -m "Validate managed raw-code checkouts"
```

## Chunk 6: Raw-Code Sync Error Reporting

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/update_wiki.py`: call manifest-backed specs and map raw-code sync failures to Chinese terminal messages.
- Test `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`: permission and non-permission pull failures, invalid config, and successful pull.

### Task 6: Report Raw-Code Sync Failures Correctly

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`

- [ ] **Step 1: Write sync error reporting tests**

Add tests:

```python
def test_run_code_sync_reports_permission_pull_failure_in_chinese(self):
    update_wiki = load_update_wiki()
    with patched_specs_and_run_command(stderr="Permission denied (publickey)") as (project, stderr):
        code = update_wiki.run_code_sync(project, shared_mode=True)
    self.assertEqual(code, 128)
    self.assertIn("请先获取代码仓库读取权限", stderr.getvalue())

def test_run_code_sync_reports_non_permission_pull_failure_without_permission_claim(self):
    update_wiki = load_update_wiki()
    with patched_specs_and_run_command(stderr="fatal: not possible to fast-forward") as (project, stderr):
        code = update_wiki.run_code_sync(project, shared_mode=True)
    self.assertEqual(code, 128)
    self.assertIn("代码仓库同步失败", stderr.getvalue())
    self.assertNotIn("获取代码仓库读取权限", stderr.getvalue())

def test_run_code_sync_reports_invalid_config_without_local_fallback_prompt(self):
    update_wiki = load_update_wiki()
    with patched_specs_error(code="code_source_config_failed", message="target_dir 必须是 raw-code/demo") as (project, stderr):
        code = update_wiki.run_code_sync(project, shared_mode=True)
    self.assertEqual(code, 2)
    self.assertIn("代码证据源配置无效", stderr.getvalue())
    self.assertNotIn("是否切换到本机模式", stderr.getvalue())

def test_run_code_sync_pulls_existing_declared_checkout(self):
    update_wiki = load_update_wiki()
    root, source, project, target = make_declared_checkout()
    commit_source_change(source, "# v2\n")
    self.assertEqual(update_wiki.run_code_sync(project, shared_mode=False), 0)
    self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "# v2\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_reports_permission_pull_failure_in_chinese tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_reports_non_permission_pull_failure_without_permission_claim tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_reports_invalid_config_without_local_fallback_prompt tools/tests/test_update_wiki_failure_report.py::UpdateFailureReportTest::test_run_code_sync_pulls_existing_declared_checkout -q
```

Expected: FAIL.

- [ ] **Step 3: Update `run_code_sync`**

Change `run_code_sync(project, shared_mode=False)` to call `managed_code_sync_specs(project, shared_mode=shared_mode)` first. Replace the existing int-only pull path with a helper that runs `subprocess.run(..., capture_output=True, text=True)` for `git pull --ff-only`, so stderr is available for classification. For each spec, verify the target exists and is clean, execute the captured pull, classify stderr, and print either the code-repo permission guidance or a generic Chinese sync failure. Invalid manifests print `code_source_config_failed: 代码证据源配置无效：...`; restore failures print `evidence_failed: 代码证据恢复失败：...`.

- [ ] **Step 4: Run focused sync reporting tests**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 5: Run raw-code related tests**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_raw_code_manager.py tools/tests/test_update_wiki_failure_report.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py
git commit -m "Report raw-code sync failures in Chinese"
```

## Chunk 7: Shared Permission Classifier

### File Structure

- Create `skills/llm-wiki/assets/project-template/tools/shared_update.py`: permission classifier and git result helpers.
- Create `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: shared update test harness and classifier tests.

### Task 7: Permission Classifier and Terminal States

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write classifier tests**

Create `test_shared_update.py` with:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py::SharedUpdateTests::test_classifies_read_and_write_permission_errors -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement classifier**

Create `shared_update.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import os
import subprocess

@dataclass
class GitResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

PERMISSION_PATTERNS = (
    "permission denied",
    "authentication failed",
    "repository not found",
    "403",
    "you are not allowed",
    "could not read from remote repository",
    "http basic: access denied",
)

def classify_git_permission(stderr: str, operation: str) -> str:
    lowered = stderr.lower()
    if any(pattern in lowered for pattern in PERMISSION_PATTERNS):
        return "write_permission" if operation == "push" else "read_permission"
    return "none"

def run_git(args: list[str], cwd: Path) -> GitResult:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return GitResult(result.returncode, result.stdout, result.stderr)
```

- [ ] **Step 4: Run test to verify it passes**

Run the same focused pytest.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Add shared update permission classifier"
```

## Chunk 8: Evidence Cache Hygiene Preflight

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: evidence cache git hygiene helper.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: raw/raw-code ignore and tracked-file tests.

### Task 8: Evidence Cache Hygiene Preflight

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write hygiene tests**

Add tests for:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py::SharedUpdateTests::test_evidence_cache_hygiene_requires_raw_ignored tools/tests/test_shared_update.py::SharedUpdateTests::test_evidence_cache_hygiene_rejects_tracked_raw tools/tests/test_shared_update.py::SharedUpdateTests::test_evidence_cache_hygiene_checks_raw_code_when_declared tools/tests/test_shared_update.py::SharedUpdateTests::test_evidence_cache_hygiene_checks_raw_code_when_wiki_code_exists -q
```

Expected: FAIL.

- [ ] **Step 3: Implement hygiene helper**

In `shared_update.py`:

```python
@dataclass
class PreflightResult:
    status: str
    message: str = ""

def check_evidence_cache_hygiene(project: Path) -> PreflightResult:
    paths = ["raw/"]
    raw_code_needed = any([
        (project / "raw-code").exists(),
        (project / "upstream" / "code-sources.json").exists(),
        (project / "wiki" / "code").exists(),
        (project / "staging" / "code-graph").exists(),
    ])
    if raw_code_needed:
        paths.append("raw-code/")

    for path in paths:
        tracked = run_git(["ls-files", "--", path], cwd=project)
        if tracked.stdout.strip():
            first = tracked.stdout.splitlines()[0]
            return PreflightResult(
                "evidence_cache_tracked_failed",
                f"证据缓存 {first} 已被 git 跟踪。请先从仓库中移除 raw/raw-code 缓存文件。",
            )
        ignored = run_git(["check-ignore", "-q", path], cwd=project)
        if ignored.returncode != 0:
            return PreflightResult(
                "evidence_cache_ignore_failed",
                f"证据缓存 {path} 必须写入 .gitignore 后才能使用共享更新。",
            )
    return PreflightResult("ok")
```

- [ ] **Step 4: Run hygiene tests**

Run the same focused pytest.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Check evidence cache git hygiene"
```

## Chunk 9: Publish Allowlist and Exact Staging

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: publish allowlist, exclusions, porcelain parsing, and publish decision.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: path classification and decision tests.

### Task 9: Publish Allowlist and Exact Staging

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write path classification tests**

Add tests for:

```python
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
        b"R  wiki/old.md\\0wiki/new.md\\0",
        b" R wiki/old.md\\0wiki/new.md\\0",
        b"C  wiki/source.md\\0wiki/copy.md\\0",
        b" C wiki/source.md\\0wiki/copy.md\\0",
    ]:
        with self.subTest(data=data):
            changes = shared.parse_porcelain_z(data)
            self.assertEqual(changes[0].paths, ("wiki/old.md", "wiki/new.md") if b"old" in data else ("wiki/source.md", "wiki/copy.md"))

def test_publish_decision_blocks_mixed_allowed_and_unexpected_paths(self):
    shared = load_shared_update()
    decision = shared.decide_publish_paths([
        shared.GitChange(" M", ("wiki/source.md",)),
        shared.GitChange("??", ("notes.md",)),
    ])
    self.assertEqual(decision.status, "unexpected_local_changes")
    self.assertIn("notes.md", decision.message)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py::SharedUpdateTests::test_classifies_allowed_and_excluded_paths tools/tests/test_shared_update.py::SharedUpdateTests::test_parse_porcelain_z_handles_rename_paths tools/tests/test_shared_update.py::SharedUpdateTests::test_publish_decision_blocks_mixed_allowed_and_unexpected_paths -q
```

Expected: FAIL.

- [ ] **Step 3: Implement path matching and porcelain parsing**

In `shared_update.py`:

```python
INCLUDE_PATTERNS = (
    "kb.manifest.yaml",
    "BUSINESS_CONTEXT.md",
    "upstream/**",
    "wiki/**",
    "docs/retrieval-playbook.md",
    "docs/build-and-maintenance.md",
    "docs/implementation-workflow.md",
    "docs/query-acceptance.md",
    "docs/*quality-audit*.md",
    "docs/*tooling*.md",
    "staging/update/latest.*",
    "staging/refinement-status.md",
    "staging/refinement-plan.json",
    "staging/source-manifest.json",
    "staging/code-graph/**",
    "staging/traceability/**",
    "graph/**",
    "index/**",
)
EXCLUDE_PATTERNS = (
    "raw/**",
    "raw-code/**",
    ".llm-wiki/**",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*.cookie",
    "*.cookies",
    "*cookie*",
    "*token*",
    "*secret*",
    "*.log",
    ".venv/**",
    "venv/**",
    "node_modules/**",
)

@dataclass
class GitChange:
    status: str
    paths: tuple[str, ...]

@dataclass
class PublishDecision:
    status: str
    paths: tuple[str, ...] = ()
    message: str = ""

def is_publish_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    parts = normalized.split("/")
    for pattern in EXCLUDE_PATTERNS:
        if "/" not in pattern and any(fnmatch.fnmatchcase(part, pattern) for part in parts):
            return False
        if "/" in pattern and fnmatch.fnmatchcase(normalized, pattern):
            return False
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in INCLUDE_PATTERNS)

def parse_porcelain_z(data: bytes) -> list[GitChange]:
    parts = [part.decode("utf-8") for part in data.split(b"\0") if part]
    changes: list[GitChange] = []
    index = 0
    while index < len(parts):
        item = parts[index]
        status = item[:2]
        first_path = item[3:]
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            index += 1
            changes.append(GitChange(status, (first_path, parts[index])))
        else:
            changes.append(GitChange(status, (first_path,)))
        index += 1
    return changes

def decide_publish_paths(changes: list[GitChange]) -> PublishDecision:
    allowed: list[str] = []
    unexpected: list[str] = []
    for change in changes:
        if all(is_publish_allowed(path) for path in change.paths):
            allowed.extend(change.paths)
        else:
            unexpected.extend(change.paths)
    if unexpected:
        return PublishDecision(
            "unexpected_local_changes",
            message="发现共享发布范围外的本地改动，请先处理后重试：" + ", ".join(unexpected),
        )
    return PublishDecision("ok", tuple(dict.fromkeys(allowed)))
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Add managed publish path checks"
```

## Chunk 10: Shared and Local Preflight

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: local/shared preflight, divergence, ahead recovery, fallback prompt.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: preflight state tests.

### Task 10: Shared and Local Preflight

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write preflight tests**

Add tests:

```python
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
            project, no_auto_raw_sync=False, interactive=True,
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

```

- [ ] **Step 2: Run base preflight tests to verify they fail**

Run the focused pytest command for the tests above.

Expected: FAIL.

- [ ] **Step 3: Implement base preflight helpers**

Implement `local_preflight`, `is_git_repo`, `git_status_dirty`, `current_upstream`, `read_divergence`, `local_mode_offer`, and shared-mode checks through fetch/diverged/behind pull. Local mode returns `ok` with a Chinese warning for non-git projects. For git repos, both local and shared preflight call `check_evidence_cache_hygiene(project)` before the general dirty-worktree check. Pull failures must classify permission vs non-permission; interactive failures return `offer_local_mode`, while noninteractive failures return `shared_sync_failed` without the confirmation prompt. Do not implement ahead-only recovery in this task; return `ahead_unrecognized_commits` for any ahead-only state temporarily.

- [ ] **Step 4: Run base preflight tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Add shared update base preflight"
```

## Chunk 11: Recognized Ahead Recovery

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: recognized unpublished update commit detection and ahead-only recovery push.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: ahead-only recovery tests.

### Task 11: Recognized Ahead Recovery

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write ahead recovery tests**

Add tests:

```python
def test_shared_mode_ahead_unrecognized_commits_stop(self):
    shared = load_shared_update()
    with tempfile.TemporaryDirectory() as tmp:
        project, remote = make_repo_with_remote(Path(tmp))
        result = shared.shared_preflight(
            project, no_auto_raw_sync=False, interactive=False,
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
        result = shared.shared_preflight(project, False, False, git_runner=fake_git, divergence_reader=lambda cwd, upstream: (1, 0), ahead_is_recognized=lambda cwd, upstream: True)
        self.assertEqual(result.status, "unpublished_local_baseline")
        self.assertNotIn("写入权限", result.message)

def test_shared_mode_blocks_remaining_divergence_after_recognized_push(self):
    shared = load_shared_update()
    with tempfile.TemporaryDirectory() as tmp:
        project, remote = make_repo_with_remote(Path(tmp))
        states = iter([(1, 0), (1, 1)])
        result = shared.shared_preflight(
            project, no_auto_raw_sync=False, interactive=False,
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
        result = shared.shared_preflight(project, False, False, git_runner=fake_git, divergence_reader=lambda cwd, upstream: next(states), ahead_is_recognized=lambda cwd, upstream: True)
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
```

- [ ] **Step 2: Run ahead recovery tests to verify they fail**

Run the focused pytest command for the ahead recovery tests from Step 1.

Expected: FAIL.

- [ ] **Step 3: Implement recognized ahead recovery**

Implement `recognized_update_commits_only(project, upstream)` so every ahead commit has subject `Update <kb-name> knowledge base`, every ahead commit body contains `Actor: local-skill` or `Actor: gateway`, and the combined diff touches only publish-allowed paths. In `shared_preflight`, ahead-only recognized commits are pushed; push permission failures mention KB write permission, non-permission failures use generic unpublished-baseline guidance, then fetch and re-check divergence. If the post-push state is behind-only, run `git pull --ff-only` before returning `ok`; if it is diverged or still ahead, stop with the appropriate Chinese terminal message.

- [ ] **Step 4: Run ahead recovery tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Recover recognized shared update commits"
```

## Chunk 12: Publish Shared Baseline

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: exact staging, commit, push, and publish result messages.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: publish behavior and failure tests.

### Task 12: Publish Shared Baseline

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write publish tests**

Add tests for:

```python
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
        result = shared.publish_shared_baseline(project, actor="local-skill", status_runner=lambda args, cwd: shared.GitBytesResult(128, b"", "fatal: status failed"))
        self.assertEqual(result.status, "shared_sync_failed")
        self.assertNotEqual(result.status, "no_changes")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py::SharedUpdateTests::test_publish_no_changes_returns_no_changes tools/tests/test_shared_update.py::SharedUpdateTests::test_publish_commits_allowlisted_changes_with_actor tools/tests/test_shared_update.py::SharedUpdateTests::test_commit_failed_dirty_result_blocks_next_local_and_shared_preflight tools/tests/test_shared_update.py::SharedUpdateTests::test_push_permission_failure_mentions_write_permission tools/tests/test_shared_update.py::SharedUpdateTests::test_publish_status_failure_fails_closed -q
```

Expected: FAIL.

- [ ] **Step 3: Implement publish helper**

Add these structures and helper:

```python
@dataclass
class PublishResult:
    status: str
    message: str = ""

@dataclass
class GitBytesResult:
    returncode: int
    stdout: bytes = b""
    stderr: str = ""

def run_git_bytes(args: list[str], cwd: Path) -> GitBytesResult:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    return GitBytesResult(result.returncode, result.stdout, result.stderr.decode("utf-8", errors="replace"))
```

Then add:

```python
def publish_shared_baseline(project: Path, actor: str = "local-skill", git_runner=run_git, status_runner=run_git_bytes) -> PublishResult:
    status = status_runner(["status", "--porcelain=v1", "-z"], cwd=project)
    if status.returncode != 0:
        return PublishResult("shared_sync_failed", "读取 git 状态失败，未发布共享 KB。请检查本地仓库状态后重试。")
    changes = parse_porcelain_z(status.stdout)
    decision = decide_publish_paths(changes)
    if decision.status != "ok":
        return PublishResult(decision.status, decision.message)
    if not decision.paths:
        return PublishResult("no_changes", "共享 KB 没有需要发布的变更。")
    add = git_runner(["add", "--", *decision.paths], cwd=project)
    if add.returncode != 0:
        return PublishResult("stage_failed_dirty_result", "暂存共享 KB 变更失败，未发布任何文件。请检查本地工作区状态后重试。")
    commit = git_runner([
        "commit",
        "-m", f"Update {project.name} knowledge base",
        "-m", f"Actor: {actor}",
    ], cwd=project)
    if commit.returncode != 0:
        return PublishResult("commit_failed_dirty_result", "提交共享 KB 失败，本地工作区可能保留了已暂存变更。请先处理后重试。")
    push = git_runner(["push"], cwd=project)
    if push.returncode != 0:
        permission = classify_git_permission(push.stderr, "push")
        if permission == "write_permission":
            return PublishResult("unpublished_local_baseline", "共享 KB 已在本地提交，但推送失败：缺少写入权限。请先获取 KB 仓库权限后执行 git push。")
        return PublishResult("unpublished_local_baseline", "共享 KB 已在本地提交，但推送失败。请检查网络、仓库地址或 Git 凭证后重试。")
    return PublishResult("published", "共享 KB 已发布。")
```

Do not use broad globs in `git add`.

- [ ] **Step 4: Run publish tests**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Publish managed KB outputs safely"
```

## Chunk 13: Shared Orchestration Entry Points

### File Structure

- Modify `skills/llm-wiki/assets/project-template/tools/shared_update.py`: mode resolution and wrapper entry points used by skill/gateway.
- Modify `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`: sequencing tests.

### Task 13: Shared Orchestration Entry Points

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/shared_update.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py`

- [ ] **Step 1: Write mode and sequencing tests**

Add tests:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests/test_shared_update.py::SharedUpdateTests::test_resolve_update_mode_defaults_to_shared tools/tests/test_shared_update.py::SharedUpdateTests::test_shared_protocol_rejects_skip_flags_before_update_callback tools/tests/test_shared_update.py::SharedUpdateTests::test_shared_protocol_does_not_publish_before_semantic_callback_finishes tools/tests/test_shared_update.py::SharedUpdateTests::test_accept_local_fallback_restarts_local_preflight -q
```

Expected: FAIL.

- [ ] **Step 3: Implement orchestration primitives without editing `update_wiki.py`**

Add:

```python
def resolve_update_mode(local_flag: bool, shared_flag: bool, env: dict[str, str] | None = None) -> str:
    values = os.environ if env is None else env
    if local_flag or values.get("LLM_WIKI_UPDATE_MODE") == "local":
        return "local"
    return "shared"

def raw_sync_skipped(no_auto_raw_sync: bool, env: dict[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return no_auto_raw_sync or values.get("LLM_WIKI_NO_AUTO_RAW_SYNC") == "1"

def begin_update(project: Path, mode: str, no_auto_raw_sync: bool, interactive: bool, update_callback, env: dict[str, str] | None = None) -> PreflightResult:
    skipped = raw_sync_skipped(no_auto_raw_sync, env)
    preflight = shared_preflight(project, skipped, interactive) if mode == "shared" else local_preflight(project)
    if preflight.status != "ok":
        return preflight
    code = update_callback()
    return PreflightResult("ok" if code == 0 else "validation_failed", "" if code == 0 else "确定性更新失败，未发布共享 KB。")

def accept_local_fallback(project: Path, local_preflight_fn=local_preflight, update_callback=None) -> PreflightResult:
    preflight = local_preflight_fn(project)
    if preflight.status != "ok":
        return preflight
    code = update_callback() if update_callback else 0
    return PreflightResult("ok" if code == 0 else "validation_failed")

def complete_shared_update(project: Path, semantic_validation, publisher=publish_shared_baseline) -> PublishResult:
    validation = semantic_validation()
    if validation.status != "ok":
        return validation
    return publisher(project)
```

These helpers are called by the skill/gateway wrapper. `tools/update_wiki.py` remains the deterministic builder; it does not own git preflight, local fallback, semantic refinement, or publish.

- [ ] **Step 4: Run mode and sequencing tests**

Run the focused pytest command from Step 2.

Expected: PASS.

- [ ] **Step 5: Run full project-template tests**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/shared_update.py skills/llm-wiki/assets/project-template/tools/tests/test_shared_update.py
git commit -m "Add shared update orchestration primitives"
```

## Chunk 14: Skill Protocol and Distribution

### File Structure

- Modify `skills/llm-wiki-update/SKILL.md`: short-entry instructions for shared mode, Chinese prompts, permission failures, local mode, and evidence skip rules.
- Modify `skills/llm-wiki/references/commands.md`: full command protocol for shared update.
- Modify `skills/llm-wiki/assets/project-template/docs/implementation-workflow.md`: document `upstream/code-sources.json`, shared update default, and local mode.
- Modify `INSTRUCTION_AND_RELEASE_PLAN.md`: release note and update contract summary.
- Optionally refresh `dist/` only if this repo expects committed distribution artifacts; otherwise leave `dist/` unchanged and mention release packaging as a follow-up.

### Task 14: Update Skill Documentation

**Files:**
- Modify: `skills/llm-wiki-update/SKILL.md`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify: `skills/llm-wiki/assets/project-template/docs/implementation-workflow.md`
- Modify: `INSTRUCTION_AND_RELEASE_PLAN.md`

- [ ] **Step 1: Patch `$llm-wiki-update` short entry**

Add a new rule near the current update command instructions:

```markdown
默认协作模式：`llm-wiki update` 默认先同步共享 KB git 基线，再恢复 `raw/` / `raw-code/` 证据缓存，完成更新和校验后发布共享 KB 产物。只有用户显式使用 `--local` 或 `LLM_WIKI_UPDATE_MODE=local` 时，才跳过 pull/push。共享模式不得使用 `--no-auto-raw-sync` 或 `LLM_WIKI_NO_AUTO_RAW_SYNC=1` 发布基线。
```

Also include Chinese permission guidance:

```markdown
如果 `git pull` / `git push` 因权限失败，中文说明缺少读取/写入权限，并提示用户申请仓库权限或检查 SSH Key / Git 凭证。
```

- [ ] **Step 2: Patch `commands.md` update section**

Add:

- shared mode is default
- local mode explicit only
- evidence skip flags local-only
- `upstream/code-sources.json` restores `raw-code/`
- publish allowlist excludes `raw/` and `raw-code/`
- failure taxonomy and Chinese prompts

- [ ] **Step 3: Patch template implementation workflow**

Document:

```text
upstream/wiki-sources.json -> raw/
upstream/code-sources.json -> raw-code/
llm-wiki update -> shared by default
llm-wiki update --local -> local-only trial
```

- [ ] **Step 4: Patch release plan**

Add a short section under update rules describing shared baseline behavior and local fallback.

- [ ] **Step 5: Run documentation grep checks**

Run:

```bash
rg -n "shared|共享|--local|code-sources|no-auto-raw-sync|权限" skills/llm-wiki-update/SKILL.md skills/llm-wiki/references/commands.md skills/llm-wiki/assets/project-template/docs/implementation-workflow.md INSTRUCTION_AND_RELEASE_PLAN.md
```

Expected: output shows all new protocol concepts.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki-update/SKILL.md skills/llm-wiki/references/commands.md skills/llm-wiki/assets/project-template/docs/implementation-workflow.md INSTRUCTION_AND_RELEASE_PLAN.md
git commit -m "Document shared update mode"
```

### Task 15: Final Verification

**Files:**
- No direct edits unless verification reveals issues.

- [ ] **Step 1: Run install tests**

Run:

```bash
bash tests/install_test.sh
```

Expected: `install tests passed`.

- [ ] **Step 2: Run installer unit tests**

Run:

```bash
python -m pytest skills/llm-wiki/scripts/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run template tool tests**

Run:

```bash
cd skills/llm-wiki/assets/project-template
uv run pytest tools/tests -q
```

Expected: PASS.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: clean.

- [ ] **Step 5: Summarize implementation**

Report:

- commits created
- tests run and results
- any dist packaging not refreshed
- exact local mode and shared mode behavior now implemented
