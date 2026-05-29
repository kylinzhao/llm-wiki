#!/usr/bin/env python3
"""Maintain registered local LLM Wiki KB projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import project_registry


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]


def build_plan(
    *,
    registry_path: Path | None = None,
    projects: list[str] | None = None,
    names: list[str] | None = None,
) -> dict[str, Any]:
    reconcile = project_registry.reconcile_registry(registry_path=registry_path)
    registry = reconcile["registry"]
    selected_projects = {str(Path(project).resolve()) for project in projects or []}
    selected_names = set(names or [])
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in registry.get("projects") or []:
        path = str(item.get("path") or "")
        name = str(item.get("name") or "")
        if selected_projects and path not in selected_projects:
            continue
        if selected_names and name not in selected_names:
            continue
        status = str(item.get("status") or "")
        if status != "active":
            skipped.append({"project": path, "status": "skipped", "reason": status or "not_active"})
            continue
        if project_registry.git_worktree_dirty(Path(path)):
            skipped.append({"project": path, "status": "skipped", "reason": "dirty_project_worktree"})
            continue
        planned.append(
            {
                "project": path,
                "status": "planned",
                "commands": [
                    f"python3 {SKILL_ROOT / 'scripts' / 'install_project_template.py'} --project {path} --engine-only --refresh-agent-rules",
                    "uv run python tools/backfill.py",
                ],
            }
        )

    return {"planned": planned, "skipped": skipped, "removed": reconcile.get("removed", [])}
