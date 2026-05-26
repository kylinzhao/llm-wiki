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
    "BUSINESS_CONTEXT.md",
    "wiki/index.md",
    "wiki/overview.md",
    "docs/retrieval-playbook.md",
    "docs/build-and-maintenance.md",
    "staging/refinement-status.md",
]

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
DIAGRAM_EXTENSIONS = {".drawio", ".dio"}
IMAGE_VALUE_KEYWORDS = {
    "流程": 5,
    "流程图": 8,
    "状态": 4,
    "规则": 4,
    "费用": 6,
    "保证金": 7,
    "订金": 6,
    "风控": 7,
    "权限": 6,
    "验收": 6,
    "测试结论": 7,
    "数据表": 6,
    "埋点": 5,
    "上线": 3,
    "接口": 3,
    "退款": 7,
    "合同": 6,
    "发票": 6,
    "金融": 5,
    "账户": 6,
    "银行": 6,
    "push": 4,
    "AB": 3,
    "实验": 4,
}
BUSINESS_CONTEXT_PLACEHOLDER_MARKERS = {
    "请在首次构建前补全本文件",
    "项目名称：TODO",
    "目标用户/角色：TODO",
    "核心业务目标：TODO",
    "实体 A：TODO",
}


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
        if rel.startswith("sources/") and rel.endswith("-index"):
            names.add(rel[: -len("-index")])
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


