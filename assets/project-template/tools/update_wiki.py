#!/usr/bin/env python3
"""Run the deterministic LLM Wiki update pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


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
    tools = project / "tools"
    steps = [
        (tools / "build_wiki.py", []),
        (tools / "scan_code.py", []),
        (tools / "build_traceability.py", []),
        (tools / "health.py", ["--json"]),
        (tools / "build_graph.py", []),
        (tools / "anchor_check.py", []),
    ]
    wiki_sources = project / "upstream" / "wiki-sources.json"
    feed_discovery = tools / "discover_wiki_feeds.py"
    if wiki_sources.is_file():
        steps.insert(0, (feed_discovery, ["--input", str(wiki_sources)]))
    if args.graphify and (project / "raw-code").is_dir():
        graphify_index = 3 if wiki_sources.is_file() else 2
        steps.insert(graphify_index, (tools / "graphify_code.py", ["--all"]))

    exit_code = 0
    for script, extra in steps:
        if not script.is_file():
            print(f"missing script: {script}", file=sys.stderr)
            return 2
        code = run(script, project, extra)
        if code != 0:
            exit_code = code
            if script.name != "health.py":
                break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
