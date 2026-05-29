# Maintain-All Registry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local KB project registry and an explicit `llm-wiki maintain-all` flow that can dry-run or apply full backfill maintenance across registered KBs.

**Architecture:** Add shared registry logic in the installed skill scripts, expose a batch runner from the skill, and add a small project-template registry helper so existing project-local `update_wiki.py` and `backfill.py` can best-effort register themselves. Keep batch maintenance explicit and dry-run by default; `--apply` is the only path that refreshes project tools or runs project backfill/update commands.

**Tech Stack:** Python 3.10+ standard library, existing Bash `install.sh`, existing `unittest` style under `skills/llm-wiki/scripts/tests` and `skills/llm-wiki/assets/project-template/tools/tests`, local JSON/Markdown reports.

---

## File Structure

- Create: `skills/llm-wiki/scripts/project_registry.py`
  - Owns `~/.llm-wiki/projects.json` read/write, KB detection, registration, discovery, reconcile, pruning, and dirty-git checks for the skill-side batch runner.
- Create: `skills/llm-wiki/scripts/maintain_all.py`
  - CLI entrypoint for `llm-wiki maintain-all`; builds dry-run plans, applies full backfill flow per KB, writes batch reports, and updates registry status.
- Create: `skills/llm-wiki/scripts/tests/test_project_registry.py`
  - Unit tests for registry idempotency, discovery, missing pruning, list rows, and dirty-git checks.
- Create: `skills/llm-wiki/scripts/tests/test_maintain_all.py`
  - Unit/integration-style tests using temporary fake KBs to verify dry-run and apply sequencing.
- Create: `skills/llm-wiki-maintain-all/SKILL.md`
  - Short skill entrypoint for users to invoke batch maintenance.
- Create: `skills/llm-wiki-maintain-all/agents/openai.yaml`
  - Agent metadata/default prompt for the new command skill.
- Modify: `skills/llm-wiki/scripts/install_project_template.py`
  - Best-effort register the target project after template install/refresh.
- Modify: `skills/llm-wiki/scripts/update_installed_skill.py`
  - Suggest `llm-wiki maintain-all` after successful skill update; do not run it automatically.
- Create: `skills/llm-wiki/assets/project-template/tools/project_registry.py`
  - Project-local best-effort registry helper for copied KB tools.
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
  - Best-effort register current KB at start of update.
- Modify: `skills/llm-wiki/assets/project-template/tools/backfill.py`
  - Best-effort register current KB at start of backfill.
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`
  - Verify update registration is attempted without blocking update behavior.
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_backfill.py`
  - Verify backfill registration is attempted without blocking backfill behavior.
- Modify: `README.md`, `skills/llm-wiki/README.md`, `skills/llm-wiki/SKILL.md`, `skills/llm-wiki/references/commands.md`
  - Document registry, discovery, dry-run/apply, pruning, and safety boundaries.
- Modify: `tests/install_test.sh`
  - Verify `llm-wiki-maintain-all` is installed.
- Modify: `dist/llm-wiki-skill/...`
  - Sync modified skill directories and project-template files into dist after source-side tests pass.

## Chunk 1: Skill-Side Registry Core

### Task 1: Add registry read/write and idempotent registration

**Files:**
- Create: `skills/llm-wiki/scripts/tests/test_project_registry.py`
- Create: `skills/llm-wiki/scripts/project_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `skills/llm-wiki/scripts/tests/test_project_registry.py`:

```python
import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def load_script_module(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProjectRegistryTest(unittest.TestCase):
    def test_register_project_is_idempotent_and_preserves_first_seen(self):
        registry = load_script_module("project_registry")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb = root / "demo-kb"
            kb.mkdir()
            (kb / "kb.manifest.yaml").write_text("version: 1\n", encoding="utf-8")
            tools = kb / "tools"
            tools.mkdir()
            (tools / "update_wiki.py").write_text("# update\n", encoding="utf-8")
            registry_path = root / "projects.json"

            first = registry.register_project(kb, registry_path=registry_path, now="2026-05-29T01:00:00+00:00")
            second = registry.register_project(kb, registry_path=registry_path, now="2026-05-29T02:00:00+00:00")

            self.assertEqual(first["path"], str(kb.resolve()))
            self.assertEqual(second["first_seen_at"], "2026-05-29T01:00:00+00:00")
            self.assertEqual(second["last_seen_at"], "2026-05-29T02:00:00+00:00")
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["status"], "active")
            self.assertEqual(payload["projects"][0]["missing_count"], 0)
