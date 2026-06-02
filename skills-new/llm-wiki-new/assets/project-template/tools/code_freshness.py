#!/usr/bin/env python3
"""Track code scan freshness for raw-code codebases."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


STRUCTURAL_ROLES = {
    "api-contract",
    "async",
    "controller",
    "data-access",
    "job",
    "route",
    "service",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fact_role_by_relative_path(codebase: str, facts: list[dict[str, object]]) -> dict[str, str]:
    prefix = f"raw-code/{codebase}/"
    roles: dict[str, str] = {}
    for fact in facts:
        path = str(fact.get("path") or "")
        if path.startswith(prefix):
            roles[path.removeprefix(prefix)] = str(fact.get("role") or "module")
    return roles


def classify_change_level(
    *,
    changed_files: list[str],
    new_files: list[str],
    deleted_files: list[str],
    roles: dict[str, str],
) -> str:
    changed_total = len(changed_files) + len(new_files) + len(deleted_files)
    if changed_total == 0:
        return "none"
    if changed_total >= 5:
        return "high"
    structural_files = [path for path in changed_files + new_files + deleted_files if roles.get(path) in STRUCTURAL_ROLES]
    if structural_files:
        return "medium"
    return "low"


def compute_freshness(
    project: Path,
    codebase: str,
    root: Path,
    files: list[Path],
    facts: list[dict[str, object]],
) -> dict[str, object]:
    state_path = project / "staging" / "code-graph" / codebase / "freshness.json"
    previous = read_json(state_path)
    had_previous_state = bool(previous)
    previous_files = previous.get("files")
    previous_map = previous_files if isinstance(previous_files, dict) else {}
    roles = fact_role_by_relative_path(codebase, facts)
    current_map: dict[str, dict[str, object]] = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        current_map[rel] = {
            "sha256": file_hash(path),
            "role": roles.get(rel, "module"),
        }

    current_paths = set(current_map)
    previous_paths = {str(path) for path in previous_map}
    new_files = sorted(current_paths - previous_paths)
    deleted_files = sorted(previous_paths - current_paths)
    changed_files = sorted(
        path
        for path in current_paths & previous_paths
        if isinstance(previous_map.get(path), dict)
        and previous_map[path].get("sha256") != current_map[path]["sha256"]
    )
    unchanged_files = sorted(
        path
        for path in current_paths & previous_paths
        if isinstance(previous_map.get(path), dict)
        and previous_map[path].get("sha256") == current_map[path]["sha256"]
    )
    all_roles = {**{path: str(previous_map[path].get("role") or "module") for path in previous_paths if isinstance(previous_map.get(path), dict)}, **roles}
    level = classify_change_level(
        changed_files=changed_files,
        new_files=new_files,
        deleted_files=deleted_files,
        roles=all_roles,
    )
    if not had_previous_state and current_map:
        level = "high"
        changed_files = new_files[:]
    return {
        "codebase_id": codebase,
        "generated_at": utc_now(),
        "file_count": len(files),
        "structural_change_level": level,
        "changed_files": changed_files,
        "new_files": new_files,
        "deleted_files": deleted_files,
        "unchanged_files": unchanged_files,
        "files": current_map,
    }
