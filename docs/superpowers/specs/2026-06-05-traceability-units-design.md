# Traceability Units Design

## Problem

Current traceability generation maps a whole source page title to many raw code files. In large KBs this produces thousands of homogeneous proposed links such as `报告分析接口 -> raw-code/.../File.java`, with little explanation of which API, requirement fact, field, or implementation role is being connected.

The Markdown size is a symptom. The root problem is insufficient traceability granularity and insufficient diagnostic dimensions.

## Goal

Model traceability around auditable requirement units in this priority order:

1. Endpoint or key source fact.
2. Business capability.
3. Field, parameter, or response structure.
4. Implementation flow or call chain.

The top-level Markdown should summarize meaningful traceability units and their best code evidence. Full low-confidence candidate queues remain in staging JSON.

## Architecture

Introduce a structured traceability unit layer:

```text
staging/traceability/units.json
```

Each unit represents one auditable requirement fact extracted from source evidence. A unit can carry endpoint, capability, parameter, field, source evidence, and extraction status. Existing `staging/traceability/state.json` remains the reviewed link state, but links should point to `unit_id` when possible instead of only repeating the source page title.

Candidate code evidence should be enriched with diagnostic dimensions:

- `codebase_id`
- `code_anchor`
- `code_role`
- `signals`
- `match_reason`
- `requires_verification`
- `diagnostics`

`wiki/code/traceability/index.md` becomes an audit entry point grouped by traceability unit. It should not be the complete candidate queue.

## Code Diagnosis Timing

Code diagnosis happens at four points, each with a different purpose:

1. **Code candidate build time**
   - Occurs when code candidates are generated from scan artifacts.
   - Diagnoses low-value anchors early: agent/tooling paths, tests, examples, generic files, missing endpoints, missing symbols, and weak scan-only matches.
   - Output belongs in `staging/code-graph/<codebase_id>/anchor-candidates.json` and related candidate metadata.

2. **Traceability build time**
   - Occurs in `tools/build_traceability.py`.
   - Diagnoses whether candidate links have enough dimensions to map to a traceability unit.
   - Emits statuses such as `needs_unit_extraction`, `unmapped_candidate`, `low_granularity_link`, and `weak_code_anchor`.
   - Keeps complete data in JSON and only renders meaningful samples in Markdown.

3. **Health time**
   - Occurs in `tools/health.py`.
   - Computes stable metrics for automation: unit count, unmapped candidate count, low-granularity link count, oversized Markdown rows/bytes, and missing unit extraction.
   - Health should not decide severity; it should report facts.

4. **Doctor time**
   - Occurs in `tools/doctor.py`.
   - Converts health metrics into actionable findings.
   - Examples: `traceability_units_missing`, `traceability_low_granularity`, `traceability_unmapped_candidates`, and `traceability_markdown_too_large`.

## Traceability Unit Shape

Example unit:

```json
{
  "id": "tu_report_analysis_internal_endpoint",
  "source": "wiki/sources/179829161-报告分析接口-index.md",
  "kind": "endpoint",
  "title": "内部报告分析查询接口",
  "capability": "报告分析查询",
  "endpoint": "GET /cars-report/internal/reportResultAnalysisByKey",
  "params": ["clue_id", "key", "task_id", "snapshot_id"],
  "fields": ["major_accident", "base_info", "report_conclusion"],
  "evidence": "来源文档「接口调用」「参数说明」「字段 key 值说明」",
  "status": "extracted"
}
```

Example link:

```json
{
  "id": "tr_report_analysis_internal_controller",
  "unit_id": "tu_report_analysis_internal_endpoint",
  "requirement": "内部报告分析查询接口",
  "source": "wiki/sources/179829161-报告分析接口-index.md",
  "code": ["raw-code/carsource/.../ReportController.java#reportResultAnalysisByKey"],
  "code_role": "controller",
  "match_reason": ["endpoint_path", "method_name"],
  "strength": "partial",
  "status": "proposed",
  "note": "Endpoint and handler name match; service implementation still requires verification."
}
```

## Compatibility

Existing `state.json` links without `unit_id` remain valid. During rendering, they are grouped under a legacy low-granularity section and counted by diagnostics. Confirmed and rejected statuses remain protected.

Existing candidate JSON files remain complete. This change should improve their metadata and rendering, not delete evidence.

## Markdown Rendering

`wiki/code/traceability/index.md` should contain:

- Summary counts by unit kind, link status, and evidence strength.
- Unit-oriented tables for extracted endpoint/fact/capability/field units.
- Best code evidence per unit, capped per unit and per section.
- A diagnostics section showing unmapped and low-granularity counts.
- Links to complete staging JSON artifacts.

The page may still have row caps, but caps are guardrails, not the primary fix.

## Tests

Add focused tests that verify:

- Source facts with endpoints produce traceability units.
- Links can carry `unit_id`, `code_role`, and `match_reason`.
- Legacy links without `unit_id` are preserved but diagnosed as low granularity.
- Unmapped code candidates remain in JSON and do not flood Markdown.
- Health reports stable traceability metrics.
- Doctor converts those metrics into actionable findings.

## Release Metadata

Because this modifies the `llm-wiki` skill bundle, update release metadata in the same change:

- `skills/llm-wiki/VERSION`
- `dist/llm-wiki-skill/VERSION`
- `dist/llm-wiki-skill/manifest.json`
- `skills/llm-wiki/references/commands/update.md`
- `dist/llm-wiki-skill/references/commands/update.md`

Prefer `scripts/release_version.py` where applicable.