```

Use this local loader pattern instead of package imports because `skills/llm-wiki` contains a hyphen.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_project_registry.py -v
```

Expected: FAIL because `project_registry.py` does not exist or does not expose `register_project`.

- [ ] **Step 3: Implement minimal registry module**

Create `skills/llm-wiki/scripts/project_registry.py` with these public functions:

```python
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTRY_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_registry_path() -> Path:
    return Path(os.environ.get("LLM_WIKI_PROJECT_REGISTRY", "~/.llm-wiki/projects.json")).expanduser()


def empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "projects": []}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_registry_path()
    if not registry_path.is_file():
        return empty_registry()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return empty_registry()
    if not isinstance(payload, dict):
        return empty_registry()
    projects = payload.get("projects")
    if not isinstance(projects, list):
        projects = []
    return {"version": int(payload.get("version") or REGISTRY_VERSION), "projects": projects}


def save_registry(payload: dict[str, Any], path: Path | None = None) -> None:
    registry_path = path or default_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_kb_project(path: Path) -> bool:
    root = path.resolve()
    if (root / "kb.manifest.yaml").is_file() and (root / "tools" / "update_wiki.py").is_file():
        return True
    return (root / "BUSINESS_CONTEXT.md").is_file() and (root / "wiki").is_dir() and (root / "staging").is_dir()


def register_project(project: Path, *, registry_path: Path | None = None, now: str | None = None) -> dict[str, Any]:
    seen_at = now or utc_now()
    root = project.resolve()
    payload = load_registry(registry_path)
    projects = list(payload.get("projects") or [])
    existing = next((item for item in projects if item.get("path") == str(root)), None)
    if existing is None:
        existing = {
            "path": str(root),
            "name": root.name,
            "first_seen_at": seen_at,
            "last_seen_at": seen_at,
            "last_success_at": "",
            "status": "active",
            "missing_count": 0,
            "last_error": "",
        }
        projects.append(existing)
    else:
        existing.setdefault("first_seen_at", seen_at)
        existing["name"] = existing.get("name") or root.name
        existing["last_seen_at"] = seen_at
        existing["status"] = "active"
        existing["missing_count"] = 0
        existing["last_error"] = ""
    payload["projects"] = sorted(projects, key=lambda item: str(item.get("path") or ""))
    save_registry(payload, registry_path)
    return existing
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_project_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/project_registry.py skills/llm-wiki/scripts/tests/test_project_registry.py
git commit -m "feat: add llm-wiki project registry"
```

### Task 2: Add discovery, reconcile, prune, and list rows

**Files:**
- Modify: `skills/llm-wiki/scripts/project_registry.py`
- Modify: `skills/llm-wiki/scripts/tests/test_project_registry.py`

- [ ] **Step 1: Write failing discovery and pruning tests**

Add tests for:

- `discover_projects(root)` finds a strong KB with `kb.manifest.yaml` + `tools/update_wiki.py`.
- `discover_projects(root)` finds a legacy KB with `BUSINESS_CONTEXT.md` + `wiki/` + `staging/`.
- Discovery does not descend into `raw/`, `raw-code/`, `wiki/`, `staging/`, `.git`, `.venv`, `node_modules`, `.worktrees`, or `worktrees`.
- `reconcile_registry()` marks a missing path as `missing` and increments `missing_count`.
- After the third missing reconcile, the entry is removed.
- `prune_missing()` removes missing paths immediately.
- `registry_rows()` returns stable display rows.
- `git_worktree_dirty(path)` returns `True` for a dirty git worktree and `False` for clean worktrees or non-git directories.

