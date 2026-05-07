#!/usr/bin/env python3
"""Run graphify for raw-code codebases and archive status."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_graphify(project: Path, codebase: str, command_name: str | None) -> dict[str, object]:
    source = project / "raw-code" / codebase
    out_dir = project / "staging" / "code-graph" / codebase / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = command_name or shutil.which("graphify") or shutil.which("graphifyy")
    status_path = project / "staging" / "code-graph" / codebase / "graphify-status.json"
    if not cmd:
        status = {
            "codebase_id": codebase,
            "status": "skipped",
            "reason": "graphify command not found on PATH",
            "updated_at": utc_now(),
            "output_path": str(out_dir),
        }
        write_json(status_path, status)
        return status

    # graphify writes graphify-out next to the scanned tree. raw-code/ is an
    # immutable evidence layer, so run graphify against a temporary copy.
    with tempfile.TemporaryDirectory(prefix=f"llm-wiki-graphify-{codebase}-") as tmp:
        work_root = Path(tmp) / codebase
        shutil.copytree(
            source,
            work_root,
            ignore=shutil.ignore_patterns(".git", "node_modules", "dist", "build", "target", "graphify-out"),
        )
        process = subprocess.run(
            [cmd, "update", str(work_root)],
            cwd=work_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        local_out = work_root / "graphify-out"
        if local_out.is_dir():
            for path in local_out.rglob("*"):
                rel = path.relative_to(local_out)
                target = out_dir / rel
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)

    status = {
        "codebase_id": codebase,
        "status": "completed" if process.returncode == 0 else "failed",
        "command": [cmd, "update", "TEMP_COPY_OF_" + str(source)],
        "returncode": process.returncode,
        "updated_at": utc_now(),
        "output_path": str(out_dir),
        "stdout_tail": process.stdout[-4000:],
        "stderr_tail": process.stderr[-4000:],
        "graph_json_exists": (out_dir / "graph.json").is_file(),
    }
    write_json(status_path, status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--codebase", help="Only run graphify for one raw-code/<codebase_id>.")
    parser.add_argument("--all", action="store_true", help="Run graphify for all raw-code codebases.")
    parser.add_argument("--command", help="Explicit graphify command path.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    raw_code = project / "raw-code"
    if not raw_code.is_dir():
        print("raw-code/ not found; graphify skipped")
        return 0
    if args.codebase:
        codebases = [args.codebase]
    elif args.all:
        codebases = sorted(path.name for path in raw_code.iterdir() if path.is_dir())
    else:
        raise SystemExit("Pass --all or --codebase <codebase_id>.")

    statuses = [run_graphify(project, codebase, args.command) for codebase in codebases]
    write_json(project / "staging" / "code-graph" / "graphify-summary.json", {"generated_at": utc_now(), "statuses": statuses})
    print(json.dumps({"statuses": statuses}, ensure_ascii=False, indent=2))
    return 0 if all(status["status"] in {"completed", "skipped"} for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
