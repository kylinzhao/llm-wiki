# Code Wiki Incremental Graphify Implementation Plan

> **For agentic workers:** REQUIRED: develop from an isolated git worktree. This plan was created in `/Users/zhaoliang/.config/superpowers/worktrees/llm-wiki-skill/codex-code-wiki-incremental-graphify` on branch `codex/code-wiki-incremental-graphify`.

**Goal:** Make code wiki updates cheaper and more precise by treating `raw-code/<codebase_id>/docs/wiki` as the preferred upstream navigation layer when present, using `graphify` only when structural evidence is missing, stale, or explicitly needed.

**Architecture:** Add deterministic code-side indexing and freshness gates before any model-heavy work. The pipeline should first decide what changed, then generate small candidate artifacts, then update only affected `wiki/code/*` pages and traceability proposals. `graphify` remains a structural evidence enhancer, not a default cost paid on every `add-code` or `update`.

**Tech Stack:** Python 3.10 stdlib tooling, existing `unittest` tests, existing llm-wiki project template scripts, Markdown protocol docs.

---

## File Map

### New files

- `docs/superpowers/plans/2026-05-29-code-wiki-incremental-graphify-plan.md`
- `skills/llm-wiki/assets/project-template/tools/code_freshness.py`
- `skills/llm-wiki/assets/project-template/tools/code_candidates.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_code_freshness.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`

### Modified files

- `README.md`
- `skills/llm-wiki/README.md`
- `skills/llm-wiki/SKILL.md`
- `skills/llm-wiki/references/code-wiki.md`
- `skills/llm-wiki/references/build-and-maintenance.md`
- `skills/llm-wiki/references/wiki-structure.md`
- `skills/llm-wiki/references/commands.md`
- `skills/llm-wiki-add-code/SKILL.md`
- `skills/llm-wiki-update/SKILL.md`
- `skills/llm-wiki/assets/project-template/docs/tooling-dependencies.md`
- `skills/llm-wiki/assets/project-template/docs/traceability-contract.md`
- `skills/llm-wiki/assets/project-template/tools/code_intelligence.py`
- `skills/llm-wiki/assets/project-template/tools/scan_code.py`
- `skills/llm-wiki/assets/project-template/tools/graphify_code.py`
- `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- `skills/llm-wiki/assets/project-template/tools/health.py`
- `skills/llm-wiki/assets/project-template/tools/update_wiki.py`

### Generated project artifacts

The implementation should teach project templates to produce these derived files:

- `staging/code-graph/<codebase_id>/freshness.json`
- `staging/code-graph/<codebase_id>/upstream-topics.json`
- `staging/code-graph/<codebase_id>/upstream-concepts.json`
- `staging/code-graph/<codebase_id>/upstream-source-map.json`
- `staging/code-graph/<codebase_id>/capability-candidates.json`
- `staging/code-graph/<codebase_id>/anchor-candidates.json`
- `staging/code-graph/<codebase_id>/structure-summary.json`

Do not require these files to exist for old projects. Missing files should degrade to the current scan-only behavior.

### Verification targets

- `python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py' -v`
- `python3 -m py_compile skills/llm-wiki/assets/project-template/tools/code_freshness.py skills/llm-wiki/assets/project-template/tools/code_candidates.py skills/llm-wiki/assets/project-template/tools/code_intelligence.py skills/llm-wiki/assets/project-template/tools/scan_code.py skills/llm-wiki/assets/project-template/tools/graphify_code.py skills/llm-wiki/assets/project-template/tools/build_traceability.py skills/llm-wiki/assets/project-template/tools/health.py skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- `rg -n "graphify.*必经|always run graphify|每次.*graphify" README.md skills/llm-wiki`

---

## Current Baseline

The current implementation already has:

- Stable upstream detection for `raw-code/<codebase_id>/docs/wiki` when the expected signature is complete.
- `scan_code.py` output for deterministic file roles, endpoints, routes, symbols, and a thin upstream summary.
- `graphify_code.py` archival behavior with skipped/failed/completed status.
- Conservative traceability language that treats upstream and graphify evidence as hints unless direct code anchors are verified.

The missing part is not "run graphify more often." The missing part is a cheap, deterministic middle layer that can answer:

- whether `docs/wiki` is present and fresh enough to use as the primary navigation layer
- whether graphify output is absent, stale, or actually needed
- which capabilities and traceability rows are affected by a code change
- which candidate anchors are good enough for model or human review

---

## Design Policy

### Default graphify decision

`add-code` and `update` should use this policy:

| Condition | Default action |
| --- | --- |
| `docs/wiki` detected, source map present, scan anchors present | Skip graphify by default; record `graphify_decision: skipped_upstream_sufficient` |
| no `docs/wiki`, or upstream signature incomplete | Keep current behavior; graphify is optional and only runs with `--graphify` or explicit policy |
| graphify output missing and caller asks for structural relations | Run graphify for the affected codebase |
| graphify output older than changed structural files | Mark stale; rerun only when policy requires it |
| only comments/config/small localized files changed | Do not run graphify; refresh scan/candidates only |
| routes/controllers/services moved or many imports changed | Run or recommend graphify for the affected codebase |

The user-facing invariant: graphify is a structure enhancer, not a mandatory rebuild step.

### Evidence strength boundary

Automated candidate generation may create `candidate`, `partial`, or `inferred` rows. It must not create `strong` traceability unless all of these are verified deterministically or by accepted trace worker state:

- explicit requirement/source anchor
- code entry anchor, such as route, controller, service, message, job, or config
- implementation anchor exists in the current source tree
- referenced files exist, and line numbers are valid when present

`docs/wiki` and graphify may support narrowing and explanation, but neither is direct proof of business implementation by itself.

---

## Chunk 1: Freshness and Graphify Decision Layer

### Task 1: Add deterministic code freshness tracking

**Files:**

- Create: `skills/llm-wiki/assets/project-template/tools/code_freshness.py`
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_code_freshness.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/scan_code.py`

