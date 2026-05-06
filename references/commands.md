# Commands

Use this reference when the user invokes a `llm-wiki` subcommand or when the request maps clearly to one command.

## Command Router

| Command | Use When | Primary Output |
| --- | --- | --- |
| `llm-wiki fast` | New project, user wants the standard path completed in one run | Full first-pass wiki, refinement, validation, status |
| `llm-wiki init` | New project, user wants phased initialization | Skeleton, deterministic build, first-pass plan |
| `llm-wiki resume` | Existing project has partial work | Resume from latest status / checkpoint |
| `llm-wiki doctor` | User wants a site-wide status, diagnosis, and recommendations | Health portrait and prioritized next steps |
| `llm-wiki update` | `raw/`, `BUSINESS_CONTEXT.md`, `raw-code/`, wiki, configured RSS/upstream wiki sources, or source code changed | Impact-scoped wiki update |
| `llm-wiki add-wiki` | Add another document/wiki directory or wiki URL as business or requirement evidence | Imported raw evidence, source provenance, RSS/update status, and affected wiki updates |
| `llm-wiki add-code` | Add another project codebase as implementation evidence | New raw-code codebase and code wiki updates |
| `llm-wiki refine` | Improve source, concepts, entities, or layered pages | AI-native text refinement |
| `llm-wiki gplus` | Text layer exists and needs query readiness | Query acceptance, quality audit, health, graph |
| `llm-wiki build-code` | Build or refresh code wiki. `llm-wiki code` is a backward-compatible alias | codebases, capabilities, mappings |
| `llm-wiki code-trace` | Need audit-grade requirement-to-code tracking. `llm-wiki trace` is a backward-compatible alias | traceability matrix |
| `llm-wiki query` | Answer a business or implementation question | Evidence-grounded answer |
| `llm-wiki review-requirement` | Review a new PRD, Cwiki page, Markdown requirement, or prototype package against wiki, raw, image, zip, frontend, and code evidence | Findings-first requirement review and Cwiki comment draft |
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
2. Install the bundled project template unless equivalent scripts already exist: `python3 /Users/zhaoliang/.codex/skills/llm-wiki/scripts/install_project_template.py --project "$PWD"`.
3. Run deterministic build with `uv run python tools/update_wiki.py`.
4. If `raw-code/` exists and code graph extraction is useful, run `uv run python tools/graphify_code.py --all`, then rerun `scan_code.py` and `build_traceability.py`.
5. Complete first-pass source summary and AI-native refinement.
6. Build layered pages, concepts, entities, truth, conflicts, evidence, proposals, reference, operations.
7. If `raw-code/` exists, refine codebase indexes, capability pages, and traceability evidence strengths.
8. If implementation audit is in scope, create traceability pages for highest-value capabilities.
9. Run G+ readiness checks when feasible: query acceptance and quality audit.
10. Run health, graph, and anchor check.
11. Update `staging/refinement-status.md`.

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
   - run the configured `raw/` wiki sync command, RSS watcher, or feed-based wiki sync command, if present
   - if upstream wiki URLs are configured but RSS/feed URLs are missing, attempt deterministic feed discovery from the wiki URL and platform metadata before syncing
   - after discovering or constructing any RSS/feed URL, verify it once before saving or using it: HTTP must be reachable without auth/login HTML, XML must parse as RSS/Atom/RDF, and it must contain at least one item/entry
   - if an RSS/feed URL cannot be inferred, tell the user exactly which wiki URL needs a manually supplied RSS URL; if the user does not provide one, leave the RSS/feed field empty and report that automatic future updates for that source cannot be completed
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
- A template-installed project should also have `scan_code.py`, `graphify_code.py`, `build_traceability.py`, and `anchor_check.py`; use them for 0-1 builds involving code evidence.
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
- upstream sync status, including missing RSS/feed URLs when automatic wiki updates are configured
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

