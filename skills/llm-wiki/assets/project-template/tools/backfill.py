#!/usr/bin/env python3
"""Backfill historical evidence and identify refinement absorption scope."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agent_rules import refresh_agent_rules
from build_wiki import (
    backfill_source_page,
    discover_sources,
    replace_or_insert_section,
    source_metadata_block,
    source_page_metadata,
)
from cjira_registry import discover_project_sources, read_registry, update_registry_for_sources
from drawio_repair import build_report as build_drawio_report
from drawio_repair import write_report as write_drawio_report
from project_registry import best_effort_register_current_project
from raw_code_manager import (
    RawCodeManagerError,
    is_local_repo_url,
    read_code_sources_manifest,
    read_codebase_metadata,
    run_git,
    validate_code_sources_manifest,
    write_codebase_metadata,
    write_code_sources_manifest,
)
from refinement_contract import refinement_status


BackfillPass = Callable[[Path], dict[str, object]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json_if_present(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_page_for(project: Path, source: dict[str, object]) -> Path:
    return project / "wiki" / "sources" / f"{source['slug']}.md"


def rel(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def pass_drawio(project: Path) -> dict[str, object]:
    report = build_drawio_report(project)
    write_drawio_report(project, report)
    affected_pages = sorted(
        str(record.get("page_index") or "")
        for record in report.get("records", [])
        if record.get("changed") is True and str(record.get("page_index") or "")
    )
    affected_evidence = sorted(
        str(record.get("evidence_path") or "")
        for record in report.get("records", [])
        if record.get("changed") is True and str(record.get("evidence_path") or "")
    )
    return {
        "status": "ok",
        "changed_count": int(report.get("changed_count") or 0),
        "drawio_count": int(report.get("drawio_count") or 0),
        "converted_count": int(report.get("converted_count") or 0),
        "unparsed_count": int(report.get("unparsed_count") or 0),
        "affected_raw_pages": affected_pages,
        "affected_evidence_pages": affected_evidence,
    }


def pass_source_metadata(project: Path) -> dict[str, object]:
    raw_dir = project / "raw"
    if not raw_dir.is_dir():
        return {
            "status": "skipped",
            "reason": "missing_raw",
            "changed_count": 0,
            "source_count": 0,
            "affected_source_pages": [],
        }

    changed_pages: list[str] = []
    sources = discover_sources(raw_dir)
    for source in sources:
        page = source_page_for(project, source)
        before = page.read_text(encoding="utf-8", errors="replace") if page.is_file() else None
        backfill_source_page(page, source, project)
        after = page.read_text(encoding="utf-8", errors="replace") if page.is_file() else None
        if before is not None and after is not None and before != after:
            changed_pages.append(rel(project, page))

    return {
        "status": "ok",
        "changed_count": len(changed_pages),
        "source_count": len(sources),
        "affected_source_pages": sorted(changed_pages),
    }


CONTENT_PENDING_MARKERS = (
    "Pending AI-native summary",
    "Pending extraction from source evidence",
    "Deterministic seed page.",
    "待完成 AI 原生摘要",
    "待从来源证据中提取",
    "确定性种子页。",
)

REFINED_STATES = {"applied", "complete", "completed", "refined"}


def text_without_source_metadata(text: str) -> str:
    return re.sub(r"(?ms)^## Source Metadata\s*```json\s*\{.*?\}\s*```\s*", "", text)


def has_heading(text: str, names: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?m)^##\s+{re.escape(name)}\s*$", text) for name in names)


def looks_refined_source_page(text: str) -> bool:
    content = text_without_source_metadata(text)
    if has_content_pending_markers(content):
        return False
    return (
        has_heading(content, ("Summary", "摘要"))
        and has_heading(content, ("Key Facts", "关键事实"))
        and has_heading(content, ("Business Links", "业务链接"))
        and has_heading(content, ("Evidence Notes", "证据说明"))
    )


def has_content_pending_markers(text: str) -> bool:
    return any(marker in text_without_source_metadata(text) for marker in CONTENT_PENDING_MARKERS)


def source_raw_rel_from_text(path: Path, metadata: dict[str, object]) -> str:
    raw_rel = metadata.get("raw_rel") if isinstance(metadata, dict) else None
    if isinstance(raw_rel, str) and raw_rel.strip():
        return raw_rel.strip()
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    match = re.search(r"(?:Raw path|原始路径):\s*`([^`]+)`", text)
    return match.group(1).strip() if match else ""


def write_refinement_status(project: Path, reconciled: list[dict[str, str]]) -> int:
    if not reconciled:
        return 0
    status = refinement_status(project)
    if not status:
        status = {}
    completed = status.get("completed")
    if not isinstance(completed, list):
        completed = []
    existing_paths = {
        str(entry.get("path") or entry.get("wiki_path") or "")
        for entry in completed
        if isinstance(entry, dict)
    }
    updated_at = utc_now()
    added_count = 0
    for item in reconciled:
        wiki_path = item["wiki_path"]
        if wiki_path in existing_paths:
            continue
        completed.append(
            {
                "path": wiki_path,
                "wiki_path": wiki_path,
                "raw_path": item.get("raw_path", ""),
                "status": "reconciled_from_existing_content",
                "source": "backfill.refinement_state_reconcile",
                "updated_at": updated_at,
            }
        )
        existing_paths.add(wiki_path)
        added_count += 1
    if added_count == 0:
        return 0
    status["completed"] = completed
    status["updated_at"] = updated_at
    (project / "staging").mkdir(parents=True, exist_ok=True)
    (project / "staging" / "refinement-status.md").write_text(
        "# Refinement Status\n\n```json\n" + json.dumps(status, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return added_count


def pass_refinement_state_reconcile(project: Path) -> dict[str, object]:
    sources_dir = project / "wiki" / "sources"
    if not sources_dir.is_dir():
        return {
            "status": "skipped",
            "reason": "missing_source_pages",
            "changed_count": 0,
            "source_count": 0,
            "reconciled_source_pages": [],
            "affected_source_pages": [],
        }

    changed_pages: list[str] = []
    reconciled_records: list[dict[str, str]] = []
    source_pages = sorted(sources_dir.glob("*.md"))
    for page in source_pages:
        before = page.read_text(encoding="utf-8", errors="replace")
        metadata = source_page_metadata(page)
        state = str(metadata.get("ai_refinement_state") or "").strip().lower()
        should_reconcile = (
            (state in REFINED_STATES and not has_content_pending_markers(before))
            or (state == "pending" and looks_refined_source_page(before))
        )
        if not should_reconcile:
            continue
        metadata["ai_refinement_state"] = "refined"
        after = replace_or_insert_section(before, "Source Metadata", source_metadata_block(metadata))
        wiki_path = rel(project, page)
        raw_path = source_raw_rel_from_text(page, metadata)
        if after != before:
            page.write_text(after, encoding="utf-8")
            changed_pages.append(wiki_path)
        reconciled_records.append({"wiki_path": wiki_path, "raw_path": raw_path})

    status_added_count = write_refinement_status(project, reconciled_records)
    return {
        "status": "ok",
        "changed_count": len(changed_pages) + status_added_count,
        "metadata_changed_count": len(changed_pages),
        "status_record_added_count": status_added_count,
        "source_count": len(source_pages),
        "reconciled_source_pages": sorted(item["wiki_path"] for item in reconciled_records),
        "affected_source_pages": sorted(changed_pages),
    }


def registry_records_snapshot(project: Path) -> dict[str, object]:
    active, archive, cache = read_registry(project)
    return {
        "active": active,
        "archive": archive,
        "cache": cache,
    }


def pass_cjira(project: Path) -> dict[str, object]:
    before = registry_records_snapshot(project)
    sources = discover_project_sources(project)
    registry_report = update_registry_for_sources(project, sources, refresh_status=False)
    after = registry_records_snapshot(project)
    changed = before != after
    affected = sorted(
        f"wiki/sources/{Path(str(source.get('raw_path') or '')).with_suffix('').as_posix().replace('raw/', '').replace('/', '-')}.md"
        for source in sources
        if str(source.get("raw_path") or "")
    )
    return {
        "status": "ok",
        "changed_count": 1 if changed else 0,
        "source_count": len(sources),
        "active_pages": registry_report.get("active_pages", 0),
        "archived_pages": registry_report.get("archived_pages", 0),
        "refreshed": False,
        "affected_source_pages": affected if changed else [],
    }


def pass_agent_rules(project: Path) -> dict[str, object]:
    status = refresh_agent_rules(project)
    return {
        "status": status,
        "changed_count": 1 if status in {"created", "updated"} else 0,
        "affected_files": ["AGENTS.md"] if status in {"created", "updated"} else [],
    }


def copy_legacy_export_item(project: Path, src: Path, dst: Path) -> str | None:
    if not src.exists() or dst.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return rel(project, dst)


def pass_wiki_export_state(project: Path) -> dict[str, object]:
    canonical = project / "staging" / "wiki-export-state"
    affected: list[str] = []
    for legacy_dir in (project / "staging" / "wiki-export", project / "raw"):
        copied = copy_legacy_export_item(project, legacy_dir / "export-state.json", canonical / "export-state.json")
        if copied:
            affected.append(copied)
        copied = copy_legacy_export_item(project, legacy_dir / "progress", canonical / "progress")
        if copied:
            affected.append(copied)
    return {
        "status": "ok",
        "changed_count": 1 if affected else 0,
        "affected_files": sorted(affected),
    }


def pass_code_sources(project: Path) -> dict[str, object]:
    raw_code = project / "raw-code"
    if not raw_code.is_dir():
        return {
            "status": "skipped",
            "reason": "missing_raw_code",
            "changed_count": 0,
            "codebase_count": 0,
            "affected_files": [],
        }

    sources: list[dict[str, object]] = []
    changed_metadata: list[str] = []
    blocked: list[dict[str, str]] = []
    for entry in sorted(raw_code.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        metadata = read_codebase_metadata(entry)
        if not metadata:
            blocked.append({"codebase_id": entry.name, "reason": "missing_llm_wiki_codebase_metadata"})
            continue
        codebase_id = str(metadata.get("codebase_id") or entry.name)
        repo_url = str(metadata.get("repo_url") or "")
        if is_local_repo_url(repo_url):
            remote = run_git(["remote", "get-url", "origin"], cwd=entry)
            if remote.returncode == 0 and remote.stdout.strip():
                repo_url = remote.stdout.strip()
            else:
                blocked.append({"codebase_id": entry.name, "reason": "local_repo_url_without_origin_remote"})
                continue
        source = {
            "codebase_id": codebase_id,
            "repo_url": repo_url,
            "origin_ref": str(metadata.get("origin_ref") or metadata.get("default_branch") or ""),
            "default_branch": str(metadata.get("default_branch") or metadata.get("origin_ref") or ""),
            "target_dir": f"raw-code/{codebase_id}",
            "enabled": True,
            "managed": True,
            "sync": {"mode": "ff-only"},
        }
        sources.append(source)
        expected_metadata = {
            "codebase_id": codebase_id,
            "repo_url": str(source["repo_url"]),
            "origin_ref": str(source["origin_ref"]),
            "default_branch": str(source["default_branch"]),
            "managed_path": str(source["target_dir"]),
        }
        if any(metadata.get(key) != value for key, value in expected_metadata.items()):
            write_codebase_metadata(entry, expected_metadata)
            changed_metadata.append(f"{source['target_dir']}/.llm-wiki-codebase.yaml")

    try:
        normalized = validate_code_sources_manifest({"version": 1, "sources": sources}, shared_mode=True, project=project)
    except RawCodeManagerError as exc:
        return {
            "status": "failed",
            "changed_count": 0,
            "codebase_count": len(sources),
            "blocked": blocked,
            "error": str(exc),
        }

    before = read_code_sources_manifest(project)
    after = {"version": 1, "sources": normalized}
    manifest_changed = before != after
    if manifest_changed:
        write_code_sources_manifest(project, after)
    affected_files = []
    if manifest_changed:
        affected_files.append("upstream/code-sources.json")
    affected_files.extend(changed_metadata)

    return {
        "status": "ok",
        "changed_count": len(affected_files),
        "codebase_count": len(normalized),
        "blocked": blocked,
        "affected_files": affected_files,
    }


BACKFILL_PASSES: tuple[tuple[str, BackfillPass], ...] = (
    ("wiki_export_state", pass_wiki_export_state),
    ("code_sources", pass_code_sources),
    ("drawio", pass_drawio),
    ("source_metadata", pass_source_metadata),
    ("refinement_state_reconcile", pass_refinement_state_reconcile),
    ("cjira", pass_cjira),
    ("agent_rules", pass_agent_rules),
)


def merge_scope(project: Path, passes: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    source_pages: set[str] = set()
    raw_pages: set[str] = set()
    evidence_pages: set[str] = set()
    files: set[str] = set()

    for result in passes.values():
        source_pages.update(str(item) for item in result.get("affected_source_pages", []) if str(item))
        raw_pages.update(str(item) for item in result.get("affected_raw_pages", []) if str(item))
        evidence_pages.update(str(item) for item in result.get("affected_evidence_pages", []) if str(item))
        files.update(str(item) for item in result.get("affected_files", []) if str(item))

    for raw_page in raw_pages:
        raw_path = project / raw_page
        if not raw_path.is_file():
            continue
        raw_dir = project / "raw"
        try:
            raw_rel = raw_path.relative_to(raw_dir)
        except ValueError:
            continue
        candidate = project / "wiki" / "sources" / f"{raw_rel.with_suffix('').as_posix().replace('/', '-')}.md"
        if candidate.is_file():
            source_pages.add(rel(project, candidate))

    return {
        "source_pages": sorted(source_pages),
        "raw_pages": sorted(raw_pages),
        "evidence_pages": sorted(evidence_pages),
        "files": sorted(files),
    }


def write_markdown_report(project: Path, report: dict[str, object]) -> None:
    out = project / "staging" / "backfill" / "latest.md"
    lines = [
        "# LLM Wiki Backfill Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Refinement absorption required: `{str(report['refinement_absorption_required']).lower()}`",
        f"- Next command: `{report['next_command']}`",
        "",
        "## Passes",
        "",
    ]
    for name, result in (report.get("passes") or {}).items():
        lines.append(f"- `{name}`: status `{result.get('status')}`, changed `{result.get('changed_count', 0)}`")
    scope = report.get("refinement_scope") or {}
    lines.extend(["", "## Refinement Scope", ""])
    for key in ("source_pages", "raw_pages", "evidence_pages", "files"):
        values = list(scope.get(key) or [])
        if values:
            lines.append(f"- {key}: " + ", ".join(f"`{item}`" for item in values))
        else:
            lines.append(f"- {key}: none")
    lines.extend(
        [
            "",
            "## Guidance",
            "",
            "Backfill has only repaired deterministic evidence. Continue with `llm-wiki update` semantics to absorb changed evidence into source summaries, concepts, entities, G+ layers, query acceptance, health, and graph.",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_backfill(project: Path) -> dict[str, object]:
    project = project.resolve()
    best_effort_register_current_project(project)
    passes: dict[str, dict[str, object]] = {}
    for name, runner in BACKFILL_PASSES:
        try:
            passes[name] = runner(project)
        except Exception as exc:
            passes[name] = {
                "status": "failed",
                "changed_count": 0,
                "error": str(exc),
            }

    scope = merge_scope(project, passes)
    changed_count = sum(int(result.get("changed_count") or 0) for result in passes.values())
    has_failure = any(result.get("status") == "failed" for result in passes.values())
    report = {
        "version": 1,
        "status": "failed" if has_failure else "ok",
        "generated_at": utc_now(),
        "project": str(project),
        "passes": passes,
        "changed_count": changed_count,
        "refinement_absorption_required": changed_count > 0,
        "refinement_scope": scope,
        "next_command": "llm-wiki update" if changed_count > 0 else "llm-wiki doctor",
    }
    write_json(project / "staging" / "backfill" / "latest.json", report)
    write_markdown_report(project, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()
    report = run_backfill(Path(args.project))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