- [ ] Write tests for a codebase with no previous freshness state. Expected: all scanned files are treated as new, and `freshness.json` records file hashes and generated time.
- [ ] Write tests for a second run with unchanged files. Expected: `changed_files` is empty and `structural_change_level` is `none`.
- [ ] Write tests for changed endpoint/controller/service-like files. Expected: `structural_change_level` is at least `medium`.
- [ ] Write tests for many changed files or moved paths. Expected: `structural_change_level` is `high`.
- [ ] Implement `code_freshness.py` using file hashes, relative paths, code roles from `scan_code`, and optional previous state.
- [ ] Update `scan_code.py` to write `staging/code-graph/<codebase_id>/freshness.json`.
- [ ] Keep old projects compatible when no prior state exists.

### Task 2: Add graphify decision policy

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/graphify_code.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/update_wiki.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_freshness.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_update_wiki_failure_report.py`

- [ ] Add tests for graphify decision outcomes: `run_requested`, `skipped_upstream_sufficient`, `skipped_no_graphify_requested`, `stale_not_rerun`, `recommended_structural_change`.
- [ ] Add `--policy` or equivalent internal decision function without breaking existing `--all`, `--codebase`, and `--command`.
- [ ] Keep `--graphify` behavior explicit: if the user passes it, the pipeline may run graphify as today.
- [ ] Add an update report entry for graphify decision per codebase.
- [ ] Ensure missing `graphify` command remains a recorded skipped state, not a hard failure.

---

## Chunk 2: Upstream `docs/wiki` Structural Adaptation

### Task 3: Expand upstream code intelligence extraction

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/code_intelligence.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`

- [ ] Add tests that build a fake `docs/wiki/index.json` with topics and concepts and expect normalized `upstream-topics.json` and `upstream-concepts.json`.
- [ ] Add tests for `source-map.jsonl` parsing into `upstream-source-map.json`.
- [ ] Add tests for malformed JSONL lines. Expected: valid lines are preserved and parse errors are reported in a warnings array.
- [ ] Implement deterministic adapters that keep only compact fields needed for retrieval: id, title, aliases, keywords, source paths, related files, freshness metadata when available.
- [ ] Do not copy full upstream Markdown pages into staging JSON.
- [ ] Update upstream summary to include adapter status and warning counts.