The automatic prune threshold is `missing_count >= 3`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_project_registry.py -v
```

Expected: FAIL because discovery and reconcile functions are missing.

- [ ] **Step 3: Implement discovery and reconcile**

Add these public functions:

```python
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "raw", "raw-code", "wiki", "staging", ".worktrees", "worktrees"}


def discover_projects(root: Path) -> list[Path]:
    found: list[Path] = []
    stack = [root.resolve()]
    while stack:
        current = stack.pop()
        if is_kb_project(current):
            found.append(current)
            continue
        try:
            children = sorted(path for path in current.iterdir() if path.is_dir())
        except OSError:
            continue
        for child in children:
            if child.name in SKIP_DIR_NAMES:
                continue
            stack.append(child)
    return sorted(set(found))


def reconcile_registry(*, registry_path: Path | None = None, now: str | None = None) -> dict[str, Any]:
    payload = load_registry(registry_path)
    kept = []
    removed = []
    for item in payload.get("projects") or []:
        path = Path(str(item.get("path") or "")).expanduser()
        if path.exists() and is_kb_project(path):
            item["status"] = "active"
            item["missing_count"] = 0
            item["last_seen_at"] = now or utc_now()
            item["last_error"] = ""
            kept.append(item)
        elif path.exists():
            item["status"] = "failed"
            item["last_error"] = "path_exists_but_not_kb"
            kept.append(item)
        else:
            item["status"] = "missing"
            item["missing_count"] = int(item.get("missing_count") or 0) + 1
            if item["missing_count"] >= 3:
                removed.append(item)
            else:
                kept.append(item)
    payload["projects"] = kept
    save_registry(payload, registry_path)
    return {"registry": payload, "removed": removed}


def prune_missing(*, registry_path: Path | None = None) -> list[dict[str, Any]]:
    ...


def registry_rows(*, registry_path: Path | None = None) -> list[dict[str, str]]:
    ...


def git_worktree_dirty(path: Path) -> bool:
    ...
```

Keep `prune_missing()` and `registry_rows()` small and deterministic. Implement `git_worktree_dirty()` with `git rev-parse --is-inside-work-tree` and `git status --porcelain`, returning `False` when the path is not a git worktree.

- [ ] **Step 4: Run registry tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_project_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/project_registry.py skills/llm-wiki/scripts/tests/test_project_registry.py
git commit -m "feat: discover registered llm-wiki projects"
```

## Chunk 2: Batch Maintain-All Runner

### Task 3: Add dry-run plan generation

**Files:**
- Create: `skills/llm-wiki/scripts/tests/test_maintain_all.py`
- Create: `skills/llm-wiki/scripts/maintain_all.py`

- [ ] **Step 1: Write failing dry-run tests**

Create tests that:

- build a temp registry with one active KB, one missing KB, and one failed KB
- call `maintain_all.build_plan(registry_path=...)`
- assert only active KBs are `planned`
- assert missing/failed KBs are skipped with reasons
- assert active KBs with dirty project git worktrees are skipped with reason `dirty_project_worktree`
- assert dry-run does not create or modify files inside the KB

Use temp KBs with `kb.manifest.yaml` and `tools/update_wiki.py`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: FAIL because `maintain_all.py` does not exist.

- [ ] **Step 3: Implement minimal plan builder**

