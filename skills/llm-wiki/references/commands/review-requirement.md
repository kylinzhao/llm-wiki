## `llm-wiki review-requirement`

Purpose: review a new requirement using **LLM Wiki knowledge-base evidence** plus upstream **`prd-review-max`** for PRD/Spec business and UX diagnosis.

Use when:

- The user provides a PRD, Cwiki URL, pageId, Markdown requirement file, exported document, or prototype package and asks for requirement review.
- The user asks whether a requirement is complete, implementable, consistent with history, or missing frontend / interaction details.
- The user wants impact-scope analysis grounded in wiki/code evidence and comments suitable for posting back to Cwiki.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `$requirement-review` | KB evidence retrieval, raw sync, impact scope, historical conflicts, implementation diff |
| `$prd-review-max` | Upstream skill from `c2b-fe/pre-code`; base checks, business-review, ux-review (**do not modify upstream files**) |

If `prd-review-max` is not installed:

```bash
./scripts/install_prd_review_max.sh --link --client auto
```

Required reads (in order):

1. `skills/requirement-review/SKILL.md`
2. `skills/requirement-review/references/kb-evidence-bridge.md`
3. **prd-review-max** `SKILL.md` and its `references/**` as loaded by that skill

Do **not** use deprecated local files under `skills/requirement-review/references/` except `kb-evidence-bridge.md`.

## KB evidence (before prd-review-max)

When the current project is an LLM Wiki project, gather evidence from:

1. `BUSINESS_CONTEXT.md`
2. target `raw/**/index.md` or provided requirement file / URL
3. `docs/retrieval-playbook.md`
4. `wiki/overview.md`, `wiki/index.md`, relevant `wiki/sources/`
5. `wiki/concepts/`, `wiki/entities/`, `wiki/truth/`, `wiki/conflicts/`, `wiki/evidence/`, `wiki/proposals/`, `wiki/reference/`, `wiki/operations/`
6. if present, `raw-code/`, `wiki/code/capabilities/`, `wiki/code/traceability/`

Build a **知识库上下文摘要** for impact scope, reasonableness, and historical rule conflicts before invoking prd-review-max.

## Input handling

- Existing `raw/**/index.md`: use as target requirement evidence.
- Cwiki URL/pageId: sync into `raw/` when the project has a configured workflow; then run deterministic update if available.
- Images and zip prototypes: mandatory multimodal / HTML prototype analysis (see `kb-evidence-bridge.md`).

## Mode mapping (user → prd-review-max)

| User intent | prd-review-max |
| --- | --- |
| 完整评审 | 业务 + UX；模式：完整 |
| 产品评审 | 业务；模式：产品 |
| 快速评审 | 业务（或指定范围）；模式：快速 |
| 评分概览 | 业务；模式：评分概览 |
| UX / 前端 only | 用户体验评审 |
| unspecified | 业务 + UX；模式：产品（prd-review-max default) |

## Output

1. prd-review-max output (per `references/common/routing.md`)
2. LLM Wiki appendices: 知识库证据范围, MECE 影响范围, 历史规则与冲突, 已有实现差异对照, Cwiki 评论版, 建议下一步

Findings-first P0/P1/P2; KB-sourced findings must cite wiki/raw/code evidence.

Cwiki comment draft: no local paths; opt-in publish only.