### Task 4: Reflect upstream coverage in codebase pages and health

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/scan_code.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`

- [ ] Extend generated `wiki/code/codebases/<codebase_id>/index.md` with compact upstream coverage fields: topics, concepts, source map entries, adapter warnings, preferred entry path.
- [ ] Add health output for `upstream_wiki_present`, `upstream_adapter_status`, `upstream_source_map_entries`, and `upstream_warning_count`.
- [ ] Do not make missing upstream intelligence a warning for projects that never had it.

---

## Chunk 3: Candidate Fusion Layer

### Task 5: Generate anchor and capability candidates

**Files:**

- Create: `skills/llm-wiki/assets/project-template/tools/code_candidates.py`
- Create: `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/scan_code.py`

- [ ] Write tests that combine scan facts and upstream source map entries into `anchor-candidates.json`.
- [ ] Write tests that combine upstream topics/concepts with endpoint/symbol facts into `capability-candidates.json`.
- [ ] Every candidate must include `signals`, `evidence_strength`, `source_files`, and `requires_verification`.
- [ ] Set default strengths conservatively: direct scan anchors can be `candidate`; upstream-only and graph-only links are `inferred`; mixed upstream plus scan facts can be `partial` only if a file anchor exists.
- [ ] Implement deterministic slug generation that prefers business concept names when available but avoids duplicate near-synonym pages.
- [ ] Update `scan_code.py` or a new build step to write candidate files for each codebase.

### Task 6: Add optional graphify structure summary

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/graphify_code.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/code_candidates.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`

- [ ] Add tests with a minimal fake `graphify-out/graph.json`.
- [ ] Parse only stable, compact structural signals into `structure-summary.json`: important nodes, important edges, communities/hotspots if present.
- [ ] Ignore or cap high-noise dependency edges.
- [ ] Feed structure signals into candidates as `graph_neighbor` or `graph_hotspot`, never as direct proof.
- [ ] If graphify output shape is unknown, record warnings and continue.

---

## Chunk 4: Incremental Traceability and Capability Updates

### Task 7: Mark affected code wiki pages and trace rows

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`

- [ ] Add tests where a changed code file invalidates an existing traceability anchor.
- [ ] Add tests where unchanged files keep existing confirmed/rejected state.
- [ ] Add affected page detection from capability candidates, traceability state, and codebase index references.
- [ ] Write stale markers into health/update reports, not directly into hand-authored sections unless the page is engine-owned.
- [ ] Preserve manually verified traceability rows unless their file anchors no longer exist or line numbers are invalid.

### Task 8: Generate traceability proposals from candidates

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- Modify: `skills/llm-wiki/assets/project-template/docs/traceability-contract.md`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`

- [ ] Add tests that candidates become proposal rows under `staging/traceability/runs/<run_id>/proposals.json` or an equivalent deterministic proposal input.
- [ ] Keep proposal rows separate from confirmed state.
- [ ] Refuse to auto-promote upstream-only or graph-only links to `strong`.
- [ ] Document that model workers may use candidate files as input, but deterministic merge rules own final Markdown rendering.

---

## Chunk 5: Command Semantics and Documentation

### Task 9: Update `add-code` and `update` behavior docs

**Files:**

- Modify: `README.md`
- Modify: `skills/llm-wiki/README.md`
- Modify: `skills/llm-wiki/SKILL.md`
- Modify: `skills/llm-wiki-add-code/SKILL.md`
- Modify: `skills/llm-wiki-update/SKILL.md`
- Modify: `skills/llm-wiki/references/code-wiki.md`
- Modify: `skills/llm-wiki/references/build-and-maintenance.md`
- Modify: `skills/llm-wiki/references/commands.md`

- [ ] Document that `docs/wiki` lowers graphify priority but does not replace direct source anchors.
- [ ] Document that `add-code` should prefer upstream docs/wiki plus scan candidates for the first pass.
- [ ] Document that `update` should run deterministic diff first, then only refresh affected codebase/capability/traceability areas.
- [ ] Document graphify triggers: missing structural evidence, stale graph, structural refactor, explicit user request, or implementation question requiring call/dependency relations.
- [ ] Document skipped graphify as a normal healthy outcome when upstream and scan evidence are sufficient.

