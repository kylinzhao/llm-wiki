"""Maintain project-level agent rules for LLM Wiki projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any


QUERY_ROUTING_HEADING = "## Query Routing"

QUERY_ROUTING_SECTION = """## Query Routing

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
"""


def inspect_agent_rules(project: Path) -> dict[str, Any]:
    agents = project / "AGENTS.md"
    exists = agents.is_file()
    has_query_routing = False
    if exists:
        has_query_routing = QUERY_ROUTING_HEADING in agents.read_text(encoding="utf-8")
    return {
        "path": str(agents),
        "exists": exists,
        "has_query_routing": has_query_routing,
        "ok": exists and has_query_routing,
    }


def refresh_agent_rules(project: Path) -> str:
    agents = project / "AGENTS.md"
    if not agents.is_file():
        agents.write_text("# LLM Wiki Project Rules\n\n" + QUERY_ROUTING_SECTION, encoding="utf-8")
        return "created"

    text = agents.read_text(encoding="utf-8")
    if QUERY_ROUTING_HEADING in text:
        return "already_present"

    if text.startswith("# "):
        first_break = text.find("\n")
        insert_at = first_break + 1 if first_break != -1 else len(text)
        refreshed = text[:insert_at].rstrip() + "\n\n" + QUERY_ROUTING_SECTION + "\n" + text[insert_at:].lstrip()
    else:
        refreshed = "# LLM Wiki Project Rules\n\n" + QUERY_ROUTING_SECTION + "\n" + text.lstrip()

    agents.write_text(refreshed.rstrip() + "\n", encoding="utf-8")
    return "updated"
