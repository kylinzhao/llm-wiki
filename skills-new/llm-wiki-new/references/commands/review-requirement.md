## `llm-wiki-new review-requirement`

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
7. frontend review rules: first read project-local `FE_REQ_REVIEW_SKILL.md` if it exists; otherwise read the bundled copy at `references/fe-req-review-skill.md` inside the llm-wiki skill package
8. if the requirement or project contains images, read nearby Markdown context and perform multimodal analysis of every requirement-relevant image
9. if the requirement or project contains zip files, inspect each relevant zip as a possible HTML prototype

Input handling:

- If the input is an existing `raw/**/index.md`, use it as the target requirement evidence.
- If the input is a Cwiki URL or pageId, extract the pageId and scan `raw/**/index.md` frontmatter for `page_id` and `source_url`.
- If the Cwiki page is not already in `raw/`, actively download or sync it into `raw/` before review when the project has a configured Cwiki/raw sync workflow. Preserve `page_id`, `source_url`, `title`, `space_key`, `version`, `updated_at`, `downloaded_at`, and `source_type` metadata when available.
- If the project has `tools/update_wiki.py`, run the deterministic update after raw sync, usually `uv run python tools/update_wiki.py`.
- Do not rewrite existing `raw/` pages by hand. If a same pageId exists with conflicting version metadata and no safe sync convention is documented, stop and ask before replacing evidence.
- If only a local Markdown or document path is provided, review it directly and, when appropriate, recommend `llm-wiki-new add-wiki` to preserve it as raw evidence.

Mandatory artifact analysis:

- Images are part of the requirement, not optional decoration. For each requirement-relevant image, capture:
  - where it appears and the surrounding text
  - visible UI, tables, flows, annotations, states, roles, data fields, and constraints
  - inferred requirement facts and what remains uncertain
  - conflicts between image content and text
- Zip files are likely prototype HTML. For each relevant zip:
  - list top-level files and detect HTML entry points, assets, scripts, routes, mock data, and README files
  - inspect HTML text, visible labels, forms, buttons, states, navigation, dialogs, tables, and validation hints
  - open locally only when needed for visual inspection; if starting a local server in a workspace where port collisions are common (e.g. many repos under one parent directory), run the local port registry guard before any dev/preview command
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
