# Upstream Code Intelligence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional upstream code-intelligence support to `llm-wiki`, make `build-code` the single recommended code-knowledge build command, and remove top-level `code-trace` from the public command model.

**Architecture:** Introduce one reusable code-intelligence helper module inside the project template tools, then thread it through deterministic scanners, health/reporting, and command documentation. Keep source code as primary evidence, treat upstream code wikis as derived inputs, and degrade cleanly when a codebase has no upstream knowledge layer.

**Tech Stack:** Markdown skills/docs, Python 3.10 stdlib tooling, PyYAML-based project tooling, shell verification commands

---

## File Map

### New files

- `docs/superpowers/plans/2026-05-15-upstream-code-intelligence-implementation-plan.md`
- `skills/llm-wiki/assets/project-template/tools/code_intelligence.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`

### Modified files

- `README.md`
- `skills/llm-wiki/README.md`
- `skills/llm-wiki/SKILL.md`
- `skills/llm-wiki/references/code-wiki.md`
- `skills/llm-wiki/references/commands.md`
- `skills/llm-wiki/references/build-and-maintenance.md`
- `skills/llm-wiki/references/wiki-structure.md`
- `skills/llm-wiki-add-code/SKILL.md`
- `skills/llm-wiki-build-code/SKILL.md`
- `skills/llm-wiki-update/SKILL.md`
- `skills/llm-wiki/assets/project-template/kb.manifest.yaml`
- `skills/llm-wiki/assets/project-template/tools/scan_code.py`
- `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- `skills/llm-wiki/assets/project-template/tools/health.py`
- `skills/llm-wiki/assets/project-template/tools/update_wiki.py`

### Deleted files

- `skills/llm-wiki-code-trace/SKILL.md`
- `skills/llm-wiki-code-trace/agents/openai.yaml`

### Verification targets

- `python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'`
- `python3 -m py_compile skills/llm-wiki/assets/project-template/tools/code_intelligence.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/build_traceability.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- `rg -n "code-trace|llm-wiki-code-trace" README.md skills/llm-wiki skills/llm-wiki-*`

## Chunk 1: Public Protocol and Command Surface

### Task 1: Update the public docs to introduce upstream code intelligence

**Files:**
- Modify: `README.md`
- Modify: `skills/llm-wiki/README.md`
- Modify: `skills/llm-wiki/SKILL.md`
- Modify: `skills/llm-wiki/references/code-wiki.md`
- Modify: `skills/llm-wiki/references/build-and-maintenance.md`
- Modify: `skills/llm-wiki/references/wiki-structure.md`

- [ ] **Step 1: Write the failing grep check for old command vocabulary**

Run:

```bash
rg -n "llm-wiki code-trace|llm-wiki trace|\\$llm-wiki-code-trace|code-trace" README.md skills/llm-wiki
```

Expected:

- existing matches show `code-trace` is still documented as a first-class command

- [ ] **Step 2: Update the top-level bundle README command descriptions**

Edit `README.md` so it:

- describes `upstream code intelligence` as an optional code-side input
- changes `build-code` to the unified code knowledge builder
- removes `code-trace` as a recommended standalone command

Use wording close to:

```md
- optional `raw-code/` source evidence
- optional upstream code-intelligence inputs contributed by a codebase itself
- normalized `wiki/code/` output owned by `llm-wiki`
```

- [ ] **Step 3: Update the main skill protocol**

Edit `skills/llm-wiki/SKILL.md` so it:

- adds upstream code intelligence to the code-side evidence model
- updates command descriptions for `add-code`, `build-code`, and `update`
- removes `code-trace` as a top-level command from the router and recommendation sections

- [ ] **Step 4: Update reference docs**

Edit `skills/llm-wiki/references/code-wiki.md`, `build-and-maintenance.md`, and `wiki-structure.md` so they:

- define the upstream layer explicitly
- document fallback behavior for codebases without upstream knowledge
- state that traceability is generated within `build-code`

- [ ] **Step 5: Re-run grep to verify the public docs changed**

Run:

```bash
rg -n "llm-wiki code-trace|llm-wiki trace|\\$llm-wiki-code-trace" README.md skills/llm-wiki
```

Expected:

- no matches in user-facing command lists
- any remaining mention must be an intentional migration note

- [ ] **Step 6: Commit**

```bash
git add README.md skills/llm-wiki/README.md skills/llm-wiki/SKILL.md skills/llm-wiki/references/code-wiki.md skills/llm-wiki/references/build-and-maintenance.md skills/llm-wiki/references/wiki-structure.md
git commit -m "docs: unify build-code command model"
```

### Task 2: Update wrapper skills and remove `llm-wiki-code-trace`

**Files:**
- Modify: `skills/llm-wiki-add-code/SKILL.md`
- Modify: `skills/llm-wiki-build-code/SKILL.md`
- Modify: `skills/llm-wiki-update/SKILL.md`
- Delete: `skills/llm-wiki-code-trace/SKILL.md`
- Delete: `skills/llm-wiki-code-trace/agents/openai.yaml`

- [ ] **Step 1: Update wrapper wording**

Edit wrapper files so they align with the new command model:

- `add-code` only onboards and registers codebases
- `build-code` owns codebase pages, capabilities, and traceability
- `update` refers to build-code phases instead of separate code-trace work

- [ ] **Step 2: Delete the deprecated wrapper**

Delete:

```text
skills/llm-wiki-code-trace/SKILL.md
skills/llm-wiki-code-trace/agents/openai.yaml
```

- [ ] **Step 3: Verify wrapper references are clean**

Run:

```bash
rg -n "llm-wiki-code-trace|code-trace" skills/llm-wiki-* README.md
```

Expected:

- no stale wrapper references
- only intentional internal notes remain, if any

- [ ] **Step 4: Commit**

```bash
git add skills/llm-wiki-add-code/SKILL.md skills/llm-wiki-build-code/SKILL.md skills/llm-wiki-update/SKILL.md
git rm skills/llm-wiki-code-trace/SKILL.md skills/llm-wiki-code-trace/agents/openai.yaml
git commit -m "refactor: remove code-trace wrapper"
```

## Chunk 2: Registry and Upstream Discovery

### Task 3: Add a reusable code-intelligence helper module

**Files:**
- Create: `skills/llm-wiki/assets/project-template/tools/code_intelligence.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`
- Modify: `skills/llm-wiki/assets/project-template/kb.manifest.yaml`

- [ ] **Step 1: Write failing tests for discovery and registry behavior**

Create `test_code_intelligence.py` using stdlib `unittest` with cases for:

- no upstream files present
- full `docs/wiki` signature present
- explicit registry entry overrides auto-detection
- fallback `discovery_mode` is `none`

Use test skeleton like:

```python
class DetectUpstreamIntelligenceTests(unittest.TestCase):
    def test_detects_guazi_flow_wiki_signature(self):
        ...
        self.assertEqual(result["upstream_type"], "guazi-flow-wiki")
        self.assertEqual(result["discovery_mode"], "auto-detected")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- fail because `code_intelligence.py` does not exist yet

