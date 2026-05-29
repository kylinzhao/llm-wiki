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
- Before init/fast/update, require a non-empty `BUSINESS_CONTEXT.md` that has
  been filled beyond the bundled TODO placeholder.
- Always read `BUSINESS_CONTEXT.md` first, then follow
  `docs/retrieval-playbook.md` and the evidence hierarchy in `wiki/`.
- Do not answer business facts from memory when relevant wiki evidence exists.
  Cite the supporting wiki/source pages and call out evidence gaps.

## Evidence Boundaries

- `raw/` is immutable source evidence. Read it; do not edit it.
- `raw-code/` is immutable code evidence. Read it; do not edit it.
- Keep `raw/` uncommitted. Gateway publish sync commits canonical staging state and generated wiki artifacts, while raw evidence is refreshed locally through wiki export/sync.
- Do not write secrets, cookies, tokens, private keys, or full sensitive config values into `wiki/`.

## Build Commands

Use `update_wiki.py` as the deterministic primary entrypoint:

```bash
uv run python tools/update_wiki.py
# optional when raw-code/ exists and graphify is installed:
uv run python tools/update_wiki.py --graphify
```

`tools/update_wiki.py` runs the deterministic chain (including health/graph/anchor checks). Traceability model work must follow `docs/traceability-contract.md`: the current agent or an external agent worker writes `staging/traceability/runs/<run_id>/proposals.json`, and deterministic tooling merges it into `staging/traceability/state.json` before rendering Markdown.

## Cwiki Authentication

When Cwiki upstream sync needs authentication, prefer the bundled `guazi-sso-login` flow over manually pasting `COOKIE_HEADER`. Ask the user to run the built-in setup script in a terminal, then return to the agent and continue update:

```bash
bash tools/confluence_sync/init_auth_env.sh
```

The script prompts for Guazi username, password, phone, and optional Jira token, writes them only to `~/.llm-wiki/guazi-sso.env` with user-only permissions, and does not write secrets into the KB project. The local SSO flow exchanges the credentials for a local Cwiki Cookie/login cache and reuses it until it expires. Jira issue reading should use `JIRA_TOKEN`; CHDSSO is only a fallback when no Jira token is available. If secrets are typed into an agent chat window, they may enter the current agent session context or local session history depending on the engine. A full `COOKIE_HEADER` is only a lower-priority one-off fallback.
