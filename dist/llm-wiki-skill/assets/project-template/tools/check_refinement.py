#!/usr/bin/env python3
"""Validate semantic refinement against staging/refinement-plan.json."""

from __future__ import annotations

import argparse
from pathlib import Path

from refinement_contract import (
    completed_or_skipped_paths,
    page_has_pending_markers,
    read_json,
    refinement_status,
    summarize_code_refinement,
)


def check_project(project: Path) -> int:
    project = project.resolve()
    plan = read_json(project / "staging" / "refinement-plan.json")
    failures: list[str] = []
    if not plan:
        print("refinement_plan_missing")
    elif plan.get("semantic_update_required") is False:
        print("semantic_update_required=false")
    else:
        status = refinement_status(project)
        recorded = completed_or_skipped_paths(status)
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
            if page_has_pending_markers(text) and wiki_path not in recorded:
                failures.append(f"pending_required_page:{wiki_path}")
            if isinstance(raw_path, str) and raw_path and raw_path not in text:
                failures.append(f"missing_raw_path_evidence:{wiki_path}")
            if wiki_path not in recorded:
                failures.append(f"missing_status_record:{wiki_path}")

    code_refinement = summarize_code_refinement(project)
    if code_refinement["status"] == "needs_refinement":
        for item in code_refinement["pending_codebases"]:
            failures.append(f"pending_code_refinement:{item['codebase_id']}:{item['reason']}")

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
