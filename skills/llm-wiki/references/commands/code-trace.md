## `llm-wiki code-trace`

Purpose: run the dedicated code trace workflow without running a full KB update.

This is a single second-level command. Do not ask the user to choose `doctor`, `rebuild`, or `refine` subcommands. Those are internal phases of the same command:

1. diagnose
2. deterministic rebuild when needed
3. AI-native refinement when needed
4. validation and final report

Use this command when the user asks to refresh `raw-code` evidence, rebuild code candidates, diagnose traceability quality, or complete code-side AI traceability refinement.

## Core Contract

- Start with read-only diagnosis, but present it as the diagnosis phase, not as a separate `doctor` subcommand.
- Run deterministic rebuild when scan, candidate, upstream `docs/wiki`, units, or traceability artifacts are missing/stale.
- Run AI-native refinement when diagnostics show missing units, low-granularity links, unmapped candidates, weak code anchors, or thin capability evidence.
- Distributed execution is allowed: split AI refinement by source, unit, capability, or codebase according to priority and task size.
- Checkpoints are allowed only when there is a real blocker, tool/context limit, or explicit user stop. A checkpoint is `usable-with-gaps`, not completion.
- Do not finish by merely recommending another command when remaining AI refinement is low-risk and feasible in the current command.

## Priority Order

When refining traceability, process in this order:

1. Endpoint or key source fact.
2. Business capability.
3. Field, parameter, or response structure.
4. Implementation flow or call chain.

Do not upgrade evidence strength to `strong` unless direct requirement evidence and direct code evidence both exist.

## Phase 1: Diagnose

Read-only. Do not mutate files.

Read:

1. `staging/health/latest.json`
2. `staging/doctor/latest.json`
3. `staging/code-graph/summary.json`
4. `staging/code-graph/<codebase_id>/manifest.json`
5. `staging/code-graph/<codebase_id>/anchor-candidates.json`
6. `staging/code-graph/<codebase_id>/capability-candidates.json`
7. `staging/traceability/units.json`
8. `staging/traceability/state.json`
9. `wiki/code/traceability/index.md`

Report internally:

- codebase scan freshness and missing code evidence
- upstream `docs/wiki` availability and adapter status
- candidate count, low-value path count, endpoint/route/symbol coverage
- upstream source-map coverage
- unit count and unit kinds
- links without `unit_id`
- unmapped candidate count
- Markdown size and table rows

Use the diagnosis to decide the next internal phase:

- Rebuild when deterministic scan/candidate/unit artifacts are missing or stale.
- Refine when deterministic artifacts exist but low-granularity or unmapped candidate evidence remains.
- Use `llm-wiki add-code` only when repeatable shared rebuild requires managed code source metadata that does not exist.
- Use `llm-wiki update` only when source/business evidence outside code trace also needs refresh.

## Phase 2: Deterministic Rebuild

Engineering rebuild. It may be scoped by user text, for example a named source, unit, or codebase, but it is still the same `llm-wiki code-trace` command.

Steps:

1. Validate `raw-code/<codebase_id>/` evidence. In shared mode, prefer engine-managed code sources from `upstream/code-sources.json`; do not invent remote metadata.
2. Run code scan for affected codebases:
   - `staging/code-graph/<codebase_id>/manifest.json`
   - endpoint, route, symbol, and file facts
3. Detect and adapt upstream code intelligence when present:
   - `raw-code/<codebase_id>/docs/wiki/INDEX.md`
   - `CONTEXT.md`
   - `schema.md`
   - `source-map.jsonl`
   - `index.json`
4. Rebuild upstream artifacts:
   - `upstream-summary.json`
   - `upstream-topics.json`
   - `upstream-concepts.json`
   - `upstream-source-map.json`
5. Rebuild candidates:
   - `anchor-candidates.json`
   - `capability-candidates.json`
6. Rebuild traceability artifacts:
   - `staging/traceability/units.json`
   - `staging/traceability/state.json`
   - `wiki/code/traceability/index.md`
7. Run health/doctor diagnostics.

After rebuild, continue into AI refinement when diagnostics show `traceability_units_missing`, `traceability_low_granularity`, or `traceability_unmapped_candidates` and the remaining work is in scope.

## Phase 3: AI-Native Refinement

This phase is semantic work, not a deterministic script chain.

Read diagnostics:

- `traceability_units_missing`
- `traceability_low_granularity`
- `traceability_unmapped_candidates`
- `weak_code_anchor`
- low-value candidate path diagnostics

Work queue:

1. Build a prioritized queue by source, traceability unit, capability, and codebase.
2. Split large queues into batches. Use available workers/subagents only with disjoint write scopes.
3. For each batch, read the source page, existing units, candidate JSON, capability pages, and relevant code anchors.
4. Split complex source pages into accurate traceability units using the priority order above.
5. Map old page-level links to unit-level links.
6. Judge candidate evidence:
   - real implementation
   - adjacent but incomplete implementation
   - weak scan-only candidate
   - irrelevant low-value path
7. Refine or create `wiki/code/capabilities/*.md` when a capability is needed to explain implementation evidence.
8. Update `staging/traceability/runs/<run_id>/proposals.json` or the reviewed state through the deterministic merge path; do not hand-edit claimed strong links without evidence.
9. Rebuild traceability and rerun health/doctor.

Completion contract:

- All in-scope high-priority units have AI-reviewed evidence decisions.
- Legacy page-title-to-file links are either mapped to `unit_id`, rejected, or explicitly left as low-granularity gaps with a reason.
- Capability pages needed for code evidence are refined.
- Evidence strengths are conservative.
- Final health/doctor no longer reports P1 traceability findings for the chosen scope.

If the queue is too large, process by priority and checkpoint explicitly:

- completed batches
- remaining sources/units/codebases
- blocker or limit
- exact continuation command: `llm-wiki code-trace`

Do not label the command complete until AI refinement is actually complete for the declared scope.

## Integration With `llm-wiki update`

`llm-wiki update` still owns integrated source/code updates. When `raw-code/` changed, update may run the equivalent code trace phases internally.

If only code trace refinement remains after deterministic update and the source/business layer is otherwise current, recommend `llm-wiki code-trace` rather than another full `llm-wiki update`.

When the same update affects both requirement/source evidence and implementation/code evidence, finish the integrated source refinement plus code trace refresh in `llm-wiki update` unless blocked.

## Final Report

Include:

- phases run: diagnosis / deterministic rebuild / AI refinement / validation
- scope: source, unit, codebase, or full KB
- deterministic artifacts refreshed
- AI refinement batches completed
- units created or changed
- capability pages created or changed
- links confirmed, downgraded, rejected, or left as gaps
- remaining blockers or queue
- validation results
- readiness: healthy / usable-with-gaps / blocked

End with `建议下一步`.
