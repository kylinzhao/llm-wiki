# LLM Wiki Project Rules

## Query Routing

This repository is an LLM Wiki knowledge-base project. When the user asks a
business, product, requirement, terminology, policy, implementation-status, or
code-traceability question in this project, prefer the LLM Wiki query workflow
before answering from general model memory.

- For business knowledge, product rules, requirement interpretation, terminology,
  and source-backed facts, use `$llm-wiki-query` / `llm-wiki query` semantics.
- For questions that need both business evidence and code implementation evidence,
  use `$llm-wiki-query-plus` / `llm-wiki query-plus` semantics.
- If the user explicitly asks to initialize, refresh, audit, diagnose, or maintain
  the knowledge base, use the relevant `llm-wiki` command semantics instead of a
  plain chat answer.
- Always read `BUSINESS_CONTEXT.md` first when it exists, then follow
  `docs/retrieval-playbook.md` and the evidence hierarchy in `wiki/`.
- Do not answer business facts from memory when relevant wiki evidence exists.
  Cite the supporting wiki/source pages and call out evidence gaps.

## Evidence Boundaries

- `raw/` is immutable source evidence. Read it; do not edit it.
- `raw-code/` is immutable code evidence. Read it; do not edit it.
- Do not commit `raw/` unless the owner explicitly asks for that.
- Do not write secrets, cookies, tokens, private keys, or full sensitive config values into `wiki/`.

## Build Commands

Use `update_wiki.py` as the deterministic primary entrypoint:

```bash
uv run python tools/update_wiki.py
# optional when raw-code/ exists and graphify is installed:
uv run python tools/update_wiki.py --graphify
```

`tools/update_wiki.py` runs the deterministic chain (including health/graph/anchor checks). Use Codex-native work for summaries, entity normalization, business judgment, implementation judgment, and final traceability strength.
