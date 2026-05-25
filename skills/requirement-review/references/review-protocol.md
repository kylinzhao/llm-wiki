# Requirement Review Protocol

## Evidence Scope

Always state the evidence scope:

```text
查询类型：需求评审
评审模式：完整评审 / 产品评审 / 快速评审 / 评分概览
维度覆盖：16/16 / 10/16 / 用户指定维度 / 仅评分
已使用 BUSINESS_CONTEXT.md：是/否/不存在
目标需求：
raw 状态：已存在 / 本次下载 / 只读外部页面 / 本地文件 / 粘贴文本
图片证据：无 / 已分析 N 个 / 存在但无法读取
zip 原型：无 / 已分析 N 个 / 存在但无法解压或识别入口
前端评审：不涉及 / 已按前端规则执行 / 涉及前端但需求缺失
代码证据：未使用 / 已使用 raw-code/wiki-code / 代码缺失
历史数据探查：不适用 / 已执行 / 需要人工确认数据权限
检索路径：
1. BUSINESS_CONTEXT.md
2. 目标需求源
3. concepts/entities
4. conflicts/evidence/proposals/truth/reference
5. 相关历史 sources/raw
6. raw-code 或 wiki/code/capabilities
7. wiki/code/traceability
8. 图片与 zip 原型证据
```

## Input Handling

- Existing `raw/**/index.md`: use it as the target requirement evidence.
- Cwiki URL/pageId: extract pageId, scan `raw/**/index.md` frontmatter for `page_id` and `source_url`, and prefer raw evidence when found.
- Cwiki page not in raw: use the project's documented Cwiki/raw sync command if available. Preserve `page_id`, `source_url`, `title`, `space_key`, `version`, `updated_at`, `downloaded_at`, and `source_type` metadata when the sync flow provides them.
- Local Markdown/document path: review directly; recommend importing into raw only when the project uses an LLM Wiki evidence layer.
- Pasted text: review as `粘贴文本`; be explicit that provenance is weaker than source-controlled raw evidence.

Do not rewrite existing raw pages by hand. If the same pageId exists with conflicting version metadata and no safe sync convention is documented, stop and ask before replacing evidence.

## Review Modes

| Mode | Dimensions | Role review | Historical data | Use when |
| --- | --- | --- | --- | --- |
| 完整评审 | All 16 dimensions | 6 roles | Execute when triggered | Formal review, first review, implementation readiness |
| 产品评审 | 1,2,3,5,6,7,13,14,15,16 | Product manager only | As needed | User asks for product/PM perspective |
| 快速评审 | User-specified dimensions or concerns | Relevant roles only | As needed | Time-limited follow-up, targeted review |
| 评分概览 | All in-scope dimensions | No | No | Quick baseline, version comparison |

If the request says `产品评审`, `产品视角`, `PM 评审`, `从产品角度看`, use 产品评审. If it says `评分`, `评分概览`, or asks only for completeness score, use 评分概览. If it names dimensions, roles, or areas, use 快速评审. Otherwise default to 完整评审 for PRD/spec review.

## Sixteen-Dimension Review

Score every in-scope dimension as `完整` / `部分` / `缺失`. A dimension can be `不适用` only with an explicit reason.

| # | Dimension | Required checks |
| --- | --- | --- |
| 1 | 背景与目标 | Why now, business goal, success metric, baseline/target, time constraint |
| 2 | 业务概念定义 | Core entities, relationships, roles, new-vs-existing concepts, ambiguity |
| 3 | 业务流程 | Entry-by-entry end-to-end path, cross-system handoff, abnormal path, state/flow diagram |
| 4 | 领域边界 | In/out scope, owning system/module, interface/data/code boundary, disputed boundary |
| 5 | 功能需求完整性 | Normal/abnormal/boundary scenarios, user stories, empty/pagination/search/sort, notifications/logs/bulk operations |
| 6 | 数据口径 | Formula, numerator/denominator, time window, null/zero/outlier, realtime/offline frequency |
| 7 | 规则清晰度 | State machine, pre/post condition, permission, validation, numeric constraint, rule priority/order |
| 8 | 技术约束 | Stack, architecture, integration, environment, data, compatibility constraints |
| 9 | 已有实现差异 | Existing implementation, behavior consistency, reusable parts, data-level impact |
| 10 | 依赖方 | Upstream/downstream/cross-team dependencies, contract, downgrade plan |
| 11 | 实现成本 | New/changed modules, database/data cleanup, FE/BE workload, phased delivery, reuse |
| 12 | 性能 | Data volume, query complexity, N+1, cache/precompute, concurrency, response target |
| 13 | 假设与限制条件 | Implicit assumptions, external/data/user/environment limits, non-goals |
| 14 | 风险问题 | Business, technical, security, dependency, schedule, complaint/compliance risks |
| 15 | 成功标准 | Functional/performance/security/business acceptance, launch condition, pass/fail criteria |
| 16 | 上线与兼容性 | Gray release, migration, old/new compatibility, rollback, monitoring/alerting |

For product review, only cover dimensions 1,2,3,5,6,7,13,14,15,16. For scoring overview, output the scorecard and statistics only unless the user asks for detail.

## Existing Implementation Diff

When code evidence exists and the selected mode is 完整评审 or relevant 快速评审:

