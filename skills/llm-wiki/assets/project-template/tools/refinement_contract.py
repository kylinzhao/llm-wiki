#!/usr/bin/env python3
"""Summarize source-level semantic refinement contract state."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PENDING_MARKERS = [
    "Pending AI-native summary",
    "Pending extraction from source evidence",
    "Deterministic seed page.",
    "待完成 AI 原生摘要",
    "待从来源证据中提取",
    "确定性种子页。",
    "ai_refinement_state: pending",
    '"ai_refinement_state": "pending"',
    '"ai_refinement_state":"pending"',
    '"ai_refinement_state": "stale"',
    '"ai_refinement_state":"stale"',
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def refinement_status(project: Path) -> dict[str, Any]:
    path = project / "staging" / "refinement-status.md"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def completed_or_skipped_paths(status: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for key in ("completed", "skipped"):
        entries = status.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path") or entry.get("wiki_path")
            if isinstance(path, str) and path:
                paths.add(path)
    return paths


def page_has_pending_markers(text: str) -> bool:
    return any(marker in text for marker in PENDING_MARKERS)


def summarize_refinement_contract(project: Path, sample_limit: int = 20) -> dict[str, Any]:
    project = project.resolve()
    plan = read_json(project / "staging" / "refinement-plan.json")
    if not plan:
        return {
            "status": "missing_plan",
            "semantic_update_required": False,
            "required_count": 0,
            "pending_count": 0,
            "pending_status_record_count": 0,
            "pending_marker_count": 0,
            "missing_page_count": 0,
            "missing_raw_path_evidence_count": 0,
            "pending_pages": [],
        }
    if plan.get("semantic_update_required") is False:
        return {
            "status": "ok",
            "semantic_update_required": False,
            "required_count": 0,
            "pending_count": 0,
            "pending_status_record_count": 0,
            "pending_marker_count": 0,
            "missing_page_count": 0,
            "missing_raw_path_evidence_count": 0,
            "pending_pages": [],
        }

    status = refinement_status(project)
    recorded = completed_or_skipped_paths(status)
    pending_pages: list[dict[str, str]] = []
    missing_page_count = 0
    pending_status_record_count = 0
    pending_marker_count = 0
    missing_raw_path_evidence_count = 0
    required_pages = [item for item in plan.get("required_source_pages") or [] if isinstance(item, dict)]

    for item in required_pages:
        wiki_path = item.get("wiki_path")
        raw_path = item.get("raw_path")
        if not isinstance(wiki_path, str) or not wiki_path:
            continue
        page = project / wiki_path
        reasons: list[str] = []
        if not page.is_file():
            missing_page_count += 1
            reasons.append("missing_page")
        else:
            text = page.read_text(encoding="utf-8", errors="replace")
            if page_has_pending_markers(text) and wiki_path not in recorded:
                pending_marker_count += 1
                reasons.append("pending_marker")
            if isinstance(raw_path, str) and raw_path and raw_path not in text:
                missing_raw_path_evidence_count += 1
                reasons.append("missing_raw_path_evidence")
        if wiki_path not in recorded:
            pending_status_record_count += 1
            reasons.append("missing_status_record")
        if reasons and len(pending_pages) < sample_limit:
            pending_pages.append(
                {
                    "wiki_path": wiki_path,
                    "raw_path": str(raw_path or ""),
                    "reason": ",".join(reasons),
                }
            )

    pending_count = max(
        pending_status_record_count,
        pending_marker_count,
        missing_page_count,
        missing_raw_path_evidence_count,
    )
    return {
        "status": "needs_refinement" if pending_count else "ok",
        "semantic_update_required": bool(plan.get("semantic_update_required")),
        "required_count": len(required_pages),
        "pending_count": pending_count,
        "pending_status_record_count": pending_status_record_count,
        "pending_marker_count": pending_marker_count,
        "missing_page_count": missing_page_count,
        "missing_raw_path_evidence_count": missing_raw_path_evidence_count,
        "pending_pages": pending_pages,
    }
