# Commands

Use this reference when the user invokes a `llm-wiki` subcommand or when the request maps clearly to one command.

## Command Router

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki fast` | New project, user wants the standard path completed in one run | Full first-pass wiki, refinement, validation, status |
| `llm-wiki init` | New project, user wants phased initialization | Skeleton, deterministic build, first-pass plan |
| `llm-wiki resume` | Existing project has partial work | Resume from latest status / checkpoint |
| `llm-wiki update` | `raw/`, `BUSINESS_CONTEXT.md`, `raw-code/`, wiki, or source code changed | Impact-scoped wiki update |
| `llm-wiki refine` | Improve source, concepts, entities, or layered pages | AI-native text refinement |
| `llm-wiki gplus` | Text layer exists and needs query readiness | Query acceptance, quality audit, health, graph |
| `llm-wiki code` | Build or refresh code wiki | codebases, capabilities, mappings |
| `llm-wiki trace` | Need audit-grade requirement-to-code tracking | traceability matrix |
| `llm-wiki query` | Answer a business or implementation question | Evidence-grounded answer |
| `llm-wiki audit` | Review wiki quality | Findings-first report |
| `llm-wiki image` | Add high-value image evidence after text completion | image notes and linked facts |
| `llm-wiki ship` | Publish or submit wiki work | validation, commit, push |

## `llm-wiki fast`

Purpose: one-shot standard build for a new project. Use when the user wants the whole first-pass workflow completed without repeated planning prompts.

Read:

1. `BUSINESS_CONTEXT.md`
2. `raw/`
3. this skill's `bootstrapping.md`
4. this skill's `build-and-maintenance.md`
5. if `raw-code/` exists, `code-wiki.md`

Run order:

1. Validate `raw/` and `BUSINESS_CONTEXT.md`.
2. Initialize missing `wiki/`, `docs/`, `staging/`, `graph/`, `tools/` scaffolding.
3. Run deterministic build.
4. Complete first-pass source summary and AI-native refinement.
5. Build layered pages, concepts, entities, truth, conflicts, evidence, proposals, reference, operations.
6. If `raw-code/` exists, build codebase indexes and capability pages.
7. If implementation audit is in scope, create initial traceability pages for highest-value capabilities.
8. Run G+ readiness checks when feasible: query acceptance and quality audit.
9. Run health and graph.
10. Update `staging/refinement-status.md`.

Default behavior:

- Proceed automatically through low-risk steps.
- Use subagents for large independent batches when available.
- Do not process low-value images.
- Do not submit or push unless the user asked for shipping or remote is already explicit.

Stop only when:

- `raw/` or `BUSINESS_CONTEXT.md` is missing.
- canonical entity rules need business confirmation.
- generated output would overwrite existing manual or refined wiki content.
- secrets or sensitive configs would be exposed.

Final report:

- phase completed
- files created / updated
- codebases included
- traceability coverage
- validation results
- blocked items
- recommended next pass

## `llm-wiki update`

Purpose: respond to changes without rebuilding the whole project.

Common triggers:

- New or edited `raw/**/index.md`.
- Updated `BUSINESS_CONTEXT.md`.
- New or edited `raw-code/*` files.
- Code wiki pages became stale.
- A user manually edited wiki pages and wants dependent pages refreshed.
- Health, graph, or traceability anchor checks started failing.

Read:

1. `BUSINESS_CONTEXT.md`
2. `staging/refinement-status.md`
3. `staging/health/latest.json`
4. `graph/summary.md`
5. `docs/retrieval-playbook.md`
6. `docs/build-and-maintenance.md`
7. changed files and their dependents

Impact analysis:

- If `raw/` changed: update matching source pages, affected layered pages, concepts, entities, query acceptance, health, graph.
- If `BUSINESS_CONTEXT.md` changed: update canonical aliases, concepts, entities, conflicts, query playbook, affected answers.
- If `raw-code/` changed: update affected codebase pages, endpoint maps, capability pages, traceability rows, graphify status if needed.
- If `wiki/code/traceability/` changed: verify evidence strength, source anchors, code anchors, and linked capability pages.
- If docs changed only: update retrieval/build guidance and run link checks.

Default update order:

1. Identify changed files and classify the trigger.
2. Map changed inputs to wiki outputs.
3. Refresh only affected pages.
4. Preserve manual edits and refined prose unless directly stale.
5. Re-run health.
6. Rebuild graph when wikilinks changed.
7. Run optional traceability anchor check when traceability pages changed.
8. Update `staging/refinement-status.md`.

Do not:

- Regenerate the full wiki just because one input changed.
- Rewrite `raw/`.
- Rewrite unrelated refined pages.
- Upgrade `partial`, `inferred`, `external`, or `missing` evidence to `strong` without direct proof.

Final report:

- trigger
- changed inputs
- affected wiki layers
- pages updated
- pages intentionally left untouched
- validation results
- remaining stale or missing evidence

## `llm-wiki trace`

Purpose: build or update audit-grade requirement-to-code matrices.

Output:

```text
wiki/code/traceability/
  index.md
  <capability>.md
```

Matrix columns:

```text
需求点 | 需求来源 | 前端页面/组件 | 前端 URI | Controller/Dubbo | Service/Method | 配置 | 表/字段 | 消息/任务 | 证据强度 | 缺口
```

Evidence strength:

- `strong`: requirement and implementation evidence align through exact URI, Controller/Dubbo, Service, table, or message evidence.
- `partial`: module or service family is located, but method, field, branch, message body, or runtime condition is incomplete.
- `inferred`: based on naming, neighboring evidence, or graph relation only.
- `external`: key behavior belongs to an external system not present under current `raw-code/`.
- `missing`: requirement evidence exists, implementation evidence has not been found.

Required sections:

- `## 覆盖范围`
- `## 追踪矩阵`
- `## 关键代码锚点`
- `## 外部系统边界`
- `## 缺失证据与下一步`

Rules:

- Start from business capability and requirement points, not from file names.
- Link back to source pages and capability pages.
- Use file paths and line numbers for high-value code anchors when verified.
- Keep `external` and `missing` explicit; they are useful findings, not failures.
- Run health and graph after adding wikilinks.

## Other Commands

### `llm-wiki init`

Use the same early stages as `fast`, but stop after the initialized baseline and first-pass plan if the user wants phased work.

### `llm-wiki resume`

Read status and checkpoints first. Continue from the last incomplete phase. Do not restart completed phases.

### `llm-wiki refine`

Limit work to the requested scope: source pages, concepts, entities, layered pages, or conflicts. Preserve evidence trails.

### `llm-wiki gplus`

Produce query acceptance and quality audit. Fix low-risk structural issues automatically. Do not decide business conflicts without evidence.

### `llm-wiki code`

Build codebase indexes, endpoint maps, capability pages, graphify records, and evidence gap reports.

### `llm-wiki query`

State query type, retrieval path, conclusion, supporting pages, unresolved points, and evidence class.

### `llm-wiki audit`

Findings first. Check entry usability, semantic consistency, source coverage, evidence strength, traceability, health, graph, and stale pages.

### `llm-wiki image`

Only after text completion or explicit user request. Follow `image-evidence.md`.

### `llm-wiki ship`

Run validation first. Ensure `raw/` is not staged or tracked. Commit and push only when remote is explicit.
