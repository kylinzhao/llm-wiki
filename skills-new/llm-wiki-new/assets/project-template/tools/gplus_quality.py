"""Heuristics for G+ semantic-layer quality.

This module intentionally checks structural signals only. Codex still owns the
semantic expansion itself: concept design, source interpretation, evidence
strength, and final business judgment.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


GPLUS_LAYERS = ["truth", "conflicts", "evidence", "proposals", "operations", "reference"]
MANUAL_LINK_MARKERS = [
    "请人工补链到 concepts / entities",
    "请人工补链到 concepts/entities",
]


def markdown_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(item for item in path.glob("*.md") if item.is_file())


def non_index_markdown_files(path: Path) -> list[Path]:
    return [item for item in markdown_files(path) if item.name != "index.md"]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def count_sources_with(project: Path, needle: str) -> int:
    return sum(1 for page in markdown_files(project / "wiki" / "sources") if needle in read_text(page))


def count_manual_placeholders(project: Path) -> int:
    count = 0
    for page in markdown_files(project / "wiki" / "sources"):
        text = read_text(page)
        if any(marker in text for marker in MANUAL_LINK_MARKERS):
            count += 1
    return count


def layer_is_low_density(project: Path, layer: str) -> bool:
    layer_dir = project / "wiki" / layer
    if not layer_dir.is_dir():
        return True
    if non_index_markdown_files(layer_dir):
        return False
    index_text = read_text(layer_dir / "index.md")
    source_backlinks = count_sources_with(project, f"[[{layer}/")
    # Index-only layers can be valid for narrow KBs. For larger KBs, no child
    # pages and no source backlinks means this layer is not carrying retrieval.
    return source_backlinks == 0 and len(index_text.split()) < 220


def extract_declared_count(text: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}[：:]\s*(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def finding(severity: str, title: str, detail: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "blocking": False,
        "title": title,
        "detail": detail,
    }


def inspect_gplus_quality(project: Path, health: dict[str, Any] | None = None) -> dict[str, Any]:
    health = health or {}
    source_files = markdown_files(project / "wiki" / "sources")
    source_count = int(health.get("source_pages") or len(source_files))
    concept_count = len(non_index_markdown_files(project / "wiki" / "concepts"))
    entity_count = len(non_index_markdown_files(project / "wiki" / "entities"))
    concept_linked_sources = count_sources_with(project, "[[concepts/")
    entity_linked_sources = count_sources_with(project, "[[entities/")
    manual_placeholders = count_manual_placeholders(project)
    concept_ratio = concept_count / source_count if source_count else 0.0
    concept_coverage = concept_linked_sources / source_count if source_count else 0.0
    entity_coverage = entity_linked_sources / source_count if source_count else 0.0
    low_density_layers = [layer for layer in GPLUS_LAYERS if layer_is_low_density(project, layer)]

    findings: list[dict[str, Any]] = []

    if source_count >= 100 and concept_count < 5:
        findings.append(
            finding(
                "P1",
                "gplus_concepts_underfit",
                (
                    f"{source_count} source pages but only {concept_count} non-index concept pages. "
                    "Concepts are likely too coarse to support topic routing; run G+ semantic expansion."
                ),
            )
        )
    elif source_count >= 100 and concept_ratio < 0.01:
        findings.append(
            finding(
                "P1",
                "gplus_concepts_underfit",
                (
                    f"Concept/source ratio is {concept_ratio:.2%} "
                    f"({concept_count}/{source_count}); run G+ semantic expansion."
                ),
            )
        )
    elif source_count >= 100 and concept_coverage < 0.50:
        findings.append(
            finding(
                "P2",
                "gplus_concept_coverage_low",
                (
                    f"Only {concept_coverage:.1%} of source pages link to concepts "
                    f"({concept_linked_sources}/{source_count})."
                ),
            )
        )

    if manual_placeholders:
        severity = "P1" if manual_placeholders >= 20 or (source_count and manual_placeholders / source_count >= 0.05) else "P2"
        findings.append(
            finding(
                severity,
                "gplus_manual_link_placeholders",
                (
                    f"{manual_placeholders} source pages still contain manual concept/entity link placeholders. "
                    "Resolve these during G+ expansion."
                ),
            )
        )

    if source_count >= 100 and len(low_density_layers) >= 4:
        findings.append(
            finding(
                "P2",
                "gplus_layers_low_density",
                (
                    "G+ layered pages are index-only or low-density for: "
                    + ", ".join(low_density_layers)
                    + ". Add only source-backed facts, conflicts, evidence, proposals, operations, or references."
                ),
            )
        )

    query_acceptance = read_text(project / "docs" / "query-acceptance.md")
    declared_sources = extract_declared_count(query_acceptance, "source pages")
    declared_wiki_pages = extract_declared_count(query_acceptance, "总页面数")
    if declared_sources and source_count and abs(declared_sources - source_count) / max(source_count, 1) > 0.20:
        findings.append(
            finding(
                "P2",
                "gplus_query_acceptance_stale",
                f"docs/query-acceptance.md declares {declared_sources} source pages, current health reports {source_count}.",
            )
        )
    elif declared_wiki_pages and health.get("wiki_pages") and abs(declared_wiki_pages - int(health["wiki_pages"])) / max(int(health["wiki_pages"]), 1) > 0.20:
        findings.append(
            finding(
                "P2",
                "gplus_query_acceptance_stale",
                f"docs/query-acceptance.md declares {declared_wiki_pages} wiki pages, current health reports {health['wiki_pages']}.",
            )
        )

    status = "needs_attention" if findings else "ok"
    return {
        "status": status,
        "metrics": {
            "source_pages": source_count,
            "non_index_concept_pages": concept_count,
            "non_index_entity_pages": entity_count,
            "concept_linked_source_pages": concept_linked_sources,
            "entity_linked_source_pages": entity_linked_sources,
            "concept_coverage": round(concept_coverage, 4),
            "entity_coverage": round(entity_coverage, 4),
            "manual_link_placeholders": manual_placeholders,
            "low_density_layers": low_density_layers,
        },
        "findings": findings,
    }
