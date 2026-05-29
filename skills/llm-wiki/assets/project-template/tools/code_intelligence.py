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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def compact_index_item(item: object) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    item_id = str(item.get("id") or item.get("slug") or item.get("name") or item.get("title") or "").strip()
    if not item_id:
        return None
    compact: dict[str, object] = {
        "id": item_id,
        "title": str(item.get("title") or item.get("name") or item_id),
    }
    for key in ("aliases", "keywords", "path", "source_path", "related_files"):
        value = item.get(key)
        if isinstance(value, list):
            compact[key] = [str(part) for part in value if str(part).strip()]
        elif isinstance(value, str) and value.strip():
            compact[key] = value.strip()
    return compact


def load_index_payload(project: Path, resolved: dict[str, object]) -> dict[str, object]:
    index_json = project / str(resolved.get("root", "")) / "index.json"
    if not index_json.is_file():
        return {}
    try:
        payload = json.loads(index_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def compact_index_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    values = payload.get(key, [])
    if not isinstance(values, list):
        return []
    compacted = [compact_index_item(item) for item in values]
    return [item for item in compacted if item is not None]


def parse_source_map(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    entries: list[dict[str, object]] = []
    warnings: list[str] = []
    if not path.is_file():
        return entries, warnings
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"line {line_number}: {exc.msg}")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"line {line_number}: expected object")
            continue
        compact: dict[str, object] = {}
        for key in ("path", "topic", "concept", "symbol", "kind", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                compact[key] = value.strip()
        if compact:
            entries.append(compact)
    return entries, warnings


def adapt_upstream_artifacts(project: Path, codebase_id: str, resolved: dict[str, object]) -> dict[str, object]:
    out_dir = project / "staging" / "code-graph" / codebase_id
    if resolved.get("upstream_type") == "none":
        return {
            "adapter_status": "skipped",
            "topic_count": 0,
            "concept_count": 0,
            "source_map_entries": 0,
            "warning_count": 0,
            "preferred_entry": "",
        }

    payload = load_index_payload(project, resolved)
    topics = compact_index_list(payload, "topics")
    concepts = compact_index_list(payload, "concepts")
    source_map_path = project / str(resolved.get("source_map_path", ""))
    source_map_entries, source_map_warnings = parse_source_map(source_map_path)
    warning_count = len(source_map_warnings)
    adapter_status = "ok_with_warnings" if warning_count else "ok"
    preferred_entry = str(resolved.get("index_path") or "")

    write_json(
        out_dir / "upstream-topics.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": resolved.get("upstream_type", "none"),
            "topics": topics,
        },
    )
    write_json(
        out_dir / "upstream-concepts.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": resolved.get("upstream_type", "none"),
            "concepts": concepts,
        },
    )
    write_json(
        out_dir / "upstream-source-map.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": resolved.get("upstream_type", "none"),
            "entries": source_map_entries,
            "warnings": source_map_warnings,
            "warning_count": warning_count,
        },
    )
    return {
        "adapter_status": adapter_status,
        "topic_count": len(topics),
        "concept_count": len(concepts),
        "source_map_entries": len(source_map_entries),
        "warning_count": warning_count,
        "preferred_entry": preferred_entry,
    }


def collect_upstream_summary(project: Path, codebase_id: str, resolved: dict[str, object]) -> dict[str, object]:
    summary = {
        "codebase_id": codebase_id,
        "upstream_type": resolved.get("upstream_type", "none"),
        "discovery_mode": resolved.get("discovery_mode", "none"),
        "root": resolved.get("root", ""),
        "index_path": resolved.get("index_path", ""),
        "adapter_status": "skipped",
        "preferred_entry": "",
        "topic_count": 0,
        "concept_count": 0,
        "source_map_entries": 0,
        "warning_count": 0,
    }
    if summary["upstream_type"] == "none":
        return summary

    summary.update(adapt_upstream_artifacts(project, codebase_id, resolved))
    return summary
