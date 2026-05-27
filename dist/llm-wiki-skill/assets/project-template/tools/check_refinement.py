#!/usr/bin/env python3
"""Validate semantic refinement against staging/refinement-plan.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def refinement_status(project: Path) -> dict:
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


def completed_or_skipped_paths(status: dict) -> set[str]:
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
    markers = [
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
    return any(marker in text for marker in markers)


def check_project(project: Path) -> int:
    project = project.resolve()
    plan = read_json(project / "staging" / "refinement-plan.json")
    if not plan:
        print("refinement_plan_missing")
        return 0
    if plan.get("semantic_update_required") is False:
        print("semantic_update_required=false")
        return 0

    status = refinement_status(project)
    recorded = completed_or_skipped_paths(status)
    failures: list[str] = []
    for item in plan.get("required_source_pages") or []:
        if not isinstance(item, dict):
            continue
        wiki_path = item.get("wiki_path")
        raw_path = item.get("raw_path")
        if not isinstance(wiki_path, str) or not wiki_path:
            failures.append("required_source_page_missing_wiki_path")
            continue
        page = project / wiki_path
        if not page.is_file():
            failures.append(f"missing_required_page:{wiki_path}")
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        if page_has_pending_markers(text):
            failures.append(f"pending_required_page:{wiki_path}")
        if isinstance(raw_path, str) and raw_path and raw_path not in text:
            failures.append(f"missing_raw_path_evidence:{wiki_path}")
        if wiki_path not in recorded:
            failures.append(f"missing_status_record:{wiki_path}")

    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("refinement_ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()
    return check_project(Path(args.project))


if __name__ == "__main__":
    raise SystemExit(main())
