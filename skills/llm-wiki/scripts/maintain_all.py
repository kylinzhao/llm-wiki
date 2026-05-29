#!/usr/bin/env python3
"""Maintain registered local LLM Wiki KB projects."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import project_registry


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
MAX_OUTPUT_CHARS = 20_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_runs_dir() -> Path:
    return Path(os.environ.get("LLM_WIKI_MAINTENANCE_RUNS_DIR", "~/.llm-wiki/maintenance-runs")).expanduser()


def run_id_from_now(now: str) -> str:
    return now.replace(":", "").replace("+", "Z").replace("-", "").replace("T", "-")


def truncate_output(output: str) -> str:
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    return output[:MAX_OUTPUT_CHARS] + "\n...[truncated]\n"


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout


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


def run_python_tool_with_uv_fallback(script: str, project: Path) -> tuple[int, str]:
    code, output = run_command(["uv", "run", "python", script], project)
    if code == 0:
        return code, output
    fallback_code, fallback_output = run_command([sys.executable, script], project)
    if fallback_code == 0:
        return fallback_code, output + fallback_output
    return fallback_code, output + fallback_output


def run_project(plan_item: dict[str, Any]) -> dict[str, Any]:
    project = Path(str(plan_item["project"])).resolve()
    install = [
        sys.executable,
        str(SKILL_ROOT / "scripts" / "install_project_template.py"),
        "--project",
        str(project),
        "--engine-only",
        "--refresh-agent-rules",
    ]
    code, output = run_command(install, project)
    if code != 0:
        return {
            "project": str(project),
            "status": "failed",
            "reason": "install_project_template",
            "output": truncate_output(output),
            "tools_refreshed": False,
        }

    code, output = run_python_tool_with_uv_fallback("tools/backfill.py", project)
    if code != 0:
        return {
            "project": str(project),
            "status": "failed",
            "reason": "backfill",
            "output": truncate_output(output),
            "tools_refreshed": True,
        }

    backfill_report = project / "staging" / "backfill" / "latest.json"
    absorption_required = False
    if backfill_report.is_file():
        try:
            payload = json.loads(backfill_report.read_text(encoding="utf-8"))
            absorption_required = bool(payload.get("refinement_absorption_required"))
        except Exception:
            absorption_required = False

    update_report = project / "staging" / "update" / "latest.json"
    if absorption_required:
        code, output = run_python_tool_with_uv_fallback("tools/update_wiki.py", project)
        if code != 0:
            return {
                "project": str(project),
                "status": "failed",
                "reason": "update",
                "output": truncate_output(output),
                "tools_refreshed": True,
                "backfill_report": str(backfill_report),
            }

    return {
        "project": str(project),
        "status": "success",
        "tools_refreshed": True,
        "backfill_report": str(backfill_report),
        "update_report": str(update_report) if update_report.is_file() else "",
    }


def update_registry_after_results(results: list[dict[str, Any]], *, registry_path: Path | None, now: str) -> None:
    payload = project_registry.load_registry(registry_path)
    by_path = {str(item.get("path") or ""): item for item in payload.get("projects") or []}
    for result in results:
        project = str(result.get("project") or "")
        item = by_path.get(project)
        if item is None:
            continue
        if result.get("status") == "success":
            item["status"] = "active"
            item["last_success_at"] = now
            item["last_error"] = ""
            item["missing_count"] = 0
        elif result.get("status") == "failed":
            item["status"] = "failed"
            item["last_error"] = str(result.get("reason") or "failed")
    project_registry.save_registry(payload, registry_path)


def write_run_reports(run_id: str, payload: dict[str, Any], runs_dir: Path) -> tuple[Path, Path]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    json_report = runs_dir / f"{run_id}.json"
    markdown_report = runs_dir / f"{run_id}.md"
    json_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# LLM Wiki Maintain-All Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Successes: `{payload['successes']}`",
        f"- Failures: `{payload['failures']}`",
        f"- Skipped: `{payload['skipped_count']}`",
        "",
        "## Projects",
        "",
    ]
    for result in payload.get("results") or []:
        status = result.get("status")
        project = result.get("project")
        reason = result.get("reason", "")
        suffix = f" ({reason})" if reason else ""
        lines.append(f"- `{status}` `{project}`{suffix}")
    markdown_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_report, markdown_report


def run_apply(
    plan: dict[str, Any],
    *,
    registry_path: Path | None = None,
    runs_dir: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    generated_at = now or utc_now()
    results: list[dict[str, Any]] = []
    for item in plan.get("planned") or []:
        results.append(run_project(item))
    skipped = list(plan.get("skipped") or [])
    payload = {
        "version": 1,
        "run_id": run_id_from_now(generated_at),
        "generated_at": generated_at,
        "results": results,
        "skipped": skipped,
        "removed": list(plan.get("removed") or []),
        "successes": sum(1 for item in results if item.get("status") == "success"),
        "failures": sum(1 for item in results if item.get("status") == "failed"),
        "skipped_count": len(skipped),
    }
    update_registry_after_results(results, registry_path=registry_path, now=generated_at)
    json_report, markdown_report = write_run_reports(payload["run_id"], payload, runs_dir or default_runs_dir())
    payload["json_report"] = str(json_report)
    payload["markdown_report"] = str(markdown_report)
    return payload