Create `skills/llm-wiki/scripts/maintain_all.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import project_registry

SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]


def build_plan(*, registry_path: Path | None = None, projects: list[str] | None = None, names: list[str] | None = None) -> dict[str, Any]:
    reconcile = project_registry.reconcile_registry(registry_path=registry_path)
    registry = reconcile["registry"]
    selected = []
    skipped = []
    for item in registry.get("projects") or []:
        path = str(item.get("path") or "")
        name = str(item.get("name") or "")
        if projects and path not in projects:
            continue
        if names and name not in names:
            continue
        status = item.get("status")
        if status != "active":
            skipped.append({"project": path, "status": "skipped", "reason": status or "not_active"})
            continue
        if project_registry.git_worktree_dirty(Path(path)):
            skipped.append({"project": path, "status": "skipped", "reason": "dirty_project_worktree"})
            continue
        selected.append({
            "project": path,
            "status": "planned",
            "commands": [
                f"python3 {SKILL_ROOT / 'scripts' / 'install_project_template.py'} --project {path} --engine-only --refresh-agent-rules",
                "uv run python tools/backfill.py",
            ],
        })
    return {"planned": selected, "skipped": skipped, "removed": reconcile.get("removed", [])}
```

- [ ] **Step 4: Run dry-run tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: PASS for dry-run tests.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/maintain_all.py skills/llm-wiki/scripts/tests/test_maintain_all.py
git commit -m "feat: plan batch llm-wiki maintenance"
```

### Task 4: Add apply flow, reports, and continue-on-failure

**Files:**
- Modify: `skills/llm-wiki/scripts/maintain_all.py`
- Modify: `skills/llm-wiki/scripts/tests/test_maintain_all.py`

- [ ] **Step 1: Write failing apply tests**

Add tests using fake KB scripts:

- Fake KB has executable `tools/backfill.py` that writes `staging/backfill/latest.json`.
- Fake KB has executable `tools/update_wiki.py` that writes `staging/update/latest.json`.
- Patch `maintain_all.SKILL_ROOT` to a temp skill root containing `scripts/install_project_template.py`.
- `run_apply()` invokes install template, then backfill, then update when backfill JSON has `refinement_absorption_required=true`.
- If first KB fails, second KB still runs.
- JSON and Markdown batch reports are written under a temp `maintenance-runs` dir.
- Registry `last_success_at` updates only on successful KBs; failed KBs get `status=failed` and `last_error`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: FAIL because apply/report functions are missing.

- [ ] **Step 3: Implement apply helpers**

Add:

```python
def default_runs_dir() -> Path:
    return Path(os.environ.get("LLM_WIKI_MAINTENANCE_RUNS_DIR", "~/.llm-wiki/maintenance-runs")).expanduser()


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return result.returncode, result.stdout


def run_project(plan_item: dict[str, Any]) -> dict[str, Any]:
    project = Path(str(plan_item["project"]))
    install = [sys.executable, str(SKILL_ROOT / "scripts" / "install_project_template.py"), "--project", str(project), "--engine-only", "--refresh-agent-rules"]
    code, output = run_command(install, project)
    if code != 0:
        return {"project": str(project), "status": "failed", "reason": "install_project_template", "output": output}
    code, output = run_command(["uv", "run", "python", "tools/backfill.py"], project)
    if code != 0:
        fallback_code, fallback_output = run_command([sys.executable, "tools/backfill.py"], project)
        if fallback_code != 0:
            return {"project": str(project), "status": "failed", "reason": "backfill", "output": output + fallback_output}
    backfill_report = project / "staging" / "backfill" / "latest.json"
    absorption_required = False
    if backfill_report.is_file():
        try:
            absorption_required = bool(json.loads(backfill_report.read_text(encoding="utf-8")).get("refinement_absorption_required"))
        except Exception:
            absorption_required = False
    if absorption_required:
        code, output = run_command(["uv", "run", "python", "tools/update_wiki.py"], project)
        if code != 0:
            fallback_code, fallback_output = run_command([sys.executable, "tools/update_wiki.py"], project)
            if fallback_code != 0:
                return {"project": str(project), "status": "failed", "reason": "update", "output": output + fallback_output}
    return {"project": str(project), "status": "success", "backfill_report": str(backfill_report)}
