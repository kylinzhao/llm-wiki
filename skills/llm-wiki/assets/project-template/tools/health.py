#!/usr/bin/env python3
"""Validate an LLM Wiki project structure."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from wiki_preflight import (
    raw_code_evidence_preflight_failed,
    raw_dir_has_files,
    raw_evidence_preflight_failed,
    raw_code_has_codebases,
    wiki_expects_raw,
    wiki_expects_raw_code,
)


REQUIRED_PATHS = [
    "raw",
    "wiki/index.md",
    "wiki/overview.md",
    "docs/retrieval-playbook.md",
    "docs/build-and-maintenance.md",
    "staging/refinement-status.md",
]

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def markdown_pages(project: Path) -> list[Path]:
    wiki = project / "wiki"
    if not wiki.is_dir():
        return []
    return sorted(path for path in wiki.rglob("*.md") if path.is_file())


def build_page_index(pages: list[Path], project: Path) -> set[str]:
    names: set[str] = set()
    wiki = project / "wiki"
    for page in pages:
        rel = page.relative_to(wiki).with_suffix("").as_posix()
        names.add(rel)
        if rel.endswith("/index"):
            names.add(rel[: -len("/index")])
        names.add(page.stem)
    return names


def find_broken_links(project: Path, pages: list[Path]) -> list[dict[str, str]]:
    names = build_page_index(pages, project)
    broken: list[dict[str, str]] = []
    wiki = project / "wiki"
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        rel = page.relative_to(wiki).as_posix()
        for target in WIKILINK_RE.findall(text):
            normalized = target.strip().removesuffix(".md")
            if normalized not in names:
                broken.append({"page": rel, "target": target})
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report only.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    missing = [rel for rel in REQUIRED_PATHS if not (project / rel).exists()]
    has_business_context = (project / "BUSINESS_CONTEXT.md").is_file()
    pages = markdown_pages(project)
    source_pages = sorted((project / "wiki" / "sources").glob("*.md")) if (project / "wiki" / "sources").is_dir() else []
    drift_path = project / "staging" / "source-drift.json"
    source_drift = json.loads(drift_path.read_text(encoding="utf-8")) if drift_path.is_file() else {}
    stale_sources = source_drift.get("stale_sources", []) if isinstance(source_drift, dict) else []
    orphan_source_pages = source_drift.get("orphan_source_pages", []) if isinstance(source_drift, dict) else []
    empty_pages = [
        str(path.relative_to(project))
        for path in pages
        if path.stat().st_size == 0
    ]
    broken_links = find_broken_links(project, pages)

    expects_raw = wiki_expects_raw(project)
    expects_raw_code = wiki_expects_raw_code(project)
    raw_dir = project / "raw"
    raw_code_dir = project / "raw-code"
    has_raw_dir = raw_dir.is_dir()
    has_raw_files = raw_dir_has_files(raw_dir)
    has_raw_code_dir = raw_code_dir.is_dir()
    has_raw_code_codebases = raw_code_has_codebases(raw_code_dir)
    raw_gap_message = raw_evidence_preflight_failed(project)
    raw_code_gap_message = raw_code_evidence_preflight_failed(project)
    evidence_gaps: list[str] = []
    if raw_gap_message:
        evidence_gaps.append(raw_gap_message)
    if raw_code_gap_message:
        evidence_gaps.append(raw_code_gap_message)

    if expects_raw and has_raw_dir and has_raw_files:
        evidence_mode = "raw_ok"
    elif expects_raw and (not has_raw_dir or not has_raw_files):
        evidence_mode = "built_without_raw"
    elif not expects_raw:
        evidence_mode = "no_raw_expectation"
    else:
        evidence_mode = "unknown"

    if expects_raw_code and has_raw_code_dir and has_raw_code_codebases:
        code_evidence_mode = "raw_code_ok"
    elif expects_raw_code and (not has_raw_code_dir or not has_raw_code_codebases):
        code_evidence_mode = "built_without_raw_code"
    elif not expects_raw_code:
        code_evidence_mode = "no_raw_code_expectation"
    else:
        code_evidence_mode = "unknown"

    recommended_actions: list[str] = []
    if raw_gap_message:
        recommended_actions.append(
            "Restore raw/ (git submodule, sparse checkout, LFS, or internal sync), then run `uv run python tools/update_wiki.py`."
        )
    if raw_code_gap_message:
        recommended_actions.append(
            "Restore raw-code/<codebase_id>/, then run `uv run python tools/update_wiki.py` or at least scan_code + build_traceability."
        )

    wiki_built = (project / "wiki" / "index.md").is_file()
    query_may_work_without_full_evidence = wiki_built and bool(evidence_gaps)

    content_ok = not missing and not empty_pages and not broken_links and not stale_sources
    evidence_ok = not evidence_gaps
    report = {
        "generated_at": utc_now(),
        "project": str(project),
        "ok": content_ok and evidence_ok,
        "has_business_context": has_business_context,
        "missing_required_paths": missing,
        "wiki_pages": len(pages),
        "source_pages": len(source_pages),
        "empty_pages": empty_pages,
        "broken_wikilinks": broken_links,
        "stale_sources": stale_sources,
        "orphan_source_pages": orphan_source_pages,
        "expects_raw_evidence": expects_raw,
        "has_raw_dir": has_raw_dir,
        "has_raw_files": has_raw_files,
        "expects_raw_code_evidence": expects_raw_code,
        "has_raw_code_dir": has_raw_code_dir,
        "has_raw_code_codebases": has_raw_code_codebases,
        "evidence_mode": evidence_mode,
        "code_evidence_mode": code_evidence_mode,
        "evidence_gaps": evidence_gaps,
        "recommended_actions": recommended_actions,
        "query_may_work_without_full_evidence": query_may_work_without_full_evidence,
    }

    out = project / "staging" / "health" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        verdict = "pass" if report["ok"] else "fail"
        print(f"health={verdict}")
        print(f"missing={len(missing)} empty={len(empty_pages)} broken_links={len(broken_links)}")
        print(f"report={out}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
