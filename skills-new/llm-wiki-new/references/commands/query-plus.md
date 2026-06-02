## `llm-wiki-new query-plus`

Answer with both business/requirement evidence and code implementation evidence. Use this when the user explicitly wants a fuller answer that connects business口径, requirement evidence, implementation status, traceability, and gaps.

Required behavior:

- Read `BUSINESS_CONTEXT.md`, relevant business/requirement wiki layers, and relevant `wiki/code/` layers.
- Distinguish business conclusions, code implementation facts, inferred links, and missing evidence.
- Preserve traceability evidence strength (`strong`, `partial`, `inferred`, `external`, `missing`) and do not upgrade inferred graph or matrix links into source facts.
- Be more detailed than ordinary `query` when useful, but keep the answer organized around the user's question.

Read `references/query-logic.md` before answering.
