# Raw-Code Git-Managed Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ambiguous raw-code onboarding model with one engine-managed git checkout contract, make `llm-wiki add-code` a one-command setup flow, and migrate legacy KBs to that same model.

**Architecture:** Introduce one deterministic raw-code management helper in the project template tools, then make `add-code` and `update` depend on that helper instead of inferring sync behavior from directory shape. Remove legacy sync overrides and non-git onboarding language so docs, skill protocol, and engine behavior describe the same single contract.

**Tech Stack:** Markdown skill/docs, Python 3.10 stdlib tooling, PyYAML-based template tooling, shell verification commands, git

---

## File Map

### New files

- `docs/superpowers/plans/2026-05-26-raw-code-git-managed-implementation-plan.md`
- `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- `skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_migrate_raw_code.py`

### Modified files

- `README.md`
- `skills/llm-wiki/README.md`
- `skills/llm-wiki/SKILL.md`
- `skills/llm-wiki/references/commands.md`
- `skills/llm-wiki/references/build-and-maintenance.md`
- `skills/llm-wiki/references/code-wiki.md`
- `skills/llm-wiki-add-code/SKILL.md`
- `skills/llm-wiki-update/SKILL.md`
- `skills/llm-wiki/assets/project-template/docs/implementation-workflow.md`
- `skills/llm-wiki/assets/project-template/kb.manifest.yaml`
- `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- `skills/llm-wiki/assets/project-template/tools/health.py`
- `skills/llm-wiki/assets/project-template/tools/scan_code.py`
- `skills/llm-wiki/assets/project-template/tools/wiki_preflight.py`

### Verification targets

- `python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'`
- `python3 -m py_compile skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/wiki_preflight.py`
- `rg -n "pull-code|raw_code_update_commands|copying, symlinking, or recording|snapshot-style|--code-sync-command|--no-auto-code-sync" README.md skills/llm-wiki skills/llm-wiki-*`

## Chunk 1: Public Contract

### Task 1: Rewrite the public raw-code protocol docs

**Files:**
- Modify: `README.md`
- Modify: `skills/llm-wiki/README.md`
- Modify: `skills/llm-wiki/SKILL.md`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify: `skills/llm-wiki/references/build-and-maintenance.md`
- Modify: `skills/llm-wiki/references/code-wiki.md`
- Modify: `skills/llm-wiki/assets/project-template/docs/implementation-workflow.md`
- Modify: `skills/llm-wiki/assets/project-template/kb.manifest.yaml`

- [ ] **Step 1: Write the failing grep check for old protocol language**

Run:

```bash
rg -n "pull-code|raw_code_update_commands|copying, symlinking, or recording|snapshot-style|--code-sync-command|--no-auto-code-sync" README.md skills/llm-wiki skills/llm-wiki-*
```

Expected:

- existing matches show the old multi-mode raw-code protocol is still documented

- [ ] **Step 2: Rewrite the bundle README**

Edit `README.md` so it:

- states that `llm-wiki add-code` creates an engine-managed git checkout under `raw-code/<codebase_id>/`
- states that permission failures stop onboarding immediately
- states that future `llm-wiki update` runs auto-refresh managed codebases
- removes outdated references to multi-mode code sync flags and manifest overrides

- [ ] **Step 3: Rewrite the main skill protocol**

Edit `skills/llm-wiki/SKILL.md` so it:

- treats engine-managed git raw-code as the only supported code onboarding model
- routes new code onboarding exclusively through `add-code`
- describes update failures accurately for dirty or broken managed raw-code entries

- [ ] **Step 4: Rewrite command and maintenance references**

Edit `skills/llm-wiki/references/commands.md`, `build-and-maintenance.md`, `code-wiki.md`, and template `implementation-workflow.md` so they:

- remove copy, symlink, recorded-path, and custom-sync guidance
- describe `add-code` as the one-command onboarding path
- describe `update` as a fixed `git pull --ff-only` refresh for managed codebases
- describe legacy raw-code layouts as migration-only states

- [ ] **Step 5: Remove manifest override guidance**

Edit `skills/llm-wiki/assets/project-template/kb.manifest.yaml` comments so they no longer mention `raw_code_update_commands`.

- [ ] **Step 6: Re-run grep to verify the docs are clean**

Run:

```bash
rg -n "pull-code|raw_code_update_commands|copying, symlinking, or recording|snapshot-style|--code-sync-command|--no-auto-code-sync" README.md skills/llm-wiki skills/llm-wiki-*
```