Purpose: add another document/wiki directory or wiki URL to the current LLM Wiki as business or requirement evidence.

Use when:

- The user has another exported wiki, Markdown directory, Confluence export, live wiki URL, or document folder that should become part of `raw/`.
- The current project should answer questions across multiple document sources.
- The added material is business/requirement evidence, not source code.

Default order:

1. Read `BUSINESS_CONTEXT.md`, existing `docs/build-and-maintenance.md`, and current `staging/refinement-status.md`.
2. Inspect the provided source directory or wiki URL and identify its document unit pattern.
3. If the input is a live wiki URL, attempt deterministic RSS/feed discovery from URL structure and platform metadata.
4. Immediately verify any discovered, constructed, or user-provided RSS/feed URL with `uv run python tools/discover_wiki_feeds.py --url <wiki_url> [--rss-url <rss_url>]`; only `discovered_verified` and `provided_verified` are valid for automatic future updates.
5. If RSS/feed discovery or verification fails, explicitly tell the user that the RSS URL cannot be inferred or verified, ask the user to manually provide the RSS URL, and explain that automatic future update work for that source cannot be completed without it. If the user does not provide one, leave the RSS/feed field empty.
6. Confirm whether the input can be copied, linked, downloaded, or synced into `raw/`; do not rewrite or normalize source evidence in place.
7. Preserve provenance: original path, source URL when present, RSS/feed URL when known, RSS/feed status, imported_at, and source collection name.
8. Place imported documents under a stable `raw/` subdirectory naming scheme that will not collide with existing page IDs.
9. Run the project update command when available, such as `uv run python tools/update_wiki.py`.
10. AI-native refine only affected source, concept, entity, and layered pages.
11. Run health and graph.

Stop for confirmation when:

- The user did not provide a source path or wiki URL.
- The input has ambiguous ownership or should not be copied into this project.
- The import would overwrite existing `raw/` directories.
- Canonical entity rules need to change to accommodate the new corpus.
- A live wiki URL needs automatic future updates but no RSS/feed URL can be inferred; ask for the manual RSS URL, and leave it empty if the user does not provide one.

Final report:

- source input: directory, export, document folder, or wiki URL
- import method: copied, linked, downloaded, synced, or blocked
- source URL, RSS/feed URL when known, and RSS/feed status: discovered, provided, missing, or not applicable
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

## `llm-wiki review-requirement`

Purpose: review a new requirement with evidence from the target requirement, current business wiki, historical raw sources, optional code wiki, frontend requirement rules, images, and zip prototype packages.

Use when:

- The user provides a PRD, Cwiki URL, pageId, Markdown requirement file, exported document, or prototype package and asks for requirement review.
- The user asks whether a requirement is complete, implementable, consistent with history, or missing frontend / interaction details.
- The user wants comments suitable for posting back to Cwiki.

Required reads:

1. `BUSINESS_CONTEXT.md`
2. target `raw/**/index.md` or provided requirement file / URL
3. `docs/retrieval-playbook.md`
4. `wiki/overview.md`, `wiki/index.md`, and relevant `wiki/sources/`
5. relevant `wiki/concepts/`, `wiki/entities/`, `wiki/truth/`, `wiki/conflicts/`, `wiki/evidence/`, `wiki/proposals/`, `wiki/reference/`, and `wiki/operations/`
6. if present, `wiki/code/index.md`, `wiki/code/capabilities/`, and `wiki/code/traceability/`
7. frontend review rules: first read project-local `FE_REQ_REVIEW_SKILL.md` if it exists; otherwise read the bundled copy at `/Users/zhaoliang/.codex/skills/llm-wiki/references/fe-req-review-skill.md`
8. if the requirement or project contains images, read nearby Markdown context and perform multimodal analysis of every requirement-relevant image
9. if the requirement or project contains zip files, inspect each relevant zip as a possible HTML prototype

Input handling:

