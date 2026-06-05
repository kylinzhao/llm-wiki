# Code Trace Command Design

## Background

`llm-wiki update` should continue to refresh code evidence when raw-code changes, but old projects also need an independent way to rebuild, diagnose, and refine code traceability without running a full KB update.

Add a dedicated second-level instruction:

```text
llm-wiki code-trace
```

This command focuses on:

- raw-code scan rebuild
- upstream `docs/wiki` adaptation
- code candidate generation
- traceability unit generation
- code trace diagnostics
- optional AI-native traceability refinement

`llm-wiki update` may call this flow internally, but users can invoke it directly for old-project code rebuilds and targeted traceability tuning.

## Command Shape

### `llm-wiki code-trace rebuild`

Deterministic engineering rebuild. It should not require AI.

Responsibilities:

1. Refresh or validate `raw-code/<codebase_id>/` inputs.
2. Run code scan and rebuild:
   - `staging/code-graph/<codebase_id>/manifest.json`
   - endpoint / route / symbol / file path facts
3. Detect and adapt upstream code intelligence:
   - `raw-code/<codebase_id>/docs/wiki/INDEX.md`
   - `CONTEXT.md`
   - `schema.md`
   - `source-map.jsonl`
   - `index.json`
4. Rebuild:
   - `upstream-summary.json`
   - `upstream-topics.json`
   - `upstream-concepts.json`
   - `upstream-source-map.json`
5. Rebuild code candidates:
   - `anchor-candidates.json`
   - `capability-candidates.json`
6. Rebuild traceability units and index:
   - `staging/traceability/units.json`
   - `staging/traceability/state.json`
   - `wiki/code/traceability/index.md`
7. Run health/doctor code trace diagnostics.

Typical usage:

```text
llm-wiki code-trace rebuild
llm-wiki code-trace rebuild --codebase carsource
```

### `llm-wiki code-trace refine`

AI-native semantic refinement. It should run after deterministic rebuild when diagnostics show low-granularity or unmapped evidence.

Responsibilities:

1. Read diagnostics from health/doctor:
   - `traceability_units_missing`
   - `traceability_low_granularity`
   - `traceability_unmapped_candidates`
   - `weak_code_anchor`
2. Split source pages into traceability units by priority:
   1. endpoint or key fact
   2. business capability
   3. field, parameter, response structure
   4. implementation flow or call chain
3. Map old page-level links to unit-level links.
4. Judge candidate code evidence:
   - real implementation
   - adjacent but incomplete implementation
   - weak scan-only candidate
   - irrelevant low-value path
5. Refine or create `wiki/code/capabilities/*.md`.
6. Update evidence strength conservatively.

Typical usage:

```text
llm-wiki code-trace refine
llm-wiki code-trace refine --source wiki/sources/179829161-报告分析接口-index.md
llm-wiki code-trace refine --unit tu_report_analysis_internal_endpoint
llm-wiki code-trace refine --codebase carsource
```

### `llm-wiki code-trace doctor`

Read-only diagnostics. It should not mutate files.

Responsibilities:

1. Report codebase scan freshness.
2. Report whether each codebase has usable `docs/wiki`.
3. Report candidate quality:
   - candidate count
   - low-value path count
   - endpoint/route/symbol coverage
   - upstream source-map coverage
4. Report traceability quality:
   - unit count
   - links without unit count
   - unmapped candidate count
   - low-granularity legacy link count
   - oversized Markdown rows/bytes
5. Recommend either:
   - `llm-wiki code-trace rebuild`
   - `llm-wiki code-trace refine`
   - `llm-wiki add-code`
   - `llm-wiki update`

Typical usage:

```text
llm-wiki code-trace doctor
llm-wiki code-trace doctor --codebase carsource
```

## Integration With `llm-wiki update`

`llm-wiki update` should still include code trace work when code evidence changes.

Recommended update behavior:

1. If `raw-code/` changed, call the equivalent of `code-trace rebuild`.
2. If rebuild diagnostics show low-granularity traceability and the change scope is manageable, continue into the equivalent of `code-trace refine`.
3. If the queue is too large or blocked, checkpoint with explicit diagnostics and recommend:

```text
llm-wiki code-trace refine
```

Do not tell the user to run a full `llm-wiki update` again when the remaining work is specifically code trace refinement.

## Old Project Flow

For old projects with existing `raw-code`:

```text
llm-wiki code-trace doctor
llm-wiki code-trace rebuild
llm-wiki code-trace doctor
llm-wiki code-trace refine
```

Expected outcome:

- old scan artifacts are rebuilt
- `docs/wiki` is detected when present
- candidates gain diagnostic dimensions
- traceability units are generated
- page-title-to-file links are diagnosed
- AI refinement only runs where deterministic diagnostics prove it is needed

For old projects without managed code source metadata:

1. If `raw-code/<codebase_id>/` exists and is usable locally, `code-trace rebuild` may scan it.
2. If shared-mode publishing or repeatable rebuild is required, require `upstream/code-sources.json` or guide the user to `llm-wiki add-code`.
3. Do not silently invent remote repo metadata.

## Engineering vs AI Boundary

Pure engineering:

- scan raw-code
- detect `docs/wiki`
- adapt upstream topics/concepts/source-map
- generate manifest, candidates, units JSON
- render traceability Markdown
- compute health/doctor diagnostics

Deterministic algorithms:

- endpoint extraction
- parameter/field extraction
- code role inference
- low-value path detection
- match reason calculation
- row/size metrics

AI-native work:

- split complex source pages into accurate traceability units
- normalize business capabilities
- judge whether code actually implements a requirement unit
- refine capability pages
- assign stronger evidence strength
- explain implementation flows

## Implementation Touch Points

Command docs:

- `skills/llm-wiki/references/commands/code-trace.md`
- `dist/llm-wiki-skill/references/commands/code-trace.md`
- Add index entries in `skills/llm-wiki/references/commands.md` and dist equivalent.
- Update `skills/llm-wiki/references/commands/update.md` to route code-specific follow-up to `code-trace`.

Project tools:

- `skills/llm-wiki/assets/project-template/tools/build_traceability.py`
- `skills/llm-wiki/assets/project-template/tools/code_candidates.py`
- `skills/llm-wiki/assets/project-template/tools/code_intelligence.py`
- `skills/llm-wiki/assets/project-template/tools/health.py`
- `skills/llm-wiki/assets/project-template/tools/doctor.py`

Tests:

- `skills/llm-wiki/assets/project-template/tools/tests/test_code_intelligence.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_code_candidates.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_health_business_context.py`
- `skills/llm-wiki/assets/project-template/tools/tests/test_gplus_quality.py`
- Add command documentation contract tests if the repo already checks command reference files.

Release metadata:

- `skills/llm-wiki/VERSION`
- `dist/llm-wiki-skill/VERSION`
- `dist/llm-wiki-skill/manifest.json`
- `skills/llm-wiki/references/commands/update.md`
- `dist/llm-wiki-skill/references/commands/update.md`

## Acceptance Criteria

- `llm-wiki code-trace rebuild` semantics are documented and can be invoked independently from `update`.
- `llm-wiki code-trace refine` semantics clearly cover AI-native traceability tuning.
- `llm-wiki code-trace doctor` is read-only and reports code trace quality.
- `update` documentation explains when it calls code trace internally.
- Old projects can rebuild raw-code scan/candidates/traceability without a full KB rebuild.
- The engineering rebuild does not require AI.
- AI refinement is reserved for semantic mapping and evidence judgment.
