---
name: requirement-review
description: 独立需求评审 skill。用于对 PRD、Spec、Cwiki 页面、Markdown 需求、产品方案、图片截图、图表、zip/HTML 原型、前端交互说明、以及含 raw/wiki/raw-code 的 LLM Wiki 项目做 evidence-first review；当用户要求需求 review、产品评审、评分概览、查漏补缺、判断是否能开发、输出 P0/P1/P2 findings、生成 Cwiki 评论稿、检查前端 UI/交互/状态/埋点完整性时使用。
---

# Requirement Review

## Overview

Use this skill to review requirements as product evidence, not as a normal Q&A task. Lead with findings, distinguish evidence from inference, and produce a report that product, design, frontend, backend, QA, and operations can act on.

This skill is standalone. Do not require `$llm-wiki`; if the current project happens to contain `BUSINESS_CONTEXT.md`, `raw/`, `wiki/`, `raw-code/`, or `wiki/code/`, use those files as evidence directly.

## Load References

Always read:

- `references/review-protocol.md`
- `references/output-template.md`

Read when the selected mode needs role review or historical data review:

- `references/multi-role-review.md`
- `references/historical-data-analysis.md`

Read when frontend is involved or may be involved:

- `references/fe-prd-review.md`
- `../../references/fe-req-signal-noise.md`（仓库根目录：有效信息 / 噪声 / 按页映射；与作者是否使用 AI 无关）
- `../../references/fe-req-design-deliverables.md`（仓库根目录：ToC / 中台后台设计交付物分层）

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
7. Select the review mode:
   - `完整评审`: default for formal/first review; cover all 16 dimensions, multi-role review, existing implementation diff, and historical data analysis when applicable.
   - `产品评审`: when the user asks from product/PM perspective; cover product dimensions 1,2,3,5,6,7,13,14,15,16 and only the product manager role.
   - `快速评审`: when the user specifies dimensions, concerns, or role angle; cover only the relevant dimensions and roles.
   - `评分概览`: when the user wants a quick score or version comparison; output only the dimension scorecard.
   If the user already states the mode, use it directly. Otherwise, infer the smallest mode that satisfies the request; do not stop for mode confirmation unless the request is materially ambiguous.
8. Cross-check business rules, historical requirements, code capability, state machines, money/accounting, roles, data migration, notifications, operations, metrics, and rollback guards.
9. Score every in-scope dimension as `完整` / `部分` / `缺失`, with one concise reason. Do not skip in-scope dimensions.
10. Output findings first, then the mode-aware scorecard and evidence-first report.

## Safety And Evidence Rules

- Do not mutate source evidence in `raw/` by hand.
- Do not silently replace Cwiki/raw versions when pageId conflicts.
- If starting any local preview/dev server in a workspace where port collisions are common (for example many repositories checked out under one parent folder), run the local port registry guard first.
- Never put local paths such as `/Users/...`, `raw/...`, or `wiki/sources/...` in the Cwiki comment draft.
- Code evidence may support a finding, but "code already implements something the PRD omitted" is not by itself a frontend缺失 finding. Put it in notes as: `代码已有实现，建议 PRD 补录与代码对齐`.
- When evidence is missing, say it is missing. Do not upgrade inference to fact.

## Output Contract

Use this shape unless the user asks for a shorter version. Keep `一、P0/P1/P2 问题` first even when also using the scorecard from `references/output-template.md`.

```text
一、P0/P1/P2 问题
二、结论
三、证据范围
四、评审模式与维度评分卡（见 `references/output-template.md`）
五、全局定位
六、前后变化
七、MECE 影响范围
八、已有实现差异对照表（完整/快速评审需要；产品评审按需备注）
九、历史数据分析报告（触发条件见 `references/historical-data-analysis.md`）
十、16 维度详情（按模式裁剪；产品评审只含产品维度）
十一、多角色评审（见 `references/multi-role-review.md`；产品评审只输出产品经理视角）
十二、前端需求完整性审查（须先含「信息结构与噪声」小节，规则见仓库根 `references/fe-req-signal-noise.md`；再按 `fe-prd-review.md` 逐页输出）
十三、图片与 zip 原型证据
十四、建议目标模型
十五、验收清单
十六、指标护栏
十七、待决问题
十八、证据链接
十九、Cwiki 评论版
二十、建议下一步
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