1. Search by PRD business keywords for controllers/routes, services, mappers/repositories, models/entities, enums/config, tests.
2. Trace the core call chain from entry point to storage/external dependency when possible.
3. Output an existing implementation table:

```text
| PRD 功能点 | 已有实现 | 代码位置（文件:行号） | 一致性 | 数据层面影响 |
```

For 产品评审, skip deep implementation diff by default. If code evidence reveals PRD/code mismatch, include it as a note: `代码已有实现，建议 PRD 补录与代码对齐`.

## Historical Data Analysis

Read `historical-data-analysis.md` and execute it when the PRD changes any of:

- database fields or table structure
- business rules, validation, calculation, or state transitions
- enum values or configuration
- report/statistical definitions
- data display fields or query conditions

If no data access is available, infer from code/schema evidence and mark `需人工确认`. If the PRD does not touch data, state `不适用`.

## Mandatory Image Analysis

Images are part of the requirement, not optional decoration. For every requirement-relevant image:

- identify where it appears and the surrounding text
- describe visible UI, flows, tables, annotations, states, roles, data fields, and constraints
- extract requirement facts implied by the image
- mark uncertainty when text is too small, cropped, ambiguous, or not readable
- compare image content with textual requirements and report conflicts

Do not do bare OCR only. Interpret screenshots and diagrams as product behavior evidence.

## Mandatory Zip / Prototype Analysis

Zip files are likely prototype HTML. For every relevant zip:

- list top-level files
- detect HTML entry points, assets, scripts, routes, mock data, README files, and exported design metadata
- inspect HTML text, visible labels, forms, buttons, states, navigation, dialogs, tables, and validation hints
- open locally only when needed for visual inspection
- if starting a local preview/dev server in an environment where port collisions are common, first run the local port registry helper from **that skill's package root** (resolve the path like other installed skills — do not hardcode a user-specific absolute path), for example:

```bash
python3 "$LOCAL_PORT_REGISTRY_SKILL_ROOT/scripts/port_registry.py" prompt --project "$PWD" --command "<start command>"
```

Set `LOCAL_PORT_REGISTRY_SKILL_ROOT` to the installed `local-port-registry` skill package root (resolve from your agent’s skill install layout; do not hardcode user-specific absolute paths).

Treat prototype behavior as evidence with provenance, and distinguish static prototype facts from implemented system facts.

## Frontend Review

Read `fe-prd-review.md` when frontend is involved. **Before** page-level UI/state/tracking checks, read the repository-root references `references/fe-req-signal-noise.md` and, when UI changes exist, `references/fe-req-design-deliverables.md`. Emit document-level findings first, then per-page findings from `fe-prd-review.md`.

Frontend is involved if any of these are true:

- project has frontend code, frontend routes, UI screenshots, HTML prototypes, or app/web/H5/console pages
- requirement mentions page, button, form, dialog, drawer, upload, filter, table, navigation, tracking, or visual state
- target flow changes user operation, conversion, approval, payment, risk handling, notification, or customer-service operation that has a UI surface

If frontend is involved but the requirement has no frontend details, add a prominent finding requiring product/design to provide:

- page inventory and entry points
- page states: loading, empty, error, success, disabled
- interaction rules and boundary conditions
- dialog/drawer/overlay behavior
- tracking requirements limited to click and pageload unless product explicitly asks for more

If frontend details exist, judge whether the logic is reasonable against business rules, historical evidence, code capabilities, image evidence, and prototype evidence.

## Review Dimensions

| Dimension | Checkpoints |
| --- | --- |
| Business baseline | Alignment with `BUSINESS_CONTEXT.md`, canonical entities, long-term product direction |
| User journey | Role, entry, conversion action, rights, upstream/downstream handoff |
| Historical rules | Conflicts with older PRDs, operations rules, experiments, truth/conflicts pages |
| State machine | Create, pending, success, failure, timeout, cancel, recover, retry, rollback |
| Money/accounting | Deduction, freeze, refund, negative balance, reconciliation, idempotency |
| Role/account model | Normal account, KA, parent-child account, store, group, external actor |
| Frontend scope | Pages, buttons, dialogs, disabled/loading/empty/error/success states, routes, tracking |
| Document signal/noise | Change summary, scope/non-goals, live baseline links; noise heuristics per `references/fe-req-signal-noise.md` |
| Backend capability | API, service, job, message, table, external dependencies, existing gaps |
| Data migration | Old status, new status, compatibility, gray release, rollback |
| Notification/ops | Push, site message, announcement, help center, CS script, manual operation |
| Metrics/monitoring | Business harm, governance value, alerts, anomaly diagnosis, rollback guard |

## Severity

- P0: unresolved ambiguity blocks unique implementation, creates accounting/rule errors, or carries severe business risk.
- P1: unresolved issue causes inconsistent experience, test ambiguity, operational explanation risk, or frontend flow gaps.
- P2: useful enhancement, monitoring, copy, gray rollout, or documentation alignment.

## Cwiki Comment Draft

When a source Cwiki URL exists, produce a concise Cwiki-friendly comment draft after the full report.

Rules:

- use original Cwiki links when available
- do not include local paths such as `/Users/...`, `raw/...`, or `wiki/sources/...`
- code evidence may be described as `本地代码证据显示`
- scan the draft for local paths before presenting it and report the scan result
- publishing comments is opt-in; if the user asks to publish, dry-run first with target pageId, title, comment length, link count, and local-path scan result
