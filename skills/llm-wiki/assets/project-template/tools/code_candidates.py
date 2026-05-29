#!/usr/bin/env python3
"""Build compact code capability and anchor candidates."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "candidate"


def rel_from_code_anchor(codebase: str, path: str) -> str:
    prefix = f"raw-code/{codebase}/"
    return path.removeprefix(prefix)


def scan_signals(fact: dict[str, object]) -> list[str]:
    signals: list[str] = []
    if fact.get("endpoints"):
        signals.append("scan_endpoint")
    if fact.get("routes"):
        signals.append("scan_route")
    if fact.get("symbols"):
        signals.append("scan_symbol")
    return signals


def source_map_by_path(entries: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        path = str(entry.get("path") or "").strip()
        if path:
            grouped.setdefault(path, []).append(entry)
    return grouped


def build_anchor_candidates(codebase: str, facts: list[dict[str, object]], source_map_entries: list[dict[str, object]]) -> list[dict[str, object]]:
    source_map = source_map_by_path(source_map_entries)
    candidates: list[dict[str, object]] = []
    for fact in facts:
        path = str(fact.get("path") or "")
        if not path:
            continue
        rel = rel_from_code_anchor(codebase, path)
        signals = scan_signals(fact)
        if rel in source_map:
            signals.append("upstream_source_map")
        if not signals:
            continue
        strength = "partial" if "upstream_source_map" in signals and any(signal.startswith("scan_") for signal in signals) else "candidate"
        candidates.append(
            {
                "codebase_id": codebase,
                "role": fact.get("role", "module"),
                "code_anchor": path,
                "signals": sorted(set(signals)),
                "source_files": [path],
                "upstream_refs": source_map.get(rel, []),
                "evidence_strength": strength,
                "requires_verification": True,
            }
        )
    return candidates


def build_capability_candidates(
    codebase: str,
    facts: list[dict[str, object]],
    topics: list[dict[str, object]],
    structure_edges: list[dict[str, object]],
) -> list[dict[str, object]]:
    facts_by_rel = {rel_from_code_anchor(codebase, str(fact.get("path") or "")): fact for fact in facts}
    candidates: list[dict[str, object]] = []
    for topic in topics:
        topic_id = str(topic.get("id") or topic.get("slug") or topic.get("title") or "").strip()
        title = str(topic.get("title") or topic_id)
        if not topic_id:
            continue
        related_files = [str(path) for path in topic.get("related_files", [])] if isinstance(topic.get("related_files"), list) else []
        matched_facts = [facts_by_rel[path] for path in related_files if path in facts_by_rel]
        signals = ["upstream_topic"]
        for fact in matched_facts:
            signals.extend(scan_signals(fact))
        if any(edge.get("source") in related_files or edge.get("target") in related_files for edge in structure_edges):
            signals.append("graph_neighbor")
        strength = "partial" if matched_facts else "inferred"
        candidates.append(
            {
                "codebase_id": codebase,
                "slug": slugify(topic_id),
                "title": title,
                "signals": sorted(set(signals)),
                "source_files": [str(fact.get("path")) for fact in matched_facts if fact.get("path")],
                "evidence_strength": strength,
                "requires_verification": True,
            }
        )
    return candidates


def build_code_candidates(project: Path, codebase: str) -> dict[str, object]:
    out_dir = project / "staging" / "code-graph" / codebase
    manifest = read_json(out_dir / "manifest.json", {})
    facts = manifest.get("facts", []) if isinstance(manifest, dict) else []
    facts = [fact for fact in facts if isinstance(fact, dict)]
    source_map = read_json(out_dir / "upstream-source-map.json", {})
    source_map_entries = source_map.get("entries", []) if isinstance(source_map, dict) else []
    source_map_entries = [entry for entry in source_map_entries if isinstance(entry, dict)]
    topics_payload = read_json(out_dir / "upstream-topics.json", {})
    topics = topics_payload.get("topics", []) if isinstance(topics_payload, dict) else []
    topics = [topic for topic in topics if isinstance(topic, dict)]
    structure = read_json(out_dir / "structure-summary.json", {})
    structure_edges = structure.get("edges", []) if isinstance(structure, dict) else []
    structure_edges = [edge for edge in structure_edges if isinstance(edge, dict)]

    anchors = build_anchor_candidates(codebase, facts, source_map_entries)
    capabilities = build_capability_candidates(codebase, facts, topics, structure_edges)
    write_json(
        out_dir / "anchor-candidates.json",
        {
            "generated_at": utc_now(),
            "codebase_id": codebase,
            "candidates": anchors,
        },
    )
    write_json(
        out_dir / "capability-candidates.json",
        {
            "generated_at": utc_now(),
            "codebase_id": codebase,
            "candidates": capabilities,
        },
    )
    return {
        "codebase_id": codebase,
        "anchor_candidate_count": len(anchors),
        "capability_candidate_count": len(capabilities),
    }
