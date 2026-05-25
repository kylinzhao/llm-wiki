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

## Cwiki Authentication

When Cwiki upstream sync needs authentication, prefer the bundled `guazi-sso-login` flow over manually pasting `COOKIE_HEADER`. The user provides Guazi username, password, phone, and preferably a Jira token. The local SSO flow exchanges the Guazi credentials for a local Cwiki Cookie/login cache and reuses it until it expires. Jira issue reading should use `JIRA_TOKEN`; CHDSSO is only a fallback when no Jira token is available. Fastest path: ask the user to provide the values in the agent window; write them to the local env file and continue update. Terminal alternative: ask the user to copy the full block below into a terminal and run it as-is. Tell the user clearly: do not replace or edit the English variable names in the script; after running it, enter the real Guazi username, password, phone, and Jira token when the terminal prompts for them, then return to the agent.

```bash
read -r -p "请输入瓜子用户名: " GUAZI_SSO_USER_NAME
read -r -s -p "请输入瓜子密码（输入时不会显示）: " GUAZI_SSO_PASSWORD; echo
read -r -p "请输入手机号: " GUAZI_SSO_APPLY_PHONE
read -r -s -p "请输入 Jira 令牌（输入时不会显示，没有可直接回车）: " JIRA_TOKEN; echo
mkdir -p ~/.llm-wiki && chmod 700 ~/.llm-wiki
umask 077
cat > ~/.llm-wiki/guazi-sso.env <<EOF
GUAZI_SSO_USER_NAME=$GUAZI_SSO_USER_NAME
GUAZI_SSO_PASSWORD=$GUAZI_SSO_PASSWORD
GUAZI_SSO_APPLY_PHONE=$GUAZI_SSO_APPLY_PHONE
JIRA_TOKEN=$JIRA_TOKEN
EOF
```

The llm-wiki skill does not upload usernames, passwords, phone numbers, Jira tokens, Cookies, or tokens, and does not write them into the KB project. Persistent auth values are stored only on the user's computer in `~/.llm-wiki/guazi-sso.env` and loaded by future local updates. If secrets are typed into an agent chat window, they may enter the current agent session context or local session history depending on the engine. If the user chooses chat input, ask for username, password, phone, and optional Jira token only; do not ask for internal skill paths. A full `COOKIE_HEADER` is only a lower-priority one-off fallback.
