---
name: requirement-review
description: 独立需求评审 skill。用于对 PRD、Cwiki 页面、Markdown 需求、产品方案、图片截图、图表、zip/HTML 原型、前端交互说明、以及含 raw/wiki/raw-code 的 LLM Wiki 项目做 evidence-first review；当用户要求需求 review、查漏补缺、判断是否能开发、输出 P0/P1/P2 findings、生成 Cwiki 评论稿、检查前端 UI/交互/状态/埋点完整性时使用。
---

# Requirement Review

## Overview

Use this skill to review requirements as product evidence, not as a normal Q&A task. Lead with findings, distinguish evidence from inference, and produce a report that product, design, frontend, backend, QA, and operations can act on.

This skill is standalone. Do not require `$llm-wiki`; if the current project happens to contain `BUSINESS_CONTEXT.md`, `raw/`, `wiki/`, `raw-code/`, or `wiki/code/`, use those files as evidence directly.

## Load References

Always read:

- `references/review-protocol.md`

Read when frontend is involved or may be involved:

- `references/fe-prd-review.md`

Frontend is involved when the project has frontend code, routes, UI screenshots, HTML prototypes, app/web/H5/console pages, or the requirement mentions pages, buttons, forms, dialogs, user interactions, tracking, or visual states.

## Workflow

1. Identify the target requirement: Cwiki URL/pageId, Markdown/doc path, `raw/**/index.md`, attached images, zip prototype, or free-form pasted PRD.
2. Build the evidence scope from local project files when available:
   - `BUSINESS_CONTEXT.md`
   - target requirement source
   - `raw/`, `wiki/`, `docs/retrieval-playbook.md`
   - `wiki/concepts/`, `wiki/entities/`, `wiki/truth/`, `wiki/conflicts/`, `wiki/evidence/`, `wiki/proposals/`, `wiki/reference/`, `wiki/operations/`
   - `raw-code/`, `wiki/code/capabilities/`, `wiki/code/traceability/`
3. If the target is a Cwiki URL/pageId and the current project has `raw/`, check whether the page already exists in `raw/**/index.md` via `page_id` or `source_url`. If not, use the project's documented Cwiki/raw sync flow when available; otherwise mark the raw state as `只读外部页面` and keep reviewing from available evidence.
4. Analyze every requirement-relevant image with multimodal reasoning. Treat screenshots, flows, tables, annotations, and diagrams as first-class requirement evidence.
5. Inspect every relevant zip as a likely HTML prototype. Unzip into a temporary location, find HTML entry points/assets/scripts/mock data, and review visible UI and interactions.
6. Apply frontend review rules if frontend is involved. If frontend is involved but the requirement has no UI, interaction, state, or tracking description, create a prominent finding requiring product/design to complete that scope.
7. Cross-check business rules, historical requirements, code capability, state machines, money/accounting, roles, data migration, notifications, operations, metrics, and rollback guards.
8. Output findings first, then evidence scope, impact model, frontend review, image/zip evidence, acceptance checklist, metrics, unresolved questions, evidence links, and Cwiki-safe comment draft when applicable.

## Safety And Evidence Rules

- Do not mutate source evidence in `raw/` by hand.
- Do not silently replace Cwiki/raw versions when pageId conflicts.
- If starting any local preview/dev server in a workspace where port collisions are common (for example many repositories checked out under one parent folder), run the local port registry guard first.
- Never put local paths such as `/Users/...`, `raw/...`, or `wiki/sources/...` in the Cwiki comment draft.
- Code evidence may support a finding, but "code already implements something the PRD omitted" is not by itself a frontend缺失 finding. Put it in notes as: `代码已有实现，建议 PRD 补录与代码对齐`.
- When evidence is missing, say it is missing. Do not upgrade inference to fact.

## Output Contract

Use this shape unless the user asks for a shorter version:

```text
一、P0/P1/P2 问题
二、结论
三、证据范围
四、全局定位
五、前后变化
六、MECE 影响范围
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

Every finding must include:

```text
标题：
等级：
证据：
影响：
建议决策：
是否阻塞开发：
```