- If the input is an existing `raw/**/index.md`, use it as the target requirement evidence.
- If the input is a Cwiki URL or pageId, extract the pageId and scan `raw/**/index.md` frontmatter for `page_id` and `source_url`.
- If the Cwiki page is not already in `raw/`, actively download or sync it into `raw/` before review when the project has a configured Cwiki/raw sync workflow. Preserve `page_id`, `source_url`, `title`, `space_key`, `version`, `updated_at`, `downloaded_at`, and `source_type` metadata when available.
- If the project has `tools/update_wiki.py`, run the deterministic update after raw sync, usually `uv run python tools/update_wiki.py`.
- Do not rewrite existing `raw/` pages by hand. If a same pageId exists with conflicting version metadata and no safe sync convention is documented, stop and ask before replacing evidence.
- If only a local Markdown or document path is provided, review it directly and, when appropriate, recommend `llm-wiki add-wiki` to preserve it as raw evidence.

Mandatory artifact analysis:

- Images are part of the requirement, not optional decoration. For each requirement-relevant image, capture:
  - where it appears and the surrounding text
  - visible UI, tables, flows, annotations, states, roles, data fields, and constraints
  - inferred requirement facts and what remains uncertain
  - conflicts between image content and text
- Zip files are likely prototype HTML. For each relevant zip:
  - list top-level files and detect HTML entry points, assets, scripts, routes, mock data, and README files
  - inspect HTML text, visible labels, forms, buttons, states, navigation, dialogs, tables, and validation hints
  - open locally only when needed for visual inspection; if starting a local server under `/Users/zhaoliang/guazi/work`, obey the local port registry guard before any dev/preview command
  - treat prototype behavior as evidence with provenance, and distinguish static prototype facts from implemented system facts

Frontend-specific review:

- If the project has frontend code, `wiki/code/` frontend pages, frontend routes, UI screenshots, HTML prototypes, or the requirement mentions pages, buttons, forms, dialogs, H5, app, web, mini program, console, portal, or user interaction, apply the frontend PRD review rules.
- The frontend rules must be applied by page dimension. Main pages count as pages; dialogs, drawers, upload boxes, overlays, and confirmation modals are reviewed inside their owning page.
- Required frontend dimensions: page states, interaction elements, boundary / exception conditions, and click / pageload tracking.
- If the project involves frontend but the requirement has no UI, interaction, page state, or frontend detail, add a prominent finding requiring the product owner to provide frontend scope, page inventory, interaction details, state definitions, and tracking requirements before development.
- If the requirement includes frontend details, judge whether the frontend logic is reasonable when combined with business rules, historical wiki evidence, code capabilities, prototype zip, and image evidence.
- Follow the frontend rule that "current code already has a reasonable implementation but PRD did not mention it" is not a frontend problem finding by itself. Put that only in review notes as: `代码已有实现，建议 PRD 补录与代码对齐`.

Review dimensions:

| Dimension | Checkpoints |
| --- | --- |
| Business baseline | Alignment with `BUSINESS_CONTEXT.md`, canonical entities, long-term product direction |
| User journey | Role, entry, conversion action, rights, upstream/downstream handoff |
| Historical rules | Conflicts with older PRDs, operations rules, experiments, truth/conflicts pages |
| State machine | Create, pending, success, failure, timeout, cancel, recover, retry, rollback |
| Money/accounting | Deduction, freeze, refund, negative balance, reconciliation, idempotency |
| Role/account model | Normal account, KA, parent-child account, store, group, external actor |
| Frontend scope | Pages, buttons, dialogs, disabled/loading/empty/error/success states, routes, tracking |
| Backend capability | API, service, job, message, table, external dependencies, existing gaps |
| Data migration | Old status, new status, compatibility, gray release, rollback |
| Notification/ops | Push, site message, announcement, help center, CS script, manual operation |
| Metrics/monitoring | Business harm, governance value, alerts, anomaly diagnosis, rollback guard |

