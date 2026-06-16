#!/usr/bin/env python3
"""Helpers for optional upstream code intelligence inputs."""

from __future__ import annotations

import json
from pathlib import Path


REGISTRY_RELATIVE_PATH = Path("staging/code-graph/code-intelligence-registry.json")

# File-based wiki signatures. ``structural-knowledge`` uses directory-based
# detection (see ``_detect_knowledge_upstream``) and is handled separately.
SUPPORTED_SIGNATURES: dict[str, list[str]] = {
    "guazi-flow-wiki": [
        "docs/wiki/INDEX.md",
        "docs/wiki/index.json",
    ],
    "structural-wiki": [
        "doc/wiki/index.md",
        "doc/wiki/overview.md",
        "doc/wiki/architecture.md",
    ],
}

# Knowledge directory marker — detected independently as a supplementary
# upstream source alongside the primary wiki type.
KNOWLEDGE_DIR_RELATIVE = Path("doc") / "knowledge"


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
        "knowledge_root": "",
        "knowledge_status": "none",
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


def _derive_wiki_root(codebase_id: str, signature: list[str]) -> Path:
    """Derive the wiki root directory from the first signature path."""
    first_rel = Path(signature[0])
    return Path("raw-code") / codebase_id / first_rel.parent


def _derive_index_path(wiki_root: Path, upstream_type: str) -> str:
    """Derive the preferred index/entry file path for a given upstream type."""
    if upstream_type == "structural-wiki":
        return (wiki_root / "index.md").as_posix()
    return (wiki_root / "INDEX.md").as_posix()


def _derive_schema_path(wiki_root: Path, upstream_type: str) -> str:
    """Derive the schema file path; structural-wiki has none."""
    if upstream_type == "structural-wiki":
        return ""
    return (wiki_root / "schema.md").as_posix()


def _derive_source_map_path(wiki_root: Path, upstream_type: str) -> str:
    """Derive the source-map path; structural-wiki has none."""
    if upstream_type == "structural-wiki":
        return ""
    return (wiki_root / "source-map.jsonl").as_posix()


def _has_markdown_files(directory: Path) -> bool:
    """Check if a directory contains at least one ``.md`` file recursively."""
    if not directory.is_dir():
        return False
    for _ in directory.rglob("*.md"):
        return True
    return False


def _detect_knowledge_upstream(project: Path, codebase_id: str) -> str:
    """Detect ``doc/knowledge/`` and return its relative path, or empty string."""
    knowledge_dir = project / "raw-code" / codebase_id / KNOWLEDGE_DIR_RELATIVE
    if not knowledge_dir.is_dir():
        return ""
    if not _has_markdown_files(knowledge_dir):
        return ""
    rel = Path("raw-code") / codebase_id / KNOWLEDGE_DIR_RELATIVE
    return rel.as_posix()


def detect_upstream_code_intelligence(project: Path, codebase_id: str) -> dict[str, object]:
    root = project / "raw-code" / codebase_id
    entry = None
    for upstream_type, signature in SUPPORTED_SIGNATURES.items():
        if all((root / rel).is_file() for rel in signature):
            wiki_root = _derive_wiki_root(codebase_id, signature)
            entry = {
                "codebase_id": codebase_id,
                "upstream_type": upstream_type,
                "discovery_mode": "auto-detected",
                "root": wiki_root.as_posix(),
                "index_path": _derive_index_path(wiki_root, upstream_type),
                "schema_path": _derive_schema_path(wiki_root, upstream_type),
                "source_map_path": _derive_source_map_path(wiki_root, upstream_type),
                "authority": "derived-upstream",
                "status": "detected",
                "notes": "",
            }
            break
    if entry is None:
        entry = _default_entry(codebase_id)

    # Supplementary: detect doc/knowledge/ independently of the wiki type.
    knowledge_root = _detect_knowledge_upstream(project, codebase_id)
    if knowledge_root:
        entry["knowledge_root"] = knowledge_root
        entry["knowledge_status"] = "detected"
    return entry


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


