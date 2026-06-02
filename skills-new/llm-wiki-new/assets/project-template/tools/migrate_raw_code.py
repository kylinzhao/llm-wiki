#!/usr/bin/env python3
"""Migrate legacy raw-code layouts to the managed git contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from backfill import pass_code_sources
from raw_code_manager import METADATA_FILENAME, detect_default_branch, read_codebase_metadata, run_git, write_codebase_metadata

GITLINK_MODE = "160000"
RAW_CODE_IGNORE_LINE = "raw-code/"


def is_git_repo(project: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def is_git_checkout(path: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def tracked_raw_code_index_entries(project: Path) -> list[tuple[str, str]]:
    if not is_git_repo(project):
        return []
    result = subprocess.run(
        ["git", "ls-files", "-s", "--", "raw-code"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        entries.append((parts[0], parts[-1]))
    return entries


def tracked_raw_code_gitlinks(project: Path) -> list[str]:
    return [path for mode, path in tracked_raw_code_index_entries(project) if mode == GITLINK_MODE]


def raw_code_is_gitignored(project: Path) -> bool:
    if not is_git_repo(project):
        return True
    result = subprocess.run(
        ["git", "check-ignore", "-q", "raw-code/"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def ensure_raw_code_gitignore(project: Path) -> bool:
    path = project / ".gitignore"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.rstrip("/") in {"raw-code", "raw-code/"}:
            return False
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(RAW_CODE_IGNORE_LINE)
    next_text = "\n".join(lines).rstrip() + "\n"
    old_text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if old_text == next_text:
        return False
    path.write_text(next_text, encoding="utf-8")
    return True


def untrack_raw_code_gitlinks(project: Path, *, apply: bool) -> list[str]:
    actions: list[str] = []
    for gitlink in tracked_raw_code_gitlinks(project):
        if apply:
            subprocess.run(
                ["git", "rm", "--cached", "-f", gitlink],
                cwd=project,
                check=True,
                capture_output=True,
                text=True,
            )
        actions.append(f"untracked_gitlink:{gitlink}")
    return actions


def resolve_origin_repo_url(path: Path) -> str:
    remote = run_git(["remote", "get-url", "origin"], cwd=path)
    if remote.returncode == 0 and remote.stdout.strip():
        return remote.stdout.strip()
    return str(path.resolve())


def adopt_existing_git_codebase(path: Path) -> None:
    branch = detect_default_branch(path)
    codebase_id = path.name
    write_codebase_metadata(
        path,
        {
            "codebase_id": codebase_id,
            "repo_url": resolve_origin_repo_url(path),
            "origin_ref": branch,
            "default_branch": branch,
            "managed_path": f"raw-code/{codebase_id}",
        },
    )


def migrate_legacy_raw_code(project: Path) -> dict[str, object]:
    raw_code = project / "raw-code"
    report: dict[str, object] = {"converted": [], "blocked": []}
    if not raw_code.is_dir():
        return report

    for entry in sorted(raw_code.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            report["blocked"].append({"codebase_id": entry.name, "reason": "symlink_requires_manual_readd"})
            continue
        if not entry.is_dir():
            continue
        if read_codebase_metadata(entry):
            continue
        if is_git_checkout(entry):
            adopt_existing_git_codebase(entry)
            report["converted"].append(entry.name)
            continue
        report["blocked"].append({"codebase_id": entry.name, "reason": "missing_repository_identity"})

    return report


def migrate_shared_raw_code_evidence(project: Path, *, apply: bool) -> dict[str, object]:
    actions: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    gitlinks = tracked_raw_code_gitlinks(project)
    tracked_non_gitlink = [
        path
        for mode, path in tracked_raw_code_index_entries(project)
        if mode != GITLINK_MODE
    ]

    if gitlinks:
        warnings.append(f"tracked_raw_code_gitlinks:{len(gitlinks)}")
    if tracked_non_gitlink:
        warnings.append(f"tracked_raw_code_paths:{len(tracked_non_gitlink)}")
    if (project / "raw-code").exists() and not raw_code_is_gitignored(project):
        warnings.append("raw_code_not_ignored")

    if apply:
        if ensure_raw_code_gitignore(project):
            actions.append("updated:.gitignore")
        actions.extend(untrack_raw_code_gitlinks(project, apply=True))
        for path in tracked_non_gitlink:
            subprocess.run(
                ["git", "rm", "--cached", "-f", path],
                cwd=project,
                check=True,
                capture_output=True,
                text=True,
            )
            actions.append(f"untracked:{path}")
        warnings = []
        gitlinks = []
        tracked_non_gitlink = []
        if (project / "raw-code").exists() and not raw_code_is_gitignored(project):
            warnings.append("raw_code_not_ignored")

    legacy = migrate_legacy_raw_code(project)
    actions.extend([f"adopted_metadata:{name}" for name in legacy.get("converted", [])])
    for item in legacy.get("blocked", []):
        blockers.append(f"{item['codebase_id']}:{item['reason']}")

    code_sources_report: dict[str, object] = {"status": "skipped", "reason": "dry_run"}
    if apply and (project / "raw-code").is_dir():
        code_sources_report = pass_code_sources(project)
        if code_sources_report.get("status") == "failed":
            blockers.append(f"code_sources:{code_sources_report.get('error', 'failed')}")
        elif code_sources_report.get("changed_count"):
            actions.append("wrote:upstream/code-sources.json")

    status = "blocked" if blockers else "needs_migration" if warnings else "ok"
    return {
        "status": status,
        "actions": actions,
        "warnings": warnings,
        "blockers": blockers,
        "legacy": legacy,
        "code_sources": code_sources_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--apply", action="store_true", help="Rewrite .gitignore, untrack gitlinks, adopt metadata, write code-sources.json.")
    parser.add_argument("--report-json", action="store_true", help="Print the migration report as JSON.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if args.apply:
        report = migrate_shared_raw_code_evidence(project, apply=True)
    else:
        report = migrate_shared_raw_code_evidence(project, apply=False)
    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={report['status']}")
        for warning in report.get("warnings", []):
            print(f"warning={warning}")
        for blocker in report.get("blockers", []):
            print(f"blocker={blocker}")
        for action in report.get("actions", []):
            print(f"action={action}")
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