Findings-first output:

Start with the issues, then context. Use P0/P1/P2:

- P0: unresolved ambiguity blocks unique implementation, creates accounting/rule errors, or carries severe business risk.
- P1: unresolved issue causes inconsistent experience, test ambiguity, operational explanation risk, or frontend flow gaps.
- P2: useful enhancement, monitoring, copy, gray rollout, or documentation alignment.

Each finding must include:

```text
标题：
等级：
证据：
影响：
建议决策：
是否阻塞开发：
```

Full report shape:

```text
一、结论
二、证据范围
三、全局定位
四、前后变化
五、MECE 影响范围
六、P0/P1/P2 问题
七、前端需求完整性审查
八、图片与 zip 原型证据
九、建议目标模型
十、验收清单
十一、指标护栏
十二、待决问题
十三、证据链接
十四、Cwiki 评论版
十五、建议下一步
```

The evidence scope must state:

```text
查询类型：需求评审
已使用 BUSINESS_CONTEXT.md：是/否
目标需求：
raw 状态：已存在 / 本次下载 / 只读外部页面 / 本地文件
图片证据：无 / 已分析 N 个 / 存在但无法读取
zip 原型：无 / 已分析 N 个 / 存在但无法解压或识别入口
前端评审：不涉及 / 已按 FE_REQ_REVIEW_SKILL.md 执行 / 涉及前端但需求缺失
代码证据：未使用 / 已使用 wiki/code / 代码缺失
检索路径：
1. BUSINESS_CONTEXT.md
2. 目标 raw/source 页面
3. concepts/entities
4. conflicts/evidence/proposals/truth/reference
5. 相关历史 sources
6. wiki/code/capabilities
7. wiki/code/traceability
8. 图片与 zip 原型证据
```

Cwiki comment draft:

- Produce a concise Cwiki-friendly comment after the full report.
- Use original Cwiki links for source evidence when available.
- Do not include local paths such as `/Users/...`, `raw/...`, or `wiki/sources/...` in the comment draft.
- Code evidence may be described as "本地代码证据显示", but local paths are only allowed in the full local report, not in the Cwiki comment draft.
- Before offering the comment draft, scan it for local paths and report the scan result.
- Publishing comments is opt-in. If the user explicitly asks to publish, dry-run first with target pageId, title, comment length, link count, and local-path scan result, then publish only when the user's wording clearly authorizes it.

Final report:

- lead with P0/P1/P2 findings
- include exact evidence links or local file references in the full report
- include the frontend per-page review section when frontend is involved
- include image and zip prototype evidence summaries when present
- include a Cwiki-safe comment draft when a source Cwiki URL exists
- end with `建议下一步`

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

Add another document/wiki directory or wiki URL into the project evidence layer. Preserve provenance and RSS/update status, avoid overwriting `raw/`, then run update, health, and graph.

### `llm-wiki add-code`

Add another project codebase as `raw-code/<codebase_id>/`. Build codebase pages, capability links, optional graphify output, and traceability when relevant.

### `llm-wiki query`

State query type, retrieval path, conclusion, supporting pages, unresolved points, and evidence class.

### `llm-wiki review-requirement`

Review a target PRD or Cwiki page against raw/wiki/code evidence. Include mandatory image multimodal analysis, zip prototype inspection, frontend PRD review via `FE_REQ_REVIEW_SKILL.md`, findings-first issues, acceptance checklist, metric guards, unresolved questions, and a Cwiki-safe comment draft when applicable.

### `llm-wiki audit`

Findings first. Check entry usability, semantic consistency, source coverage, evidence strength, traceability, health, graph, and stale pages.

### `llm-wiki image`

Only after text completion or explicit user request. Follow `image-evidence.md`.

### `llm-wiki ship`

Run validation first. Ensure `raw/` is not staged or tracked. Commit and push only when remote is explicit.
