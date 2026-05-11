#!/usr/bin/env python3
"""Run the deterministic LLM Wiki update pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from wiki_preflight import raw_code_evidence_preflight_failed, raw_evidence_preflight_failed


def run(script: Path, project: Path, extra: list[str] | None = None) -> int:
    command = [sys.executable, str(script), "--project", str(project)]
    if extra:
        command.extend(extra)
    print("+ " + " ".join(command))
    return subprocess.call(command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument(
        "--graphify",
        action="store_true",
        help="Also run graphify for all raw-code codebases. Missing graphify is recorded as skipped.",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    err = raw_evidence_preflight_failed(project)
    if err:
        print(err, file=sys.stderr)
        return 2

    tools = project / "tools"
    steps = [
        (tools / "build_wiki.py", []),
        (tools / "scan_code.py", []),
        (tools / "build_traceability.py", []),
        (tools / "health.py", ["--json"]),
        (tools / "build_graph.py", []),
        (tools / "anchor_check.py", []),
    ]
    if args.graphify:
        steps.insert(2, (tools / "graphify_code.py", ["--all"]))

    exit_code = 0
    for script, extra in steps:
        if not script.is_file():
            print(f"missing script: {script}", file=sys.stderr)
            return 2
        if script.name in {"scan_code.py", "graphify_code.py"}:
            code_err = raw_code_evidence_preflight_failed(project)
            if code_err:
                print(code_err, file=sys.stderr)
                return 2
        code = run(script, project, extra)
        if code != 0:
            exit_code = code
            if script.name != "health.py":
                break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