def count_raw_images(project: Path) -> int:
    raw = project / "raw"
    if not raw.is_dir():
        return 0
    return sum(
        1
        for path in raw.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def count_raw_diagrams(project: Path) -> int:
    raw = project / "raw"
    if not raw.is_dir():
        return 0
    return sum(
        1
        for path in raw.rglob("*")
        if path.is_file() and path.suffix.lower() in DIAGRAM_EXTENSIONS
    )


def drawio_repair_status(project: Path) -> dict[str, object]:
    root = project / "raw"
    drawio_files = [
        path
        for path in root.rglob("*")
        if root.is_dir()
        and path.is_file()
        and path.suffix.lower() in DIAGRAM_EXTENSIONS
    ]
    missing = [
        path.relative_to(project).as_posix()
        for path in drawio_files
        if not path.with_suffix(path.suffix + ".md").is_file()
    ]
    report = {}
    report_path = project / "staging" / "drawio" / "latest.json"
    if report_path.is_file():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        report = payload if isinstance(payload, dict) else {}
    return {
        "drawio_count": len(drawio_files),
        "missing_evidence_count": len(missing),
        "missing_evidence": missing[:50],
        "last_report": {
            "generated_at": report.get("generated_at", ""),
            "converted_count": report.get("converted_count", 0),
            "unparsed_count": report.get("unparsed_count", 0),
            "changed_count": report.get("changed_count", 0),
        },
    }


def count_image_notes(project: Path) -> int:
    notes = project / "staging" / "image-notes"
    if not notes.is_dir():
        return 0
    return sum(1 for path in notes.rglob("*.md") if path.is_file())


def page_title(index_path: Path) -> str:
    text = index_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("#").strip()
        if stripped.startswith("title:"):
            return stripped.split(":", 1)[1].strip().strip('"')
    return index_path.parent.name


def source_page_for_raw_index(project: Path, index_path: Path) -> str | None:
    raw = project / "raw"
    try:
        rel_parent = index_path.parent.relative_to(raw)
    except ValueError:
        return None
    parts = rel_parent.parts
    if len(parts) < 2:
        return None
    collection = parts[0]
    page_dir = parts[-1]
    source_page = project / "wiki" / "sources" / f"{collection}-{page_dir}-index.md"
    if source_page.is_file():
        return source_page.relative_to(project).as_posix()
    matches = sorted((project / "wiki" / "sources").glob(f"*{page_dir}*index.md"))
    if matches:
        return matches[0].relative_to(project).as_posix()
    return None


def image_refinement_candidates(project: Path, limit: int = 20) -> list[dict]:
    raw = project / "raw"
    if not raw.is_dir():
        return []

    candidates: list[dict] = []
    for index_path in sorted(raw.rglob("index.md")):
        page_dir = index_path.parent
        images = [
            path
            for path in page_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in (IMAGE_EXTENSIONS | DIAGRAM_EXTENSIONS)
        ]
        if not images:
            continue

        text = index_path.read_text(encoding="utf-8", errors="replace")
        hits = [
            keyword
            for keyword in IMAGE_VALUE_KEYWORDS
            if keyword.lower() in text.lower()
        ]
        score = min(len(images), 20) + sum(IMAGE_VALUE_KEYWORDS[keyword] for keyword in hits)
        if not hits and len(images) < 3:
            continue

        candidates.append(
            {
                "raw_page": index_path.relative_to(project).as_posix(),
                "wiki_source_page": source_page_for_raw_index(project, index_path),
                "title": page_title(index_path),
                "image_count": len(images),
                "signals": hits[:12],
                "score": score,
            }
        )

    candidates.sort(key=lambda item: (-item["score"], -item["image_count"], item["raw_page"]))
    return candidates[:limit]


def refinement_status(project: Path) -> dict:
    status_path = project / "staging" / "refinement-status.md"
    if not status_path.is_file():
        return {}
    text = status_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def code_intelligence_status(project: Path) -> dict[str, object]:
    root = project / "staging" / "code-graph"
    detected: list[str] = []
    fallback_only: list[str] = []
    if not root.is_dir():
        return {"detected_codebases": detected, "fallback_only_codebases": fallback_only}
    for summary_path in sorted(root.glob("*/upstream-summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        codebase_id = str(payload.get("codebase_id") or summary_path.parent.name)
        upstream_type = str(payload.get("upstream_type") or "none")
        if upstream_type == "none":
            fallback_only.append(codebase_id)
        else:
            detected.append(codebase_id)
    return {"detected_codebases": detected, "fallback_only_codebases": fallback_only}


def business_context_status(project: Path) -> dict[str, object]:
    path = project / "BUSINESS_CONTEXT.md"
    if not path.is_file():
        return {
            "has_business_context": False,
            "has_valid_business_context": False,
            "business_context_status": "missing",
            "business_context_message": "BUSINESS_CONTEXT.md is required before llm-wiki init/fast/update.",
        }
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return {
            "has_business_context": True,
            "has_valid_business_context": False,
            "business_context_status": "empty",
            "business_context_message": "BUSINESS_CONTEXT.md exists but is empty; fill the business baseline before building.",
        }
    if any(marker in text for marker in BUSINESS_CONTEXT_PLACEHOLDER_MARKERS):
        return {
            "has_business_context": True,
            "has_valid_business_context": False,
            "business_context_status": "template_placeholder",
            "business_context_message": (
                "BUSINESS_CONTEXT.md still contains the template placeholder; replace TODOs with the "
                "project business boundary, canonical entities, rules, and evidence priority before building."
            ),
        }
    return {
        "has_business_context": True,
        "has_valid_business_context": True,
        "business_context_status": "ok",
        "business_context_message": "",
    }


def cjira_registry_status(project: Path) -> dict[str, object]:
    root = project / "staging" / "cjira-registry"

    def load_records(path: Path) -> list[dict[str, object]]:
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        records = payload.get("records") if isinstance(payload, dict) else []
        return [item for item in records if isinstance(item, dict)]

    active_records = load_records(root / "active.json")
    archive_records = load_records(root / "archive.json")
    try:
        cache_payload = json.loads((root / "cache.json").read_text(encoding="utf-8")) if (root / "cache.json").is_file() else {}
    except json.JSONDecodeError:
        cache_payload = {}
    if not isinstance(cache_payload, dict):
        cache_payload = {}

    all_records = [*active_records, *archive_records]
    return {
        "active_pages": len(active_records),
        "archived_pages": len(archive_records),
        "idea_pages": sum(1 for item in all_records if item.get("doc_status") == "idea"),
        "in_progress_pages": sum(1 for item in all_records if item.get("doc_status") == "in_progress"),
        "frozen_pages": sum(1 for item in all_records if item.get("doc_status") == "frozen"),
        "low_confidence_pages": sum(1 for item in all_records if item.get("confidence") == "low"),
        "stale_status_pages": sum(
            1 for item in cache_payload.values() if isinstance(item, dict) and item.get("fetch_failed") is True
        ),
    }


def build_report(project: Path) -> dict[str, object]:
    project = project.resolve()
    missing = [rel for rel in REQUIRED_PATHS if not (project / rel).exists()]
    business_context = business_context_status(project)
    if not business_context["has_valid_business_context"] and "BUSINESS_CONTEXT.md" not in missing:
        missing.append("BUSINESS_CONTEXT.md")
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

    raw_image_count = count_raw_images(project)
    raw_diagram_count = count_raw_diagrams(project)
    drawio_status = drawio_repair_status(project)
    image_note_count = count_image_notes(project)
    image_candidates = image_refinement_candidates(project)
    status_doc = refinement_status(project)
    image_evidence_status = str(status_doc.get("image_evidence_status", "")).strip() or "unknown"
    image_evidence_gaps: list[str] = []
    if (raw_image_count or raw_diagram_count) and image_note_count == 0 and image_evidence_status not in {"complete", "not_applicable", "skipped_by_user"}:
        image_evidence_gaps.append(
            "raw/ contains image or draw.io diagram assets but no staging/image-notes/ were found; after text/G+ completion, review high-value visual evidence with `llm-wiki image`."
        )
    if drawio_status["missing_evidence_count"]:
        image_evidence_gaps.append(
            f"raw/ contains {drawio_status['missing_evidence_count']} draw.io diagram(s) without generated .drawio.md text evidence; run `llm-wiki update` to repair draw.io evidence."
        )

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
            "Restore raw/ (git submodule, sparse checkout, LFS, or internal sync), then run `llm-wiki update`."
        )
    if raw_code_gap_message:
        recommended_actions.append(
            "Restore raw-code/<codebase_id>/, then run `llm-wiki update`."
        )
    if image_evidence_gaps:
        recommended_actions.append(
            "Run `llm-wiki image` for selective high-value image evidence after confirming the text layer is complete; do not batch-analyze low-value screenshots by default."
        )
    if drawio_status["missing_evidence_count"]:
        recommended_actions.insert(0, "Run `llm-wiki update` to generate missing draw.io Mermaid text evidence before semantic refinement.")
    if not business_context["has_valid_business_context"]:
        recommended_actions.insert(
            0,
            "Complete BUSINESS_CONTEXT.md with the project business baseline, canonical entities, rules, and evidence priority before running `llm-wiki init`, `llm-wiki fast`, or `llm-wiki update`.",
        )

    code_intelligence = code_intelligence_status(project)
    cjira_registry = cjira_registry_status(project)
    if cjira_registry["stale_status_pages"]:
        recommended_actions.append(
            "Refresh active cjira statuses with `llm-wiki update`; if Jira auth is missing, configure local SSO/Jira auth first."
        )
    wiki_built = (project / "wiki" / "index.md").is_file()
    query_may_work_without_full_evidence = wiki_built and bool(evidence_gaps)

    content_ok = not missing and not empty_pages and not broken_links and not stale_sources
    evidence_ok = not evidence_gaps
    ok = content_ok and evidence_ok
    report = {
        "generated_at": utc_now(),
        "project": str(project),
        "ok": ok,
        "status": "pass" if ok else "fail",
        "has_business_context": business_context["has_business_context"],
        "has_valid_business_context": business_context["has_valid_business_context"],
        "business_context_status": business_context["business_context_status"],
        "business_context_message": business_context["business_context_message"],
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
        "raw_image_assets": raw_image_count,
        "raw_drawio_assets": raw_diagram_count,
        "drawio_repair": drawio_status,
        "image_notes": image_note_count,
        "image_evidence_status": image_evidence_status,
        "image_evidence_gaps": image_evidence_gaps,
        "image_refinement_candidates": image_candidates,
        "cjira_registry": cjira_registry,
        "code_intelligence": code_intelligence,
        "recommended_actions": recommended_actions,
        "query_may_work_without_full_evidence": query_may_work_without_full_evidence,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report only.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    report = build_report(project)

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
