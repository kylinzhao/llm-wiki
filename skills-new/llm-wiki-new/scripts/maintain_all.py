#!/usr/bin/env python3
"""Maintain registered local LLM Wiki KB projects."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_local_module(name: str):
    script_dir = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(f"llm_wiki_scripts_{name}", script_dir / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


project_registry = load_local_module("project_registry")


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


def git_output(project: Path, *args: str) -> tuple[int, str]:
    return run_command(["git", *args], project)


def git_has_path(project: Path) -> bool:
    return (project / ".git").exists()


def git_check_ignore(project: Path, path: str) -> bool:
    code, _ = git_output(project, "check-ignore", "-q", path)
    return code == 0


def git_ls_files(project: Path, path: str) -> list[str]:
    code, output = git_output(project, "ls-files", path)
    return output.splitlines() if code == 0 else []


def parse_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def inspect_project_preflight(project: Path) -> dict[str, Any]:
    blockers: list[str] = []
    repairable: list[str] = []
    warnings: list[str] = []

    if not (project / "raw").is_dir():
        blockers.append("missing_raw")
    if not (project / "wiki").is_dir():
        blockers.append("missing_wiki")
    if not (project / "tools" / "update_wiki.py").is_file():
        blockers.append("missing_tools_update_wiki")

    if git_has_path(project):
        status = git_ls_files(project, "raw")
        if status:
            blockers.append("raw_tracked_by_git")
        tracked_raw_code = git_ls_files(project, "raw-code")
        if tracked_raw_code:
            blockers.append("raw_code_tracked_by_git")
        if not git_check_ignore(project, "raw"):
            warnings.append("raw_not_ignored")
        if (project / "raw-code").exists() and not git_check_ignore(project, "raw-code"):
            warnings.append("raw_code_not_ignored")
        code, upstream = git_output(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if code != 0 or not upstream.strip():
            blockers.append("missing_git_upstream")
        else:
            code, counts = git_output(project, "rev-list", "--left-right", "--count", f"{upstream.strip()}...HEAD")
            if code == 0:
                behind, ahead = [int(part) for part in counts.split()[:2]]
                if behind:
                    blockers.append(f"behind_upstream:{behind}")
                if ahead:
                    blockers.append(f"ahead_upstream:{ahead}")

    raw_code = project / "raw-code"
    if raw_code.is_dir():
        manifest = project / "upstream" / "code-sources.json"
        if not manifest.is_file():
            repairable.append("missing_code_sources_manifest")
        for child in sorted(raw_code.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            metadata_path = child / ".llm-wiki-codebase.yaml"
            if not metadata_path.is_file():
                blockers.append(f"raw-code/{child.name}:missing_metadata")
                continue
            metadata = parse_simple_yaml(metadata_path)
            code, status = git_output(child, "status", "--porcelain")
            if code != 0:
                blockers.append(f"raw-code/{child.name}:invalid_git_checkout")
            elif status.strip():
                blockers.append(f"raw-code/{child.name}:dirty")
            repo_url = metadata.get("repo_url", "")
            if repo_url.startswith("/") or repo_url.startswith("./") or repo_url.startswith("../"):
                code, remote = git_output(child, "remote", "get-url", "origin")
                if code == 0 and remote.strip():
                    repairable.append(f"raw-code/{child.name}:local_repo_url_can_use_origin")
                else:
                    blockers.append(f"raw-code/{child.name}:local_repo_url_without_origin")

    return {"blockers": blockers, "repairable": repairable, "warnings": warnings}


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
        preflight = inspect_project_preflight(Path(path))
        hard_blockers = list(preflight.get("blockers") or [])
        if hard_blockers:
            skipped.append(
                {
                    "project": path,
                    "status": "skipped",
                    "reason": "preflight_blocked",
                    "preflight": preflight,
                }
            )
            continue
        planned.append(
            {
                "project": path,
                "status": "planned",
                "preflight": preflight,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Maintain registered local LLM Wiki KB projects.")
    parser.add_argument("--registry", help="Override registry path for tests or advanced local use.")
    parser.add_argument("--discover", action="append", default=[], help="Discover KB projects under this directory.")
    parser.add_argument("--list", action="store_true", help="List registered KB projects.")
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help="Immediately remove registry entries whose paths no longer exist.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the planned maintenance. Without this flag, only prints a dry-run plan.",
    )
    parser.add_argument("--project", action="append", default=[], help="Only include this absolute KB path.")
    parser.add_argument("--name", action="append", default=[], help="Only include projects with this registered name.")
    return parser.parse_args(argv)


def print_rows(rows: list[dict[str, str]]) -> None:
    print("status\tmissing\tlast_success\tpath\tlast_error")
    for row in rows:
        print(
            f"{row['status']}\t{row['missing_count']}\t{row['last_success_at']}\t"
            f"{row['path']}\t{row['last_error']}"
        )


def print_plan(plan: dict[str, Any]) -> None:
    print("Dry-run plan")
    for item in plan.get("planned") or []:
        print(f"PLAN {item['project']}")
        preflight = item.get("preflight") or {}
        if preflight.get("repairable"):
            print("  repairable=" + ",".join(preflight["repairable"]))
        if preflight.get("warnings"):
            print("  warnings=" + ",".join(preflight["warnings"]))
        for command in item.get("commands") or []:
            print(f"  + {command}")
    for item in plan.get("skipped") or []:
        print(f"SKIP {item['project']} reason={item['reason']}")
        preflight = item.get("preflight") or {}
        if preflight.get("blockers"):
            print("  blockers=" + ",".join(preflight["blockers"]))
        if preflight.get("repairable"):
            print("  repairable=" + ",".join(preflight["repairable"]))
    for item in plan.get("removed") or []:
        print(f"REMOVED {item.get('path')}")


def print_apply_summary(summary: dict[str, Any]) -> None:
    print("Apply summary")
    print(f"successes={summary['successes']}")
    print(f"failures={summary['failures']}")
    print(f"skipped={summary['skipped_count']}")
    print(f"json_report={summary['json_report']}")
    print(f"markdown_report={summary['markdown_report']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = Path(args.registry).expanduser().resolve() if args.registry else None

    for root in args.discover:
        for project in project_registry.discover_projects(Path(root).expanduser()):
            project_registry.register_project(project, registry_path=registry_path)

    if args.prune_missing:
        removed = project_registry.prune_missing(registry_path=registry_path)
        print(f"pruned={len(removed)}")
        return 0

    if args.list:
        project_registry.reconcile_registry(registry_path=registry_path)
        print_rows(project_registry.registry_rows(registry_path=registry_path))
        return 0

    plan = build_plan(registry_path=registry_path, projects=args.project, names=args.name)
    print_plan(plan)
    if args.apply:
        print_apply_summary(run_apply(plan, registry_path=registry_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
