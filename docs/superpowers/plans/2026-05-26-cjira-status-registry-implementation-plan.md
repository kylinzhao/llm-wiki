# Cjira Status Registry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-page `cjira` and `idea` state tracking so old and new LLM Wiki projects can refresh requirement status during `llm-wiki update` and use that state in query/mapping semantics.

**Architecture:** Add one focused project-template tool, `tools/cjira_registry.py`, that owns extraction, registry persistence, Jira status refresh, and active-to-archive transitions. Wire it into `build_wiki.py` for local signal indexing and into `update_wiki.py` for live status refresh, then expose registry health in `health.py` and state-aware rules in query documentation.

**Tech Stack:** Python 3.10+, standard library, `requests`, existing `unittest` test style, existing Cwiki/Jira auth helpers from `tools/confluence_sync/export_confluence_tree.py`.

---

## File Structure

- Create: `skills/llm-wiki/assets/project-template/tools/cjira_registry.py`
  - Owns `cjira` extraction, `idea` detection, registry merge, Jira issue status lookup, terminal-state classification, and CLI entrypoint.
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py`
  - Unit tests for extraction, status classification, registry transitions, and failed lookup behavior.
- Modify: `skills/llm-wiki/assets/project-template/tools/build_wiki.py`
  - Calls registry extraction after source discovery and before writing status artifacts.
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
  - Runs `cjira_registry.py --refresh` after `build_wiki.py` so active issues are refreshed during normal update.
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
  - Includes registry counts, stale fetches, lookup failures, and low-confidence primary issue selections in health output.
- Modify: `skills/llm-wiki/references/query-logic.md`
  - Adds query behavior for `idea`, `in_progress`, and `frozen` pages.
- Modify: `skills/llm-wiki/references/commands.md`
  - Adds update/doctor/reporting requirements for the registry.
- Modify: `skills/llm-wiki/SKILL.md`
  - Adds the registry as a standard build/update state source.
- Modify: `dist/llm-wiki-skill/...`
  - Only after source-side implementation passes tests, refresh generated distribution artifacts using the repo's existing release/build process if one exists.

## Chunk 1: Registry Core

### Task 1: Add extraction and classification tests

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py`
- Create later in this chunk: `skills/llm-wiki/assets/project-template/tools/cjira_registry.py`

- [ ] **Step 1: Write failing tests for issue extraction**

Add tests that load `cjira_registry.py` like existing template tests:

```python
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]

def load_cjira_registry():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("cjira_registry", TOOLS_DIR / "cjira_registry.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
```

Test cases:

- one revision-table issue becomes `primary_cjira`
- an issue under a `【JIRA 编号】` heading becomes `supporting_cjira`
- multiple primary candidates return `confidence="low"`
- title containing `【IDEA】` returns `idea_flag=True` and `doc_status="idea"`
- semantic idea phrases without a title marker can return `idea_flag=True` with `confidence="medium"`

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: FAIL because `tools/cjira_registry.py` does not exist.

- [ ] **Step 3: Implement minimal extractor**

Create `tools/cjira_registry.py` with these public functions:

```python
ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")
CJIRA_URL_RE = re.compile(r"https?://cjira\.guazi-corp\.com/browse/(?P<key>[A-Z][A-Z0-9_]+-\d+)")

def extract_issue_candidates(text: str) -> list[dict[str, object]]:
    ...

def detect_idea(title: str, text: str) -> dict[str, object]:
    ...

def classify_page(title: str, raw_path: str, text: str) -> dict[str, object]:
    ...
```

Implementation notes:

- Use URL extraction plus issue-key extraction, then de-duplicate by issue key.
- Preserve a `source_anchor` snippet around each issue.
- Treat anchors near `JIRA 编号`, `jira编号`, or `【JIRA` as supporting by default.
- Treat anchors near `文档记录`, table headers, `修改内容`, or the first visible issue as primary candidates.
- Return low confidence when multiple primary candidates remain.
- Do not fetch Jira status in this task.