Expected:

- no user-facing matches remain, except intentional migration wording if absolutely necessary

- [ ] **Step 7: Commit**

```bash
git add README.md skills/llm-wiki/README.md skills/llm-wiki/SKILL.md skills/llm-wiki/references/commands.md skills/llm-wiki/references/build-and-maintenance.md skills/llm-wiki/references/code-wiki.md skills/llm-wiki/assets/project-template/docs/implementation-workflow.md skills/llm-wiki/assets/project-template/kb.manifest.yaml
git commit -m "docs: define managed raw-code protocol"
```

### Task 2: Align the wrapper skills

**Files:**
- Modify: `skills/llm-wiki-add-code/SKILL.md`
- Modify: `skills/llm-wiki-update/SKILL.md`

- [ ] **Step 1: Rewrite the add-code wrapper**

Edit `skills/llm-wiki-add-code/SKILL.md` so it requires:

- one-command repo onboarding
- hard stop on missing repository access
- managed git checkout under `raw-code/<codebase_id>/`
- final report that explicitly says future `update` runs will auto-refresh this codebase

- [ ] **Step 2: Rewrite the update wrapper**

Edit `skills/llm-wiki-update/SKILL.md` so it requires:

- engine-managed raw-code detection
- fixed git refresh semantics
- hard failure for dirty or invalid managed raw-code entries
- clear reporting when legacy raw-code layouts must be migrated

- [ ] **Step 3: Verify wrapper wording**

Run:

```bash
rg -n "raw_code_update_commands|--code-sync-command|--no-auto-code-sync|copying, symlinking, or recording" skills/llm-wiki-add-code/SKILL.md skills/llm-wiki-update/SKILL.md
```

Expected:

- no stale protocol wording remains

- [ ] **Step 4: Commit**

```bash
git add skills/llm-wiki-add-code/SKILL.md skills/llm-wiki-update/SKILL.md
git commit -m "docs: align raw-code wrapper skills"
```

## Chunk 2: Deterministic Raw-Code Manager

### Task 3: Add failing tests for managed raw-code onboarding

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`

- [ ] **Step 1: Write failing tests for repo inspection and metadata writing**

Create `test_raw_code_manager.py` using stdlib `unittest` with cases for:

- readable local git repo can be adopted into `raw-code/<codebase_id>/`
- remote or local repo permission failure aborts before creating the managed target
- dirty existing target is rejected
- metadata file is written with the required fields

Use a test skeleton like:

```python
class AddManagedCodebaseTests(unittest.TestCase):
    def test_permission_failure_does_not_create_target(self):
        ...
        self.assertFalse((project / "raw-code" / "private-repo").exists())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m unittest skills.llm-wiki.assets.project-template.tools.tests.test_raw_code_manager
```

Expected:

- fail because `raw_code_manager.py` does not exist yet

### Task 4: Implement the raw-code manager helper

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/raw_code_manager.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py`

- [ ] **Step 1: Implement repo inspection helpers**

Create focused helpers such as:

- `resolve_repo_source(...)`
- `probe_repo_access(...)`
- `derive_codebase_id(...)`
- `managed_codebase_path(project: Path, codebase_id: str) -> Path`
- `write_codebase_metadata(...)`

- [ ] **Step 2: Implement managed checkout creation**

Add a helper like:

```python
def add_managed_codebase(project: Path, source: str, codebase_id: str | None = None) -> dict:
    ...
```

It should:

- validate repo access first
- create or reuse `raw-code/`
- reject dirty existing targets
- clone or create a managed checkout into `raw-code/<codebase_id>/`
- write `.llm-wiki-codebase.yaml`
- return a structured result for the skill and engine

- [ ] **Step 3: Implement clear permission and invalid-state errors**

Add stable error categories for:

- `missing_access`
- `invalid_repo_source`
- `dirty_target`
- `target_exists`

- [ ] **Step 4: Re-run the onboarding tests**

Run:

```bash
python3 -m unittest skills.llm-wiki.assets.project-template.tools.tests.test_raw_code_manager
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/tests/test_raw_code_manager.py
git commit -m "feat: add managed raw-code helper"
```

## Chunk 3: Update Engine