```

Then implement `run_apply(plan, registry_path, runs_dir)` and `write_run_reports(run_id, results, runs_dir)`.

Keep subprocess output in reports concise; truncate very large command output to a reasonable limit such as 20,000 characters.

- [ ] **Step 4: Run apply tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/maintain_all.py skills/llm-wiki/scripts/tests/test_maintain_all.py
git commit -m "feat: apply batch llm-wiki maintenance"
```

### Task 5: Add CLI flags and console output

**Files:**
- Modify: `skills/llm-wiki/scripts/maintain_all.py`
- Modify: `skills/llm-wiki/scripts/tests/test_maintain_all.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests for `main(argv)` using temp registry paths:

- `--list` prints active/missing rows and exits `0`.
- `--prune-missing` removes missing paths and exits `0`.
- `--discover <dir>` registers discovered KBs.
- default invocation prints a dry-run plan and does not apply.
- `--apply` invokes apply path.
- `--project <path>` and `--name <name>` filter selection.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: FAIL until CLI behavior exists.

- [ ] **Step 3: Implement CLI**

Add `parse_args()` and `main(argv=None)`:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Maintain registered local LLM Wiki KB projects.")
    parser.add_argument("--registry", help="Override registry path for tests or advanced local use.")
    parser.add_argument("--discover", action="append", default=[], help="Discover KB projects under this directory.")
    parser.add_argument("--list", action="store_true", help="List registered KB projects.")
    parser.add_argument("--prune-missing", action="store_true", help="Immediately remove registry entries whose paths no longer exist.")
    parser.add_argument("--apply", action="store_true", help="Apply the planned maintenance. Without this flag, only prints a dry-run plan.")
    parser.add_argument("--project", action="append", default=[], help="Only include this absolute KB path.")
    parser.add_argument("--name", action="append", default=[], help="Only include projects with this registered name.")
    return parser.parse_args(argv)
```

Main order:

1. Resolve registry path.
2. Register discoveries.
3. Reconcile/prune/list if requested.
4. Build plan.
5. Print dry-run plan.
6. If `--apply`, execute and print final summary.

Do not prompt interactively in the first implementation; `--apply` is explicit confirmation.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_maintain_all.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/maintain_all.py skills/llm-wiki/scripts/tests/test_maintain_all.py
git commit -m "feat: add maintain-all cli"
```

## Chunk 3: Project-Local Auto Registration

### Task 6: Add project-template registry helper

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/project_registry.py`
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_project_registry.py`

- [ ] **Step 1: Write failing project-template registry tests**

Create tests that:

- `register_current_project(project, registry_path=...)` writes the same registry shape as the skill-side helper.
- register is idempotent.
- write failures are swallowed by `best_effort_register_current_project(project)`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_project_registry.py -v
```

Expected: FAIL because project-template `tools/project_registry.py` does not exist.

- [ ] **Step 3: Implement compact project helper**

Create a small copy-oriented helper with no dependency on installed skill paths:

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_registry_path() -> Path:
    return Path(os.environ.get("LLM_WIKI_PROJECT_REGISTRY", "~/.llm-wiki/projects.json")).expanduser()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def register_current_project(project: Path, *, registry_path: Path | None = None, now: str | None = None) -> dict[str, Any]:
    ...


def best_effort_register_current_project(project: Path) -> None:
    try:
        register_current_project(project)
    except Exception as exc:
        print(f"registry_warning={exc}", file=sys.stderr)
```

Use the same entry fields as the skill-side registry. Keep this helper intentionally duplicated rather than importing from an installed skill path, because project tools are copied into arbitrary KBs.

- [ ] **Step 4: Run project registry tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_project_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/project_registry.py skills/llm-wiki/assets/project-template/tools/tests/test_project_registry.py
git commit -m "feat: register project-local llm-wiki tools"
```