- [ ] **Step 3: Implement the helper module**

Create `code_intelligence.py` with focused helpers:

- `load_code_intelligence_registry(project: Path) -> dict`
- `save_code_intelligence_registry(project: Path, registry: dict) -> None`
- `detect_upstream_code_intelligence(project: Path, codebase_id: str) -> dict`
- `resolve_code_intelligence(project: Path, codebase_id: str) -> dict`
- `collect_upstream_summary(project: Path, codebase_id: str, resolved: dict) -> dict`

Use a stable signature map like:

```python
SUPPORTED_SIGNATURES = {
    "guazi-flow-wiki": [
        "docs/wiki/INDEX.md",
        "docs/wiki/CONTEXT.md",
        "docs/wiki/schema.md",
        "docs/wiki/source-map.jsonl",
        "docs/wiki/index.json",
    ],
}
```

Registry path should default to:

```python
project / "staging" / "code-graph" / "code-intelligence-registry.json"
```

- [ ] **Step 4: Add manifest comments or defaults**

Update `kb.manifest.yaml` comments to document:

- the registry path
- that codebases may have optional upstream code intelligence
- explicit entries override auto-detection

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- PASS

- [ ] **Step 6: Compile the helper module**

Run:

```bash
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/code_intelligence.py
```

Expected:

- no output

- [ ] **Step 7: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/code_intelligence.py skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py skills/llm-wiki/assets/project-template/kb.manifest.yaml
git commit -m "feat: add upstream code intelligence registry"
```

## Chunk 3: Tooling Integration

### Task 4: Teach `scan_code.py` to adapt upstream code intelligence

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/scan_code.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Test: `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`

- [ ] **Step 1: Extend tests with scan-side expectations**

Add tests for:

- upstream summary files written under `staging/code-graph/<codebase_id>/`
- registry entries preserved
- generated codebase page includes upstream sections when upstream data exists

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- fail because `scan_code.py` does not yet emit upstream artifacts

- [ ] **Step 3: Update `scan_code.py`**

Import the helper module and change `scan_codebase()` so it:

- resolves upstream intelligence for the codebase
- writes `upstream-discovery.json` and `upstream-summary.json`
- enriches `wiki/code/codebases/<codebase_id>/index.md`

Add a page section with output like:

```md
## Upstream Code Intelligence