def _parse_structural_wiki_index(index_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse a structural-wiki index.md to extract module and API topics.

    Reads markdown links under known section headers (## 模块, ## 接口, ## API)
    and returns them as compact topic entries.
    """
    import re

    topics: list[dict[str, object]] = []
    concepts: list[dict[str, object]] = []
    if not index_path.is_file():
        return topics, concepts

    try:
        content = index_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return topics, concepts

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)

    current_section = ""
    last_pos = 0
    for match in section_pattern.finditer(content):
        section_title = match.group(1).strip()
        # Process content between last_pos and this section header
        block = content[last_pos:match.start()]
        _extract_links_from_block(block, current_section, link_pattern, topics, concepts)
        current_section = section_title
        last_pos = match.end()

    # Process remaining content after the last header
    block = content[last_pos:]
    _extract_links_from_block(block, current_section, link_pattern, topics, concepts)

    return topics, concepts


def _extract_links_from_block(
    block: str,
    section: str,
    link_pattern: "re.Pattern[str]",
    topics: list[dict[str, object]],
    concepts: list[dict[str, object]],
) -> None:
    """Extract markdown links from a block and classify them as topics or concepts."""
    is_topic_section = any(
        kw in section
        for kw in ("模块", "接口", "API", "总览", "业务", "核心", "Modules", "API")
    )
    is_concept_section = any(kw in section for kw in ("概念", "Concept"))
    if not is_topic_section and not is_concept_section:
        return

    for link_match in link_pattern.finditer(block):
        title = link_match.group(1).strip()
        path = link_match.group(2).strip()
        if not title or not path:
            continue
        entry: dict[str, object] = {
            "id": title,
            "title": title,
            "path": path,
        }
        if is_topic_section:
            topics.append(entry)
        else:
            concepts.append(entry)


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


def _adapt_guazi_flow_wiki(project: Path, codebase_id: str, resolved: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[str], str]:
    """Adapt guazi-flow-wiki upstream: read index.json + source-map.jsonl."""
    payload = load_index_payload(project, resolved)
    topics = compact_index_list(payload, "topics")
    concepts = compact_index_list(payload, "concepts")
    source_map_path = project / str(resolved.get("source_map_path", ""))
    source_map_entries, source_map_warnings = parse_source_map(source_map_path)
    preferred_entry = str(resolved.get("index_path") or "")
    return topics, concepts, source_map_entries, source_map_warnings, preferred_entry


def _adapt_structural_wiki(project: Path, codebase_id: str, resolved: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[str], str]:
    """Adapt structural-wiki upstream: parse index.md for module/API topics."""
    index_path = project / str(resolved.get("index_path", ""))
    topics, concepts = _parse_structural_wiki_index(index_path)
    preferred_entry = str(resolved.get("index_path") or "")
    return topics, concepts, [], [], preferred_entry


def _parse_structural_knowledge_dir(
    knowledge_root: Path,
    codebase_root: Path,
) -> list[dict[str, object]]:
    """Scan ``doc/knowledge/`` recursively and extract one topic per ``.md`` file.

    Title is taken from the first ``# header`` in the file, falling back to the
    filename stem.  Short README stubs (< 100 chars) are skipped.
    """
    import re

    h1_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    topics: list[dict[str, object]] = []
    if not knowledge_root.is_dir():
        return topics

    for md_file in sorted(knowledge_root.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""

        # Skip short README stubs
        if md_file.name == "README.md" and len(content.strip()) < 100:
            continue

        # Path relative to codebase root
        try:
            rel_path = md_file.relative_to(codebase_root)
        except ValueError:
            rel_path = md_file

        # Title from H1 header or filename
        h1_match = h1_pattern.search(content)
        title = h1_match.group(1).strip() if h1_match else md_file.stem

        topics.append({
            "id": title,
            "title": title,
            "path": rel_path.as_posix(),
            "source_type": "knowledge",
        })

    return topics


def _adapt_structural_knowledge(
    project: Path,
    codebase_id: str,
    knowledge_root_str: str,
) -> list[dict[str, object]]:
    """Adapt structural-knowledge: scan ``doc/knowledge/`` for domain knowledge topics."""
    knowledge_root = project / knowledge_root_str
    codebase_root = project / "raw-code" / codebase_id
    return _parse_structural_knowledge_dir(knowledge_root, codebase_root)


def adapt_upstream_artifacts(project: Path, codebase_id: str, resolved: dict[str, object]) -> dict[str, object]:
    out_dir = project / "staging" / "code-graph" / codebase_id
    upstream_type = str(resolved.get("upstream_type", "none"))

    topics: list[dict[str, object]] = []
    concepts: list[dict[str, object]] = []
    source_map_entries: list[dict[str, object]] = []
    source_map_warnings: list[str] = []
    preferred_entry = ""

    if upstream_type == "structural-wiki":
        topics, concepts, source_map_entries, source_map_warnings, preferred_entry = _adapt_structural_wiki(project, codebase_id, resolved)
    elif upstream_type == "guazi-flow-wiki":
        topics, concepts, source_map_entries, source_map_warnings, preferred_entry = _adapt_guazi_flow_wiki(project, codebase_id, resolved)

    # Supplementary: adapt doc/knowledge/ if detected (works even when no wiki)
    knowledge_root = str(resolved.get("knowledge_root", ""))
    knowledge_topics: list[dict[str, object]] = []
    if knowledge_root:
        knowledge_topics = _adapt_structural_knowledge(project, codebase_id, knowledge_root)
        topics.extend(knowledge_topics)

    warning_count = len(source_map_warnings)
    if upstream_type == "none" and knowledge_topics:
        adapter_status = "knowledge-only"
    elif upstream_type == "none":
        adapter_status = "skipped"
    elif warning_count:
        adapter_status = "ok_with_warnings"
    else:
        adapter_status = "ok"

    write_json(
        out_dir / "upstream-topics.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": upstream_type,
            "topics": topics,
        },
    )
    write_json(
        out_dir / "upstream-concepts.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": upstream_type,
            "concepts": concepts,
        },
    )
    # Write knowledge-specific output for downstream consumers
    write_json(
        out_dir / "upstream-knowledge.json",
        {
            "codebase_id": codebase_id,
            "knowledge_root": knowledge_root,
            "topics": knowledge_topics,
            "topic_count": len(knowledge_topics),
        },
    )
    write_json(
        out_dir / "upstream-source-map.json",
        {
            "codebase_id": codebase_id,
            "upstream_type": upstream_type,
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
        "knowledge_topic_count": len(knowledge_topics),
    }


def collect_upstream_summary(project: Path, codebase_id: str, resolved: dict[str, object]) -> dict[str, object]:
    summary = {
        "codebase_id": codebase_id,
        "upstream_type": resolved.get("upstream_type", "none"),
        "discovery_mode": resolved.get("discovery_mode", "none"),
        "root": resolved.get("root", ""),
        "index_path": resolved.get("index_path", ""),
        "knowledge_root": resolved.get("knowledge_root", ""),
        "knowledge_status": resolved.get("knowledge_status", "none"),
        "adapter_status": "skipped",
        "preferred_entry": "",
        "topic_count": 0,
        "concept_count": 0,
        "source_map_entries": 0,
        "warning_count": 0,
        "knowledge_topic_count": 0,
    }
    # Still adapt knowledge even when no wiki upstream is detected.
    if summary["upstream_type"] == "none" and not summary.get("knowledge_root"):
        return summary

    summary.update(adapt_upstream_artifacts(project, codebase_id, resolved))
    return summary