### Task 7: Register from install, update, and backfill

**Files:**
- Modify: `skills/llm-wiki/scripts/install_project_template.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/backfill.py`
- Modify: `skills/llm-wiki/scripts/tests/test_install_project_template.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_backfill.py`

- [ ] **Step 1: Write failing tests for automatic registration**

Add tests:

- `install_project_template.py --project <kb>` writes registry entry when `LLM_WIKI_PROJECT_REGISTRY` points to a temp file.
- `tools/update_wiki.py` calls `best_effort_register_current_project(project)` before update work. Patch the function and assert it was called.
- `tools/backfill.py` calls `best_effort_register_current_project(project)` before pass execution. Patch the function and assert it was called.
- If registry writing fails, update/backfill behavior still continues.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_install_project_template.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py skills/llm-wiki/assets/project-template/tools/tests/test_backfill.py -v
```

Expected: FAIL until registration hooks exist.

- [ ] **Step 3: Implement install registration**

In `install_project_template.py`, import the skill-side `project_registry` helper and call it near the end of `main()` after `project` is resolved and created:

```python
try:
    from project_registry import register_project

    register_project(project)
    registry_status = "registered"
except Exception as exc:
    registry_status = f"warning:{exc}"
```

Print `registry=<status>` in the command output.

- [ ] **Step 4: Implement update/backfill registration**

In project-template `tools/update_wiki.py` and `tools/backfill.py`, import:

```python
from project_registry import best_effort_register_current_project
```

Call `best_effort_register_current_project(project)` once after resolving `project`.

If an import conflict is possible in tests, insert the tools directory into `sys.path` using the existing local pattern before importing.

- [ ] **Step 5: Run registration tests**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_install_project_template.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py skills/llm-wiki/assets/project-template/tools/tests/test_backfill.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki/scripts/install_project_template.py skills/llm-wiki/scripts/tests/test_install_project_template.py skills/llm-wiki/assets/project-template/tools/project_registry.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/backfill.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py skills/llm-wiki/assets/project-template/tools/tests/test_backfill.py
git commit -m "feat: auto-register llm-wiki projects"
```

## Chunk 4: Skill Entrypoint, Docs, and Install Packaging

### Task 8: Add `llm-wiki-maintain-all` skill entrypoint

**Files:**
- Create: `skills/llm-wiki-maintain-all/SKILL.md`
- Create: `skills/llm-wiki-maintain-all/agents/openai.yaml`
- Modify: `tests/install_test.sh`
- Modify: `README.md`

- [ ] **Step 1: Write failing install test**

Modify `tests/install_test.sh` to assert:

```bash
assert_contains "would copy llm-wiki-maintain-all" "$TMP_DIR/dry-run.out"
assert_file "$home/skills/llm-wiki-maintain-all/SKILL.md"
```

- [ ] **Step 2: Run install test to verify failure**

Run:

```bash
bash tests/install_test.sh
```

Expected: FAIL because the new skill directory does not exist.

- [ ] **Step 3: Create skill files**

Create `skills/llm-wiki-maintain-all/SKILL.md`:

```markdown
---
name: llm-wiki-maintain-all
description: Batch maintain registered local LLM Wiki KB projects. Use when the user wants to discover local KBs, list/prune the KB registry, or run full backfill/update maintenance across registered KBs.
---

# LLM Wiki Maintain All

语言要求：默认用中文回复用户，除非用户明确要求其他语言。

## 目标

用于维护本机多个已注册 LLM Wiki KB 项目。默认只 dry-run 输出计划；只有用户明确要求执行时才运行 `--apply`。

## 常用命令

```bash
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --discover /Users/zhaoliang/guazi/work
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --list
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --apply
python3 "$LLM_WIKI_SKILL_ROOT/scripts/maintain_all.py" --prune-missing
```

## 执行规则

- 先解析当前安装的 `llm-wiki` skill 根目录，不要写死个人路径。
- 默认 dry-run，不修改 KB。
- 用户明确确认后才加 `--apply`。
- Cwiki 鉴权失败、dirty git worktree、raw-code checkout 损坏都必须作为单个 KB 的 blocker 报告，不要静默跳过或加 `--no-auto-raw-sync`。
- 批量执行时一个 KB 失败不阻塞后续 KB。
```

