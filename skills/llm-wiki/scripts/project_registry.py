#!/usr/bin/env python3
"""Local registry of LLM Wiki KB projects on this machine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_registry_path() -> Path:
    return Path(os.environ.get("LLM_WIKI_PROJECT_REGISTRY", "~/.llm-wiki/projects.json")).expanduser()


def empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "projects": []}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_registry_path()
    if not registry_path.is_file():
        return empty_registry()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return empty_registry()
    if not isinstance(payload, dict):
        return empty_registry()
    projects = payload.get("projects")
    if not isinstance(projects, list):
        projects = []
    return {"version": int(payload.get("version") or REGISTRY_VERSION), "projects": projects}


def save_registry(payload: dict[str, Any], path: Path | None = None) -> None:
    registry_path = path or default_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_kb_project(path: Path) -> bool:
    root = path.resolve()
    if (root / "kb.manifest.yaml").is_file() and (root / "tools" / "update_wiki.py").is_file():
        return True
    return (root / "BUSINESS_CONTEXT.md").is_file() and (root / "wiki").is_dir() and (root / "staging").is_dir()


def register_project(
    project: Path,
    *,
    registry_path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    seen_at = now or utc_now()
    root = project.resolve()
    payload = load_registry(registry_path)
    projects = list(payload.get("projects") or [])
    existing = next((item for item in projects if item.get("path") == str(root)), None)
    if existing is None:
        existing = {
            "path": str(root),
            "name": root.name,
            "first_seen_at": seen_at,
            "last_seen_at": seen_at,
            "last_success_at": "",
            "status": "active",
            "missing_count": 0,
            "last_error": "",
        }
        projects.append(existing)
    else:
        existing.setdefault("first_seen_at", seen_at)
        existing["name"] = existing.get("name") or root.name
        existing["last_seen_at"] = seen_at
        existing["status"] = "active"
        existing["missing_count"] = 0
        existing["last_error"] = ""
    payload["projects"] = sorted(projects, key=lambda item: str(item.get("path") or ""))
    save_registry(payload, registry_path)
    return existing