### Task 10: Update project template dependency notes

**Files:**

- Modify: `skills/llm-wiki/assets/project-template/docs/tooling-dependencies.md`
- Modify: `skills/llm-wiki/references/wiki-structure.md`

- [ ] Add the new staging artifacts to the structure docs.
- [ ] Explain that `graphify` is optional and low-frequency by default when upstream docs/wiki is present.
- [ ] Explain that old projects without candidate artifacts remain supported.

---

## Chunk 6: Verification and Release

### Task 11: Full regression verification

- [ ] Run:

```bash
python3 -m unittest discover -s skills/llm-wiki/assets/project-template/tools/tests -p 'test_*.py' -v
```

- [ ] Run:

```bash
python3 -m py_compile \
  skills/llm-wiki/assets/project-template/tools/code_freshness.py \
  skills/llm-wiki/assets/project-template/tools/code_candidates.py \
  skills/llm-wiki/assets/project-template/tools/code_intelligence.py \
  skills/llm-wiki/assets/project-template/tools/scan_code.py \
  skills/llm-wiki/assets/project-template/tools/graphify_code.py \
  skills/llm-wiki/assets/project-template/tools/build_traceability.py \
  skills/llm-wiki/assets/project-template/tools/health.py \
  skills/llm-wiki/assets/project-template/tools/update_wiki.py
```

- [ ] Run:

```bash
rg -n "graphify.*必经|always run graphify|每次.*graphify" README.md skills/llm-wiki
```

Expected: no user-facing text implies graphify is mandatory for every code update.

### Task 12: Manual smoke scenario

Create a temporary project with:

- `BUSINESS_CONTEXT.md`
- `raw/` with one minimal requirement page
- `raw-code/demo-app/` with a small endpoint/service pair
- `raw-code/demo-app/docs/wiki/` with the supported signature

Then run:

```bash
python3 tools/scan_code.py --project "$TMP_PROJECT"
python3 tools/build_traceability.py --project "$TMP_PROJECT"
python3 tools/health.py --project "$TMP_PROJECT" --json
```

Expected:

- upstream files are adapted
- graphify is not required
- candidate artifacts exist
- traceability remains candidate/partial/inferred unless direct anchors are verified
- health reports upstream and graphify status separately

### Task 13: Commit strategy

Use small commits:

1. `feat: add code freshness tracking`
2. `feat: adapt upstream code wiki artifacts`
3. `feat: generate code capability candidates`
4. `feat: make graphify policy incremental`
5. `feat: mark affected traceability candidates`
6. `docs: document incremental code wiki updates`

Do not mix broad documentation updates with candidate-generation logic in the same commit unless the docs are required to explain a new public field.

---

## Risks and Guardrails

- **Over-trusting upstream wiki:** Keep upstream evidence tagged as derived. Do not promote upstream-only links to `strong`.
- **Graphify format instability:** Normalize graphify into compact summaries and tolerate unknown shapes.
- **Token cost creep:** Keep large upstream Markdown and raw graph JSON out of query paths. Query should read compact candidates and normalized `wiki/code/*` first.
- **Wiki churn:** Update only affected generated sections. Preserve manual traceability state and hand-authored pages.
- **False freshness confidence:** Treat missing previous freshness state as unknown/new, not clean.
- **Large repositories:** Cap candidate lists and record truncation in warnings.

## Completion Criteria

- Existing `test_code_intelligence.py` still passes.
- New freshness and candidate tests cover unchanged, small-change, structural-change, upstream-present, and graphify-stale cases.
- `update_wiki.py --graphify` still explicitly runs graphify.
- Default update with complete `docs/wiki` and valid scan anchors records graphify as skipped because upstream plus scan evidence is sufficient.
- Health exposes enough state for query/update agents to decide whether to use docs/wiki, graphify, scan artifacts, or direct source.
- Docs clearly state that code trace can be built from requirements plus code wiki candidates, but direct source anchors remain required for `strong`.