### Task 5: Replace legacy code sync logic in `update_wiki.py`

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/wiki_preflight.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/scan_code.py`

- [ ] **Step 1: Write failing tests for managed codebase refresh**

Extend `test_raw_code_manager.py` or add focused tests covering:

- managed codebase is discovered from metadata
- update blocks on dirty managed checkout
- update fails on metadata-without-git state
- update reports legacy unmanaged raw-code entries as migration blockers

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- FAIL on the new update behavior cases

- [ ] **Step 3: Refactor code sync discovery**

Edit `update_wiki.py` so it:

- stops reading `raw_code_update_commands`
- stops accepting `--code-sync-command`
- stops accepting `--no-auto-code-sync`
- enumerates `raw-code/*`
- reads `.llm-wiki-codebase.yaml`
- validates each managed checkout
- runs `git pull --ff-only`

- [ ] **Step 4: Update reporting and failure details**

Edit `update_wiki.py`, `health.py`, and `wiki_preflight.py` so they:

- distinguish managed codebases from legacy unmanaged raw-code directories
- emit clear status labels for `refreshed`, `blocked_dirty`, `invalid_managed_checkout`, `legacy_unmanaged_raw_code`, and `pull_failed`
- direct the user toward migration or repair instead of silently continuing

- [ ] **Step 5: Keep scan preflight aligned**

Edit `scan_code.py` and `wiki_preflight.py` so code-side checks:

- still allow normal scanning once managed raw-code exists
- describe legacy raw-code directories as migration blockers when relevant

- [ ] **Step 6: Re-run the full tool tests**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- PASS

- [ ] **Step 7: Run compile verification**

Run:

```bash
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/wiki_preflight.py
```

Expected:

- no output

- [ ] **Step 8: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/wiki_preflight.py
git commit -m "refactor: enforce managed raw-code updates"
```

## Chunk 4: Legacy Migration

### Task 6: Add failing tests for legacy raw-code migration

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_migrate_raw_code.py`

- [ ] **Step 1: Write failing tests for legacy layouts**

Cover at least:

- copied source tree with resolvable origin is migrated into a managed checkout
- symlinked raw-code entry is rejected until repository identity is supplied
- legacy local git repo without metadata can be adopted into the managed format
- permission failure aborts migration without leaving a partial target

- [ ] **Step 2: Run the migration tests to verify they fail**

Run:

```bash
python3 -m unittest skills.llm-wiki.assets.project-template.tools.tests.test_migrate_raw_code
```

Expected:

- FAIL because `migrate_raw_code.py` does not exist yet

### Task 7: Implement the migration helper

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_migrate_raw_code.py`

- [ ] **Step 1: Implement legacy raw-code classification**

Create helpers that classify:

- managed checkout
- local git repo without metadata
- symlink
- copied or non-git directory

- [ ] **Step 2: Implement deterministic migration flow**

The migration CLI should:

- scan `raw-code/*`
- re-add adoptable git repos through the managed helper
- stop with actionable errors for entries whose origin cannot be resolved
- emit a machine-readable report

- [ ] **Step 3: Re-run migration tests**

Run:

```bash
python3 -m unittest skills.llm-wiki.assets.project-template.tools.tests.test_migrate_raw_code
```

Expected:

- PASS

- [ ] **Step 4: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py skills/llm-wiki/assets/project-template/tools/tests/test_migrate_raw_code.py
git commit -m "feat: add legacy raw-code migration tool"
```

## Chunk 5: End-to-End Verification

### Task 8: Verify the public contract and engine agree

**Files:**
- Verify only

- [ ] **Step 1: Run the stale-language grep**

Run:

```bash
rg -n "pull-code|raw_code_update_commands|copying, symlinking, or recording|snapshot-style|--code-sync-command|--no-auto-code-sync" README.md skills/llm-wiki skills/llm-wiki-*
```

Expected:

- no stale public protocol wording remains

- [ ] **Step 2: Run the full test suite**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- PASS

- [ ] **Step 3: Run compile verification**

Run:

```bash
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/raw_code_manager.py skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/wiki_preflight.py
```

Expected:

- no output

- [ ] **Step 4: Smoke-test the operator workflow**

Run a local manual flow against a disposable test KB:

```bash
python3 skills/llm-wiki/assets/project-template/tools/migrate_raw_code.py --project /tmp/test-kb --report-json
uv run python tools/update_wiki.py
```

Expected:

- migration reports either success or actionable blockers
- update refreshes managed codebases before scanning

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify managed raw-code workflow"
```