Create `skills/llm-wiki-maintain-all/agents/openai.yaml` matching other short skills:

```yaml
display:
  display_name: "LLM Wiki Maintain All"
  default_prompt: "维护本机已注册的 LLM Wiki KB 项目；先 dry-run 计划，确认后批量 backfill/update。"
```

Update README command table to include `$llm-wiki-maintain-all`.

- [ ] **Step 4: Run install test**

Run:

```bash
bash tests/install_test.sh
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki-maintain-all tests/install_test.sh README.md
git commit -m "feat: add maintain-all skill entrypoint"
```

### Task 9: Document commands and update-skill suggestion

**Files:**
- Modify: `skills/llm-wiki/scripts/update_installed_skill.py`
- Modify: `skills/llm-wiki/README.md`
- Modify: `skills/llm-wiki/SKILL.md`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify: `README.md`
- Modify: `skills/llm-wiki/scripts/tests/test_update_installed_skill.py` if an update-skill test file exists; otherwise create it.

- [ ] **Step 1: Write failing update-skill/docs tests**

If no test exists, create `skills/llm-wiki/scripts/tests/test_update_installed_skill.py` with a simple test that patches `run()` and asserts successful `main()` output contains `maintain-all` guidance.

Also add a docs presence test if this repo has a docs test pattern; otherwise include docs verification in Step 4 with `rg`.

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_update_installed_skill.py -v
```

Expected: FAIL until update-skill prints the suggestion.

- [ ] **Step 3: Update docs and suggestion**

In `update_installed_skill.py`, after successful install command, print:

```text
Installed llm-wiki skill updated. Existing KB projects keep their project-local tools until refreshed.
Run `llm-wiki maintain-all` / `$llm-wiki-maintain-all` to preview batch backfill/update for registered KBs.
```

Update command docs to describe:

- registry path: `~/.llm-wiki/projects.json`
- `--discover`
- `--list`
- `--prune-missing`
- dry-run default
- `--apply`
- safety boundaries

- [ ] **Step 4: Run tests and docs checks**

Run:

```bash
python3 -m unittest skills/llm-wiki/scripts/tests/test_update_installed_skill.py -v
rg -n "maintain-all|projects.json|prune-missing|--discover|--apply" README.md skills/llm-wiki/README.md skills/llm-wiki/SKILL.md skills/llm-wiki/references/commands.md
```

Expected: unittest PASS; `rg` finds the new command language in all listed docs.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/scripts/update_installed_skill.py skills/llm-wiki/scripts/tests/test_update_installed_skill.py README.md skills/llm-wiki/README.md skills/llm-wiki/SKILL.md skills/llm-wiki/references/commands.md
git commit -m "docs: document maintain-all registry workflow"
```

## Chunk 5: Dist Sync and Full Verification

### Task 10: Sync dist artifacts

**Files:**
- Modify/create matching files under `dist/llm-wiki-skill/...`

- [ ] **Step 1: Copy source-side changed files into dist**

Use normal file copy commands, not manual editing, for dist sync:

