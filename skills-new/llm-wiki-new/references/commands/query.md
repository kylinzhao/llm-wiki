## `llm-wiki-new query`

State query type, retrieval path, conclusion, supporting pages, unresolved points, and evidence class.

Default behavior:

- If the question is about business knowledge, product rules, 需求口径, terminology, operations, or document facts, answer from `BUSINESS_CONTEXT.md` and business/requirement wiki layers. Do not include detailed code evidence, code paths, endpoints, services, controllers, classes, tables, jobs, or implementation traces unless they are necessary to avoid a wrong answer.
- If the question is about code implementation, architecture, APIs, source locations, call chains, frontend/backend mapping, testing, or whether a requirement has landed in code, use `wiki/code/` normally.
- If the question is ambiguous, prefer the business-only path and mention that `llm-wiki-new query-plus` can be used for a full business+code answer.

Evidence link policy:

- Prefer remote original wiki links when source_url/page_id metadata is available.
- Keep local raw/wiki snapshot links for reproducibility.
- Do not expose local raw/wiki paths in Cwiki comment drafts.
- For ordinary user-facing query answers, show the remote original link first and keep local raw/wiki links as snapshot or refinement evidence.
- For doctor/update/debug output, local paths may be primary because the user is inspecting local KB state.

Read `references/query-logic.md` before answering.
