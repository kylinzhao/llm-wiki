#!/usr/bin/env python3
"""Best-effort local project registry helper for copied KB tools."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_registry_path() -> Path:
    return Path(os.environ.get("LLM_WIKI_PROJECT_REGISTRY", "~/.llm-wiki/projects.json")).expanduser()


def load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": REGISTRY_VERSION, "projects": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": REGISTRY_VERSION, "projects": []}
    if not isinstance(payload, dict):
        return {"version": REGISTRY_VERSION, "projects": []}
    projects = payload.get("projects")
    if not isinstance(projects, list):
        projects = []
    return {"version": int(payload.get("version") or REGISTRY_VERSION), "projects": projects}


def save_registry(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register_current_project(
    project: Path,
    *,
    registry_path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    seen_at = now or utc_now()
    root = project.resolve()
    path = registry_path or default_registry_path()
    payload = load_registry(path)
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
    save_registry(payload, path)
    return existing


def best_effort_register_current_project(project: Path) -> None:
    try:
        register_current_project(project)
    except Exception as exc:
        print(f"registry_warning={exc}", file=sys.stderr)