```bash
rsync -a skills/llm-wiki/scripts/project_registry.py dist/llm-wiki-skill/scripts/project_registry.py
rsync -a skills/llm-wiki/scripts/maintain_all.py dist/llm-wiki-skill/scripts/maintain_all.py
rsync -a skills/llm-wiki/assets/project-template/tools/project_registry.py dist/llm-wiki-skill/assets/project-template/tools/project_registry.py
rsync -a skills/llm-wiki/assets/project-template/tools/update_wiki.py dist/llm-wiki-skill/assets/project-template/tools/update_wiki.py
rsync -a skills/llm-wiki/assets/project-template/tools/backfill.py dist/llm-wiki-skill/assets/project-template/tools/backfill.py
rsync -a skills/llm-wiki-maintain-all dist/
```

Adjust paths if the actual dist layout differs. Do not sync test files into dist unless existing dist already carries tests.

- [ ] **Step 2: Verify source and dist key files match**

Run:

```bash
diff -u skills/llm-wiki/scripts/project_registry.py dist/llm-wiki-skill/scripts/project_registry.py
diff -u skills/llm-wiki/scripts/maintain_all.py dist/llm-wiki-skill/scripts/maintain_all.py
diff -u skills/llm-wiki/assets/project-template/tools/project_registry.py dist/llm-wiki-skill/assets/project-template/tools/project_registry.py
diff -u skills/llm-wiki/assets/project-template/tools/update_wiki.py dist/llm-wiki-skill/assets/project-template/tools/update_wiki.py
diff -u skills/llm-wiki/assets/project-template/tools/backfill.py dist/llm-wiki-skill/assets/project-template/tools/backfill.py
```

Expected: no diff output.

- [ ] **Step 3: Commit**

```bash
git add dist/llm-wiki-skill dist/llm-wiki-maintain-all
git commit -m "chore: sync maintain-all dist artifacts"
```

### Task 11: Run full verification

**Files:**
- No code edits unless verification exposes an issue.

- [ ] **Step 1: Run script-level tests**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/scripts/tests -p 'test_*.py'
```

Expected: PASS.

- [ ] **Step 2: Run project-template tool tests**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected: PASS.

- [ ] **Step 3: Run install tests**

Run:

```bash
bash tests/install_test.sh
```

Expected: `install tests passed`.

- [ ] **Step 4: Compile Python files**

Run:

```bash
python3 -m compileall -q skills/llm-wiki/scripts skills/llm-wiki/assets/project-template/tools dist/llm-wiki-skill
```

Expected: exit code `0`.

- [ ] **Step 5: Manual dry-run smoke test**

Use temp directories so no real KB is modified:

```bash
tmp="$(mktemp -d)"
kb="$tmp/demo-kb"
mkdir -p "$kb/tools"
printf 'version: 1\n' > "$kb/kb.manifest.yaml"
printf '#!/usr/bin/env python3\n' > "$kb/tools/update_wiki.py"
LLM_WIKI_PROJECT_REGISTRY="$tmp/projects.json" python3 skills/llm-wiki/scripts/maintain_all.py --discover "$tmp"
LLM_WIKI_PROJECT_REGISTRY="$tmp/projects.json" python3 skills/llm-wiki/scripts/maintain_all.py --list
```

Expected: first command registers/plans `demo-kb`; second command lists `demo-kb` as active. Remove the temp directory after inspection.

- [ ] **Step 6: Commit any verification fixes**

If verification required fixes:

```bash
git add <fixed-files>
git commit -m "fix: stabilize maintain-all verification"
```

If no fixes were needed, do not create an empty commit.

## Execution Notes

- Do not run `maintain_all.py --apply` against real KB projects during implementation unless the user explicitly asks.
- Do not start local dev servers; this feature is CLI-only.
- Do not change or remove unrelated `.DS_Store` or other untracked files in the main checkout.
- Keep every registry write free of secrets. The registry stores paths and status only.
- If plan execution uses subagents, assign disjoint file ownership:
  - registry core: `skills/llm-wiki/scripts/project_registry.py` and its tests
  - batch runner: `skills/llm-wiki/scripts/maintain_all.py` and its tests
  - project-local registration: project-template tools and tests
  - docs/entrypoint/dist: skills, docs, install test, dist sync