- Type: `guazi-flow-wiki`
- Discovery mode: `auto-detected`
- Preferred entry: `raw-code/sell-taro/docs/wiki/INDEX.md`
- Evidence boundary: derived upstream navigation, not direct source proof
```

- [ ] **Step 4: Update `health.py`**

Add code-intelligence status into the JSON report:

- detected upstreams
- discovery mode
- missing adaptation files
- codebases on fallback-only path

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- PASS

- [ ] **Step 6: Compile updated tools**

Run:

```bash
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/health.py
```

Expected:

- no output

- [ ] **Step 7: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py
git commit -m "feat: integrate upstream intelligence into scan and health"
```

### Task 5: Fold traceability generation into the `build-code` path

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Modify: `skills/llm-wiki/references/commands.md`
- Modify: `skills/llm-wiki/references/build-and-maintenance.md`

- [ ] **Step 1: Write failing tests or checks for traceability semantics**

Add a unittest case or narrow smoke check that expects:

- upstream summaries can contribute candidate capability hints
- evidence strength remains `partial` or `inferred` until direct anchors exist

If a full automated test is too awkward here, add a deterministic helper in `build_traceability.py` and test that helper directly.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
```

Expected:

- fail because `build_traceability.py` is not reading upstream summaries yet

- [ ] **Step 3: Update `build_traceability.py`**

Change it so it:

- reads `upstream-summary.json` when present
- emits conservative notes into traceability seeds
- never upgrades evidence to `strong` from upstream data alone

Use note text like:

```python
"Derived upstream topic matched; direct code anchor still required."
```

- [ ] **Step 4: Update `update_wiki.py`**

Make the update pipeline treat code traceability as part of the build-code sequence rather than a separate conceptual branch. Ensure the orchestration order is:

1. refresh code inputs
2. run `scan_code.py`
3. optionally run `graphify_code.py`
4. run `build_traceability.py`
5. run health and anchor checks as needed

- [ ] **Step 5: Update command reference wording**

Edit `skills/llm-wiki/references/commands.md` and `build-and-maintenance.md` so the documented run order matches the new implementation and never tells users to treat `code-trace` as a separate top-level workflow.

- [ ] **Step 6: Run tests and compile checks**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/build_traceability.py skills/llm-wiki/assets/project-template/tools/update_wiki.py
```

Expected:

- tests PASS
- py_compile produces no output

- [ ] **Step 7: Commit**

```bash
git add skills/llm-wiki/assets/project-template/tools/build_traceability.py skills/llm-wiki/assets/project-template/tools/update_wiki.py skills/llm-wiki/references/commands.md skills/llm-wiki/references/build-and-maintenance.md skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py
git commit -m "feat: fold traceability into build-code pipeline"
```

## Chunk 4: Final Verification and Release Notes

### Task 6: Run whole-change verification and summarize migration impact

**Files:**
- Modify: `README.md`
- Modify: `skills/llm-wiki/README.md`
- Modify: `skills/llm-wiki/references/commands.md`

- [ ] **Step 1: Run end-to-end static verification**

Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py'
python3 -m py_compile skills/llm-wiki/assets/project-template/tools/code_intelligence.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/build_traceability.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/update_wiki.py
rg -n "llm-wiki code-trace|llm-wiki trace|\\$llm-wiki-code-trace" README.md skills/llm-wiki skills/llm-wiki-*
```

Expected:

- unit tests PASS
- py_compile emits no output
- grep finds no stale public command references

- [ ] **Step 2: Add explicit migration note**

Document in the user-facing docs that:

- `build-code` now includes traceability generation
- repositories without upstream intelligence continue on the scan-only path
- `sell-taro`-style `docs/wiki` layouts are auto-detected, while heterogeneous layouts can be explicitly registered

- [ ] **Step 3: Review `git diff --stat` for scope control**

Run:

```bash
git diff --stat HEAD~1..HEAD
```

Expected:

- only the intended docs, wrappers, and tooling files are in scope

- [ ] **Step 4: Commit**

```bash
git add README.md skills/llm-wiki/README.md skills/llm-wiki/references/commands.md
git commit -m "docs: document upstream intelligence migration"
```

## Notes for the Implementer

- Do not rewrite unrelated protocols just because they mention code.
- Keep helper logic in `code_intelligence.py`; do not duplicate signature matching inside multiple tools.
- Prefer stdlib `unittest` over introducing pytest dependencies into the template.
- Preserve current preflight behavior when `raw-code/` is missing but expected.
- When a codebase has no upstream intelligence, treat that as a normal success path, not as a warning-worthy failure by default.
- If a step reveals that deleting `skills/llm-wiki-code-trace/` breaks installer assumptions or packaging rules, stop and adjust the plan before continuing.

## Plan Review Status

This plan was written in-session without spawning a separate reviewer agent. If platform policy later allows subagent review, run a focused plan-doc review against this file before execution.
