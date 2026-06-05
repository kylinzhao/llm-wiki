# Traceability Units Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace page-title-to-file traceability with unit-oriented traceability diagnostics for endpoint/fact, capability, field, and flow dimensions.

**Architecture:** Add traceability units as a structured staging layer produced by `build_traceability.py`. Preserve complete JSON candidate/state data, render Markdown around units and diagnostics, and expose stable health/doctor findings.

**Tech Stack:** Python 3 standard library, unittest/pytest, Markdown and JSON staging artifacts.

---

## Chunk 1: Traceability Units And Markdown

### Task 1: Add failing tests for unit extraction and rendering

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`

- [ ] **Step 1: Add a test for source facts producing endpoint units**

Create a temporary project with a refined source page containing key facts such as `GET /cars-report/internal/reportResultAnalysisByKey`, `clue_id`, `key`, and `report_version`. Run `build_traceability.build_traceability(project)` and assert:

- `staging/traceability/units.json` exists.
- At least one unit has `kind == "endpoint"`.
- The unit has endpoint, capability, params, fields, evidence, and source.
- Markdown includes the endpoint/capability instead of only the source title.

- [ ] **Step 2: Add a test for legacy links being diagnosed as low granularity**

Seed `staging/traceability/state.json` with a link that has source/requirement/code but no `unit_id`. Run `build_traceability`. Assert Markdown has a low-granularity diagnostics section and state remains preserved.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py -q
```

Expected: new tests fail because units and low-granularity diagnostics do not exist yet.

### Task 2: Implement units in build_traceability.py

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/build_traceability.py`

- [ ] **Step 1: Add unit extraction helpers**

Add helpers to parse refined source pages and source manifest entries:

- `source_page_path(project, source)`
- `extract_traceability_units(project, sources)`
- `infer_capability(title, text)`
- `extract_endpoint_units(source_ref, title, text)`
- `extract_field_units(source_ref, title, text)`
- `fallback_source_unit(source_ref, title)`

Use deterministic regex extraction only. Do not call model APIs from local scripts.

- [ ] **Step 2: Persist units**

Write complete units to:

```text
staging/traceability/units.json
```

Include schema version, generated_at, units, and diagnostics.

- [ ] **Step 3: Normalize links with optional dimensions**

Extend `normalize_link` to preserve optional fields:

- `unit_id`
- `capability`
- `code_role`
- `match_reason`
- `diagnostics`

- [ ] **Step 4: Render unit-oriented Markdown**

Replace flat proposed rendering with:

- Summary counts.
- Traceability Units table.
- Links grouped by unit.
- Legacy low-granularity links section.
- Candidate artifact links.

Keep row caps as guardrails only.

- [ ] **Step 5: Run tests**

Run the same test command. Expected: new and existing traceability tests pass.

## Chunk 2: Code Candidate Diagnostic Dimensions

### Task 3: Add candidate diagnostics tests

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`

- [ ] **Step 1: Add a low-value path diagnostic test**

Create code under `.agents/`, `tests/`, and normal `src/`. Assert candidate output marks low-value paths with diagnostics or excludes them from high-value matching.

- [ ] **Step 2: Add code role/match reason assertions**

Assert anchor candidates carry `code_role`, `signals`, and diagnostics suitable for later traceability matching.

- [ ] **Step 3: Run tests and verify expected failures**

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py -q
```

### Task 4: Enrich candidates

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/code_candidates.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/build_traceability.py`

- [ ] **Step 1: Add deterministic role inference**

Infer roles from path/symbol names:

- controller/router/endpoint
- service
- dto/request/response
- entity/repository
- frontend/page/component
- config
- test
- tooling
- unknown

- [ ] **Step 2: Add low-value diagnostics**

Mark paths under `.agents/`, `node_modules`, `tests`, `test`, `examples`, build output, and generic tooling scripts as low-value for business traceability.

- [ ] **Step 3: Use diagnostics during traceability rendering**

Do not promote low-value candidates into unit top evidence. Keep them in JSON and count them in diagnostics.

- [ ] **Step 4: Run candidate and traceability tests**

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py -q
```

## Chunk 3: Health And Doctor Diagnostics

### Task 5: Add health/doctor tests

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/tests/test_gplus_quality.py`

- [ ] **Step 1: Test health traceability metrics**

Seed a project with `staging/traceability/units.json`, `state.json`, and a traceability Markdown file. Assert `health.build_report` includes `traceability` metrics:

- `unit_count`
- `links_without_unit_count`
- `unmapped_candidate_count`
- `markdown_size_bytes`
- `markdown_table_rows`
- `status`

- [ ] **Step 2: Test doctor findings**

Stub `doctor.run_health` with problematic traceability metrics. Assert findings include `traceability_low_granularity` and, when relevant, `traceability_markdown_too_large`.

- [ ] **Step 3: Run tests and verify expected failures**

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py skills/llm-wiki/assets/project-template/tools/tests/test_gplus_quality.py -q
```

### Task 6: Implement health/doctor diagnostics

**Files:**
- Modify: `skills/llm-wiki/assets/project-template/tools/health.py`
- Modify: `skills/llm-wiki/assets/project-template/tools/doctor.py`

- [ ] **Step 1: Add `traceability_status(project)` in health**

Compute stable metrics from staging and Markdown files. Do not mutate project files.

- [ ] **Step 2: Include metrics in health report**

Add a `traceability` object to the health JSON.

- [ ] **Step 3: Add doctor findings**

Add P1/P2 findings based on metrics:

- `traceability_units_missing`
- `traceability_low_granularity`
- `traceability_unmapped_candidates`
- `traceability_markdown_too_large`

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py skills/llm-wiki/assets/project-template/tools/tests/test_gplus_quality.py -q
```

## Chunk 4: Release Metadata And Final Verification

### Task 7: Update release metadata

**Files:**
- Modify: `skills/llm-wiki/VERSION`
- Modify: `dist/llm-wiki-skill/VERSION`
- Modify: `dist/llm-wiki-skill/manifest.json`
- Modify: `README.md`
- Modify: `skills/llm-wiki/README.md`
- Modify: `dist/llm-wiki-skill/README.md`
- Modify: `skills/llm-wiki/references/commands/update.md`
- Modify: `dist/llm-wiki-skill/references/commands/update.md`

- [ ] **Step 1: Run release_version.py**

```bash
python3 scripts/release_version.py --version 1.0.9 --engine-version engine-v1.0.9 --note "新增 traceability units，以 endpoint/关键事实、能力、字段和调用链维度诊断代码追踪粒度。"
```

- [ ] **Step 2: Add update command release notes**

Add a concise release note to both source and dist `references/commands/update.md`.

### Task 8: Final verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused tests**

```bash
python3 -m pytest skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py skills/llm-wiki/assets/project-template/tools/tests/test_gplus_quality.py -q
```

- [ ] **Step 2: Run release tests**

```bash
python3 -m pytest tests/test_release_version.py -q
```

- [ ] **Step 3: Inspect git diff**

```bash
git diff --stat
git status --short
```

- [ ] **Step 4: Commit implementation**

```bash
git add docs/superpowers/plans/2026-06-05-traceability-units.md skills/llm-wiki dist/llm-wiki-skill README.md tests
git commit -m "feat: add traceability units diagnostics"
```