- [ ] **Step 4: Run extraction tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: PASS for extraction tests.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/cjira_registry.py skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py
git commit -m "feat: add cjira registry extraction"
```

### Task 2: Add registry persistence and archive transitions

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/cjira_registry.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py`

- [ ] **Step 1: Write failing tests for registry files**

Add tests for:

- `staging/cjira-registry/active.json` is written for `idea` and non-terminal pages
- terminal primary issue moves page to `archive.json`
- archive writes happen before active pruning
- failed or unknown status remains active

Use a fake status map, not network:

```python
status_by_key = {
    "PSP-40038": {"status": "Done", "terminal": True},
    "OP-42513": {"status": "In Progress", "terminal": False},
}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: FAIL because persistence functions are missing.

- [ ] **Step 3: Implement persistence functions**

Add these functions:

```python
def registry_dir(project: Path) -> Path:
    return project / "staging" / "cjira-registry"

def read_registry(project: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    ...

def write_registry(project: Path, active: list[dict[str, object]], archive: list[dict[str, object]], cache: dict[str, object]) -> None:
    ...

def update_registry_for_sources(project: Path, sources: list[dict[str, object]], refresh_status: bool = False) -> dict[str, object]:
    ...
```

Output shape:

```json
{
  "generated_at": "2026-05-26T00:00:00+00:00",
  "records": []
}
```

Record shape:

```json
{
  "page_id": "",
  "page_path": "raw/.../index.md",
  "title": "8.动销平台_自营政策调价",
  "doc_status": "in_progress",
  "primary_cjira": "PSP-40038",
  "supporting_cjira": [],
  "idea_flag": false,
  "status_source": "cjira",
  "primary_cjira_status": "In Progress",
  "primary_cjira_terminal": false,
  "last_checked_at": "",
  "source_anchor": "...",
  "confidence": "high"
}
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/cjira_registry.py skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py
git commit -m "feat: persist cjira page registry"
```

## Chunk 2: Jira Status Refresh

### Task 3: Add live status lookup with auth-compatible fallback

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/cjira_registry.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py`

- [ ] **Step 1: Write failing tests for status refresh**

Add tests with `unittest.mock` for:

- `fetch_jira_status("PSP-40038")` calls `/rest/api/2/issue/PSP-40038`
- `fields.status.name` is used as the status string
- status values `Done`, `Closed`, `Resolved`, `已完成`, `已关闭`, `已解决` classify as terminal
- request failure records a stale cache entry and keeps the record active

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: FAIL because live lookup is missing.

- [ ] **Step 3: Implement lookup and terminal classification**

Add:

```python
DEFAULT_TERMINAL_STATUSES = {
    "done", "closed", "resolved",
    "已完成", "已关闭", "已解决",
}

def normalize_status(value: str) -> str:
    return value.strip().lower()

def is_terminal_status(status: str, terminal_statuses: set[str] | None = None) -> bool:
    ...

def fetch_jira_status(issue_key: str, *, jira_base: str, headers: dict[str, str], session: requests.Session) -> dict[str, object]:
    ...
```

Auth behavior:

- Accept `--jira-token`, `--jira-cookie`, `--jira-chdsso`, `--auto-jira-chdsso-from-sso`, and `--jira-chdsso-env`.
- Reuse the behavior already present in `tools/confluence_sync/export_confluence_tree.py` conceptually; avoid importing that large script if it creates brittle coupling.
- If no Jira auth is available, write registry records without live status and surface a warning in the report.

- [ ] **Step 4: Add CLI flags**

CLI:

```bash
uv run python tools/cjira_registry.py --project "$PWD"
uv run python tools/cjira_registry.py --project "$PWD" --refresh
uv run python tools/cjira_registry.py --project "$PWD" --refresh --auto-jira-chdsso-from-sso
```

Default `--project` is `.`.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/cjira_registry.py skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py
git commit -m "feat: refresh cjira issue status"
```

## Chunk 3: Build And Update Integration

### Task 4: Generate registry during deterministic build

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/build_wiki.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_build_wiki_source_v2.py`

- [ ] **Step 1: Write failing build integration test**

Add a test that creates:

```markdown
---
title: '8.动销平台_自营政策调价'
page_id: '665758297'
---

# 8.动销平台_自营政策调价

<a href="https://cjira.guazi-corp.com/browse/PSP-40038">PSP-40038</a>
```

Expected:

- `staging/cjira-registry/active.json` exists
- one record has `primary_cjira="PSP-40038"`
- `doc_status` is `in_progress` when no live status was refreshed

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_build_wiki_source_v2.py -v
```

Expected: FAIL because build does not write registry.

- [ ] **Step 3: Call registry update from `build_wiki.py`**

Add:

```python
from cjira_registry import update_registry_for_sources
```

In `update_status(...)`, after writing `source-manifest.json`, call:

```python
cjira_report = update_registry_for_sources(project, sources, refresh_status=False)
status["cjira_registry"] = cjira_report
```

Keep this no-network. Live refresh belongs to `update_wiki.py`.

- [ ] **Step 4: Run build integration tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_build_wiki_source_v2.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/build_wiki.py skills/llm-wiki/assets/project-template/tools/tests/test_build_wiki_source_v2.py
git commit -m "feat: index cjira registry during wiki build"
```

### Task 5: Refresh registry during `update_wiki.py`

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`

- [ ] **Step 1: Write failing update step test**

Add a test that inspects the deterministic step list through a helper function. If no helper exists, first extract the inline `steps` list into:

```python
def deterministic_steps(tools: Path, graphify: bool = False) -> list[tuple[Path, list[str]]]:
    ...
```

Expected order:

1. `build_wiki.py`
2. `cjira_registry.py --refresh`
3. `scan_code.py`
4. optional `graphify_code.py --all`
5. `build_traceability.py`
6. `health.py --json`
7. `build_graph.py`
8. `anchor_check.py`

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py -v
```

Expected: FAIL because the helper and step are missing.

- [ ] **Step 3: Add the update step**

Implement `deterministic_steps(...)` and replace the inline list.

Add `cjira_registry.py` immediately after `build_wiki.py`:

```python
(tools / "cjira_registry.py", ["--refresh"])
```

If later auth propagation is needed, add explicit update flags in a separate task; do not silently read shell credentials except the existing local auth env file behavior already used by Cwiki tooling.

- [ ] **Step 4: Run update tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py
git commit -m "feat: refresh cjira registry during update"
```

## Chunk 4: Health And Query Semantics

### Task 6: Surface registry state in health and doctor

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py`
- Optionally modify: `skills/llm-wiki/assets/project-template/tools/doctor.py`

- [ ] **Step 1: Write failing health test**

Create a temporary project with:

- `staging/cjira-registry/active.json`
- one `idea`
- one `in_progress`
- one low-confidence primary selection
- one stale lookup failure

Expected health fields:

```json
{
  "cjira_registry": {
    "active_pages": 2,
    "archived_pages": 0,
    "idea_pages": 1,
    "in_progress_pages": 1,
    "frozen_pages": 0,
    "low_confidence_pages": 1,
    "stale_status_pages": 1
  }
}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py -v
```

Expected: FAIL because health does not read registry.

- [ ] **Step 3: Implement health summary**

Add:

```python
def cjira_registry_status(project: Path) -> dict[str, object]:
    ...
```

Include it in `build_report(...)` as `cjira_registry`.

Recommended action when stale:

```text
Refresh active cjira statuses with `llm-wiki update`; if Jira auth is missing, configure local SSO/Jira auth first.
```

- [ ] **Step 4: Run health tests**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py
git commit -m "feat: report cjira registry health"
```

### Task 7: Document query and mapping behavior

**Files:**
- Modify: `skills/llm-wiki/references/query-logic.md`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify: `skills/llm-wiki/SKILL.md`

- [ ] **Step 1: Update query logic**

Add a section named `Document status semantics`:

```markdown
## Document Status Semantics

When `staging/cjira-registry/active.json` or `archive.json` has a record for a source page:

- `idea`: describe as idea/proposal/exploratory evidence; do not present as committed scope.
- `in_progress`: describe as active or in-progress requirement evidence; avoid treating it as stable truth.
- `frozen`: may be used as stable requirement evidence, subject to normal source support.

For mapping and traceability, prefer `frozen`, allow `in_progress` as provisional, and mark `idea` as candidate-only.
```

- [ ] **Step 2: Update commands and skill protocol**

Add update/doctor requirements:

- `update` refreshes active registry status after source scan
- frozen pages move to archive
- doctor reports stale or low-confidence registry entries
- query should read registry when answering status-sensitive questions

- [ ] **Step 3: Review docs for consistency**

Run:

```bash
rg -n "cjira|Jira|idea|frozen|in_progress|Document status" skills/llm-wiki/SKILL.md skills/llm-wiki/references/query-logic.md skills/llm-wiki/references/commands.md
```

Expected: New wording appears in all three files and uses consistent status names.

- [ ] **Step 4: Commit**

```bash
git add skills/llm-wiki/SKILL.md skills/llm-wiki/references/query-logic.md skills/llm-wiki/references/commands.md
git commit -m "docs: define cjira-aware query semantics"
```

## Chunk 5: End-To-End Verification And Distribution

### Task 8: Add a fixture-based end-to-end registry test

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py`

- [ ] **Step 1: Write an E2E test against a temporary project**

Fixture:

- one normal `cjira` page
- one `【IDEA】` page without `cjira`
- one page with `【JIRA 编号】` supporting issue

Expected:

- active registry contains the idea page
- active registry contains the normal cjira page
- supporting issue is not selected as primary
- source manifest remains unchanged except for existing build behavior

- [ ] **Step 2: Run E2E test**

Run:

```bash
uv run python -m unittest skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/tests/test_cjira_registry.py
git commit -m "test: cover cjira registry end to end"
```

### Task 9: Run full relevant test suite

**Files:** No source edits expected.

- [ ] **Step 1: Run template tool tests**

Run:

```bash
uv run python -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p "test_*.py" -v
```

Expected: PASS.

- [ ] **Step 2: Run installer tests**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/scripts/tests -p "test_*.py" -v
```

Expected: PASS.

- [ ] **Step 3: Run bundle smoke test**

Run:

```bash
./tests/install_test.sh
```

Expected: PASS.

### Task 10: Refresh distribution artifacts if required

**Files:**
- Modify: `dist/llm-wiki-skill/...` only if the repo's distribution workflow expects committed `dist/`.

- [ ] **Step 1: Identify the distribution command**

Run:

```bash
rg -n "dist/llm-wiki-skill|build dist|bundle|install.sh" README.md INSTRUCTION_AND_RELEASE_PLAN.md tests install.sh
```

Expected: Find the repo's intended distribution refresh process or confirm none exists.

- [ ] **Step 2: Refresh dist when required**

If the repo expects `dist/` committed, run the documented build command. If there is no documented command, do not manually copy files into `dist/`; document the gap.

- [ ] **Step 3: Commit distribution update**

```bash
git add dist/llm-wiki-skill
git commit -m "chore: refresh llm-wiki skill dist"
```

Skip this commit if `dist/` is not tracked or no distribution refresh is required.

## Final Verification

- [ ] Confirm `git status --short` only shows intended files.
- [ ] Confirm frozen records are archived before being removed from active.
- [ ] Confirm unknown or failed Jira status does not become `frozen`.
- [ ] Confirm `idea` pages remain in the active registry even with no `cjira`.
- [ ] Confirm old projects only need an upgraded skill plus `llm-wiki update` to populate the registry from existing `raw/`.

