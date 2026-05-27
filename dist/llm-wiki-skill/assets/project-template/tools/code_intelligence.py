#!/usr/bin/env python3
"""Helpers for optional upstream code intelligence inputs."""

from __future__ import annotations

import json
from pathlib import Path


REGISTRY_RELATIVE_PATH = Path("staging/code-graph/code-intelligence-registry.json")

SUPPORTED_SIGNATURES: dict[str, list[str]] = {
    "guazi-flow-wiki": [
        "docs/wiki/INDEX.md",
        "docs/wiki/CONTEXT.md",
        "docs/wiki/schema.md",
        "docs/wiki/source-map.jsonl",
        "docs/wiki/index.json",
    ]
}


def registry_path(project: Path) -> Path:
    return project / REGISTRY_RELATIVE_PATH


def _default_entry(codebase_id: str) -> dict[str, object]:
    return {
        "codebase_id": codebase_id,
        "upstream_type": "none",
        "discovery_mode": "none",
        "root": "",
        "index_path": "",
        "schema_path": "",
        "source_map_path": "",
        "authority": "source-only",
        "status": "none",
        "notes": "",
    }


def load_code_intelligence_registry(project: Path) -> dict:
    path = registry_path(project)
    if not path.is_file():
        return {"codebases": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"codebases": {}}
    codebases = data.get("codebases")
    if not isinstance(codebases, dict):
        data["codebases"] = {}
    return data


def save_code_intelligence_registry(project: Path, registry: dict) -> None:
    path = registry_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_upstream_code_intelligence(project: Path, codebase_id: str) -> dict[str, object]:
    root = project / "raw-code" / codebase_id
    for upstream_type, signature in SUPPORTED_SIGNATURES.items():
        if all((root / rel).is_file() for rel in signature):
            wiki_root = Path("raw-code") / codebase_id / "docs" / "wiki"
            return {
                "codebase_id": codebase_id,
                "upstream_type": upstream_type,
                "discovery_mode": "auto-detected",
                "root": wiki_root.as_posix(),
                "index_path": (wiki_root / "INDEX.md").as_posix(),
                "schema_path": (wiki_root / "schema.md").as_posix(),
                "source_map_path": (wiki_root / "source-map.jsonl").as_posix(),
                "authority": "derived-upstream",
                "status": "detected",
                "notes": "",
            }
    return _default_entry(codebase_id)


def resolve_code_intelligence(project: Path, codebase_id: str) -> dict[str, object]:
    registry = load_code_intelligence_registry(project)
    codebases = registry.get("codebases", {})
    if isinstance(codebases, dict):
        entry = codebases.get(codebase_id)
        if isinstance(entry, dict):
            resolved = _default_entry(codebase_id)
            resolved.update(entry)
            resolved["codebase_id"] = codebase_id
            return resolved
    return detect_upstream_code_intelligence(project, codebase_id)


def _count_source_map_entries(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            count += 1
    return count


def collect_upstream_summary(project: Path, codebase_id: str, resolved: dict[str, object]) -> dict[str, object]:
    summary = {
        "codebase_id": codebase_id,
        "upstream_type": resolved.get("upstream_type", "none"),
        "discovery_mode": resolved.get("discovery_mode", "none"),
        "root": resolved.get("root", ""),
        "index_path": resolved.get("index_path", ""),
        "topic_count": 0,
        "concept_count": 0,
        "source_map_entries": 0,
    }
    if summary["upstream_type"] == "none":
        return summary

    index_json = project / str(resolved.get("root", "")) / "index.json"
    if index_json.is_file():
        payload = json.loads(index_json.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            topics = payload.get("topics", [])
            concepts = payload.get("concepts", [])
            if isinstance(topics, list):
                summary["topic_count"] = len(topics)
            if isinstance(concepts, list):
                summary["concept_count"] = len(concepts)

    source_map_path = project / str(resolved.get("source_map_path", ""))
    summary["source_map_entries"] = _count_source_map_entries(source_map_path)
    return summary
