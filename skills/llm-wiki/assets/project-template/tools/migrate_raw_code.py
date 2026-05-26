#!/usr/bin/env python3
"""Migrate legacy raw-code layouts to the managed git contract."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from raw_code_manager import METADATA_FILENAME, detect_default_branch, read_codebase_metadata, write_codebase_metadata


def is_git_checkout(path: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def adopt_existing_git_codebase(path: Path) -> None:
    branch = detect_default_branch(path)
    write_codebase_metadata(
        path,
        {
            "codebase_id": path.name,
            "repo_url": str(path.resolve()),
            "origin_ref": branch,
            "default_branch": branch,
            "managed_path": str(path),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--report-json", action="store_true", help="Print the migration report as JSON.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    report = migrate_legacy_raw_code(project)
    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"converted={len(report['converted'])}")
        print(f"blocked={len(report['blocked'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
