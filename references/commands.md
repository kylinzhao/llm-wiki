# Commands

Use this reference when the user invokes a `llm-wiki` subcommand or when the request maps clearly to one command.

## Command Router

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki fast` | New project, user wants the standard path completed in one run | Full first-pass wiki, refinement, validation, status |
| `llm-wiki init` | New project, user wants phased initialization | Skeleton, deterministic build, first-pass plan |
| `llm-wiki resume` | Existing project has partial work | Resume from latest status / checkpoint |
| `llm-wiki doctor` | User wants a site-wide status, diagnosis, and recommendations | Health portrait and prioritized next steps |
| `llm-wiki update` | `raw/`, `BUSINESS_CONTEXT.md`, `raw-code/`, wiki, or source code changed | Impact-scoped wiki update |
| `llm-wiki add-wiki` | Add another document/wiki directory as business or requirement evidence | Imported raw evidence and affected wiki updates |
| `llm-wiki add-code` | Add another project codebase as implementation evidence | New raw-code codebase and code wiki updates |
| `llm-wiki refine` | Improve source, concepts, entities, or layered pages | AI-native text refinement |
| `llm-wiki gplus` | Text layer exists and needs query readiness | Query acceptance, quality audit, health, graph |
| `llm-wiki build-code` | Build or refresh code wiki. `llm-wiki code` is a backward-compatible alias | codebases, capabilities, mappings |
| `llm-wiki code-trace` | Need audit-grade requirement-to-code tracking. `llm-wiki trace` is a backward-compatible alias | traceability matrix |
| `llm-wiki query` | Answer a business or implementation question | Evidence-grounded answer |
| `llm-wiki audit` | Review wiki quality | Findings-first report |
| `llm-wiki image` | Add high-value image evidence after text completion | image notes and linked facts |
| `llm-wiki ship` | Publish or submit wiki work | validation, commit, push |

## Completion Rule

Every command must end with `建议下一步`.

The recommendation should be project-specific:

- 1-3 prioritized next actions.
- Include the exact next command when useful.
- Mention when it is reasonable to pause.
- Mention what future change should trigger `llm-wiki update`.

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
2. Refresh upstream inputs when the project has a declared updater:
   - run the configured `raw/` wiki sync command, if present
   - update clean `raw-code/*` repositories, if requested or configured
   - never silently overwrite dirty `raw-code/*` worktrees
3. Run the deterministic project update command when available, such as `uv run python tools/update_wiki.py`.
4. Map changed inputs to wiki outputs from the update report, usually `staging/update/latest.md` or `staging/update/latest.json`.
5. Refresh affected pages:
   - changed `raw/` pages update matching source pages, layered pages, concepts, entities, query readiness, health, and graph
   - changed `raw-code/` files update affected codebase pages, endpoint maps, capability pages, traceability rows, and graphify status when needed
   - changed `BUSINESS_CONTEXT.md` updates canonical aliases, concepts, entities, conflicts, truth, and retrieval guidance
   - if health or the update report shows remaining `pending` or `stale` source pages, resolve them in the same command when they are in scope or the backlog is small enough to finish safely
6. When the same update affects both requirement/source evidence and implementation/code evidence, treat source refinement and code traceability refresh as one integrated update pass:
   - refine stale affected source pages first
   - immediately update affected `wiki/code/capabilities/` and `wiki/code/traceability/` rows against the refined requirement evidence
   - re-check evidence strength after both sides are updated
   - do not present these as separate optional next commands unless the user explicitly asked to stop after one layer
7. Continue automatically through all low-risk update completion work:
   - affected source AI refinement
   - affected concept/entity/layer page refresh
   - affected codebase and capability page refresh
   - affected code traceability rows
   - broken wikilink fixes
   - health and graph rebuild
8. Preserve manual edits and refined prose unless directly stale.
9. Re-run health after AI-native edits, not only after deterministic build.
10. Rebuild graph after AI-native edits when wikilinks changed.
11. Run optional traceability anchor check when traceability pages changed.
12. Update `staging/refinement-status.md`.

Project command convention:

- If the repo has `tools/update_wiki.py`, prefer it over manually chaining `build_wiki.py`, `health.py`, and `build_graph.py`.
- If the repo does not have a local update command, use the standard deterministic build order and create a brief impact report before AI-native edits.
- Local scripts may scan files, compare hashes, build manifests, and validate links; semantic summary, entity normalization, and implementation judgment must happen in Codex-native work, not through local model SDK calls.

Do not:

- Regenerate the full wiki just because one input changed.
- Rewrite `raw/`.
- Rewrite unrelated refined pages.
- Upgrade `partial`, `inferred`, `external`, or `missing` evidence to `strong` without direct proof.
- End by asking the user to run `llm-wiki update` again for low-risk pending/stale/source/code-trace work that can be completed now.

Final report:

- trigger
- changed inputs
- affected wiki layers
- pages updated
- pages intentionally left untouched
- validation results
- remaining stale or missing evidence

Recommendation rule:

- Do not recommend `llm-wiki update` as the next step when the current `llm-wiki update` can safely finish the remaining source refinement, capability, traceability, health, or graph work. Finish it in the current command.
- If affected source pages remain stale and affected code traceability also needs refresh but a hard blocker prevents completion, report the blocker and checkpoint, then recommend one combined continuation: `llm-wiki update` to resume the integrated source refinement plus code-trace refresh.
- Recommend `llm-wiki code-trace` separately only when the source wiki is already current and the remaining work is traceability-only.
- Recommend source-only refinement separately only when no affected code evidence or traceability pages are in scope.

## `llm-wiki add-wiki`

Purpose: add another document/wiki directory to the current LLM Wiki as business or requirement evidence.

Use when:

- The user has another exported wiki, Markdown directory, Confluence export, or document folder that should become part of `raw/`.
- The current project should answer questions across multiple document sources.
- The added material is business/requirement evidence, not source code.

Default order:

1. Read `BUSINESS_CONTEXT.md`, existing `docs/build-and-maintenance.md`, and current `staging/refinement-status.md`.
2. Inspect the provided source directory and identify its document unit pattern.
3. Confirm whether the input can be copied or linked into `raw/`; do not rewrite or normalize source evidence in place.
4. Preserve provenance: original path, source URL when present, imported_at, and source collection name.
5. Place imported documents under a stable `raw/` subdirectory naming scheme that will not collide with existing page IDs.
6. Run the project update command when available, such as `uv run python tools/update_wiki.py`.
7. AI-native refine only affected source, concept, entity, and layered pages.
8. Run health and graph.

Stop for confirmation when:

- The user did not provide a source path.
- The input has ambiguous ownership or should not be copied into this project.
- The import would overwrite existing `raw/` directories.
- Canonical entity rules need to change to accommodate the new corpus.

Final report:

- source directory
- import method: copied, linked, or blocked
- imported document count
- affected wiki pages
- validation results
- remaining normalization or entity questions

## `llm-wiki add-code`

Purpose: add another project codebase under `raw-code/<codebase_id>/` and build or refresh the code wiki layer.

Use when:

- The user points to another local project, repo clone, or source tree.
- The project should answer implementation questions using that codebase.
- The added material is implementation evidence, not business requirements.

Default order:

1. Read `BUSINESS_CONTEXT.md` and existing `wiki/code/index.md` when present.
2. Inspect the provided code path, detect repo root, stack, entry points, docs, and whether it is a git repository.
3. Choose a stable `codebase_id` from the repo or directory name; ask only if it collides or is misleading.
4. Add the codebase under `raw-code/<codebase_id>/` by copying, symlinking, or recording the existing path according to project convention. Do not mix it into `raw/`.
5. Scan the codebase for README, AGENTS, OpenSpec, API contracts, routes, controllers, services, jobs, messages, data access, and config.
6. Run graphify if available and useful; otherwise record why it was skipped.
7. Create or update `wiki/code/codebases/<codebase_id>/` and affected `wiki/code/capabilities/`.
8. If relevant requirements already exist, add or refresh `wiki/code/traceability/` rows with conservative evidence strength.
9. Run health and graph.

Stop for confirmation when:

- The source path is missing.
- The target `raw-code/<codebase_id>/` already exists.
- Copying the repo would include secrets, credentials, build artifacts, or very large dependency directories.
- The codebase is dirty and the user asked to pull or update it.

Final report:

- codebase_id
- source path and import method
- detected stack and entry points
- pages created or updated
- capability and traceability coverage
- validation results
- missing evidence

## `llm-wiki doctor`

Purpose: read-only diagnosis of the whole LLM Wiki site. Use it when the user asks “现在状态如何”, “还缺什么”, “下一步干什么”, “这个 wiki 健康吗”, or wants a project-level operating recommendation.

Read:

1. `BUSINESS_CONTEXT.md`
2. `wiki/index.md`
3. `wiki/overview.md`
4. `docs/retrieval-playbook.md`
5. `docs/build-and-maintenance.md`
6. `staging/refinement-status.md`
7. `staging/health/latest.json`
8. `graph/summary.md`
9. `wiki/code/index.md`
10. `wiki/code/traceability/index.md`
11. `docs/query-acceptance.md`
12. `docs/gplus-quality-audit.md`

If any file is missing, report it as a signal. Do not create or modify files.

Optional read-only checks:

- Count `raw/*/index.md` and `wiki/sources/*.md`.
- Count `wiki/code/codebases/*`, `wiki/code/capabilities/*.md`, and `wiki/code/traceability/*.md`.
- Inspect latest health status.
- Inspect graph node / edge counts.
- Search for broken or stale markers.
- If traceability pages exist, sample evidence strength distribution.
- If code anchors are used, recommend anchor check when not recently run.

Output shape:

```text
诊断类型：llm-wiki doctor
已使用 BUSINESS_CONTEXT.md：是/否
读取路径：

总体 verdict：

状态画像：
- 输入层：
- 文档层：
- 代码层：
- 追踪矩阵：
- 校验层：
- 发布/维护状态：

主要问题：
- P0 ...
- P1 ...
- P2 ...

建议下一步：
1. ...
2. ...
3. ...
```

Verdict levels:

- `healthy`: health/graph pass, retrieval docs exist, source coverage complete, no urgent gaps.
- `usable-with-gaps`: wiki answers common questions but has traceability, code, image, or stale gaps.
- `needs-maintenance`: health/graph/staleness/coverage problems should be fixed before relying on it.
- `blocked`: missing required inputs or broken core structure.

Recommendation rules:

- If required inputs or entry docs are missing, recommend `llm-wiki init` or `llm-wiki update`.
- If source coverage or refinement is incomplete, recommend `llm-wiki refine`.
- If G+ artifacts are missing, recommend `llm-wiki gplus`.
- If code wiki exists but traceability is thin, recommend `llm-wiki code-trace`.
- If files changed recently or stale markers exist, recommend `llm-wiki update`.
- If everything is healthy and remote publishing is desired, recommend `llm-wiki ship`.

## `llm-wiki code-trace`

Purpose: build or update audit-grade requirement-to-code matrices.

Backward-compatible alias: `llm-wiki trace`.

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

### `llm-wiki doctor`

Read-only project status diagnosis. Never edit files. End with prioritized next commands.

### `llm-wiki refine`

Limit work to the requested scope: source pages, concepts, entities, layered pages, or conflicts. Preserve evidence trails.

### `llm-wiki gplus`

Produce query acceptance and quality audit. Fix low-risk structural issues automatically. Do not decide business conflicts without evidence.

### `llm-wiki build-code`

Build codebase indexes, endpoint maps, capability pages, graphify records, and evidence gap reports.

Backward-compatible alias: `llm-wiki code`.

### `llm-wiki code-trace`

Build requirement-to-code traceability matrices. Backward-compatible alias: `llm-wiki trace`.

### `llm-wiki add-wiki`

Add another document/wiki directory into the project evidence layer. Preserve provenance, avoid overwriting `raw/`, then run update, health, and graph.

### `llm-wiki add-code`

Add another project codebase as `raw-code/<codebase_id>/`. Build codebase pages, capability links, optional graphify output, and traceability when relevant.

### `llm-wiki query`

State query type, retrieval path, conclusion, supporting pages, unresolved points, and evidence class.

### `llm-wiki audit`

Findings first. Check entry usability, semantic consistency, source coverage, evidence strength, traceability, health, graph, and stale pages.

### `llm-wiki image`

Only after text completion or explicit user request. Follow `image-evidence.md`.

### `llm-wiki ship`

Run validation first. Ensure `raw/` is not staged or tracked. Commit and push only when remote is explicit.
