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

from wiki_preflight import raw_code_evidence_preflight_failed, wiki_expects_raw_code


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def decide_graphify_action(project: Path, codebase: str, requested: bool = False) -> dict[str, object]:
    code_graph = project / "staging" / "code-graph" / codebase
    if requested:
        return {
            "codebase_id": codebase,
            "decision": "run_requested",
            "should_run": True,
            "reason": "graphify was explicitly requested",
        }

    freshness = read_json(code_graph / "freshness.json", {})
    upstream = read_json(code_graph / "upstream-summary.json", {})
    endpoint_map = read_json(code_graph / "endpoint-map.json", [])
    status = read_json(code_graph / "graphify-status.json", {})
    structural_change_level = str(freshness.get("structural_change_level") if isinstance(freshness, dict) else "unknown")
    upstream_type = str(upstream.get("upstream_type") if isinstance(upstream, dict) else "none")
    source_map_entries = int(upstream.get("source_map_entries") or 0) if isinstance(upstream, dict) else 0
    endpoint_count = len(endpoint_map) if isinstance(endpoint_map, list) else 0

    if upstream_type != "none" and source_map_entries > 0 and endpoint_count > 0 and structural_change_level in {"none", "low"}:
        return {
            "codebase_id": codebase,
            "decision": "skipped_upstream_sufficient",
            "should_run": False,
            "reason": "upstream docs/wiki and scan anchors are sufficient for this update",
        }
    if structural_change_level == "high":
        return {
            "codebase_id": codebase,
            "decision": "recommended_structural_change",
            "should_run": False,
            "reason": "structural code changes were detected; graphify is recommended but not run without request",
        }
    if structural_change_level == "medium" and isinstance(status, dict) and status.get("status") == "completed":
        return {
            "codebase_id": codebase,
            "decision": "stale_not_rerun",
            "should_run": False,
            "reason": "existing graphify output may be stale; rerun requires explicit request",
        }
    return {
        "codebase_id": codebase,
        "decision": "skipped_no_graphify_requested",
        "should_run": False,
        "reason": "graphify was not requested",
    }


def summarize_graphify_output(project: Path, codebase: str) -> dict[str, object]:
    out_dir = project / "staging" / "code-graph" / codebase / "graphify-out"
    graph_json = out_dir / "graph.json"
    summary_path = project / "staging" / "code-graph" / codebase / "structure-summary.json"
    payload = read_json(graph_json, {})
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    edges = payload.get("edges", []) if isinstance(payload, dict) else []
    compact_nodes = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("path") or "").strip()
        if not node_id or "node_modules/" in node_id:
            continue
        compact_nodes.append({"id": node_id, "label": str(node.get("label") or node_id)})
    compact_edges = []
    for edge in edges if isinstance(edges, list) else []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or edge.get("from") or "").strip()
        target = str(edge.get("target") or edge.get("to") or "").strip()
        if not source or not target or "node_modules/" in source or "node_modules/" in target:
            continue
        compact_edges.append(
            {
                "source": source,
                "target": target,
                "type": str(edge.get("type") or edge.get("kind") or "related"),
                "signal": "graph_neighbor",
            }
        )
    summary = {
        "codebase_id": codebase,
        "node_count": len(compact_nodes),
        "edge_count": len(compact_edges),
        "nodes": compact_nodes[:200],
        "edges": compact_edges[:500],
        "warnings": [] if graph_json.is_file() else ["graphify-out/graph.json missing"],
    }
    write_json(summary_path, summary)
    return summary


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
    if (out_dir / "graph.json").is_file():
        summarize_graphify_output(project, codebase)
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
        err = raw_code_evidence_preflight_failed(project)
        if err:
            raise SystemExit(err)
        print("raw-code/ not found; graphify skipped")
        return 0
    if args.codebase:
        codebases = [args.codebase]
    elif args.all:
        codebases = sorted(path.name for path in raw_code.iterdir() if path.is_dir())
        if wiki_expects_raw_code(project) and not codebases:
            raise SystemExit(
                "empty_raw_code_evidence: raw-code/ has no codebase directories while code wiki expects "
                "implementation evidence. Populate raw-code/<codebase_id>/, then rerun graphify."
            )
    else:
        raise SystemExit("Pass --all or --codebase <codebase_id>.")

    statuses = [run_graphify(project, codebase, args.command) for codebase in codebases]
    write_json(project / "staging" / "code-graph" / "graphify-summary.json", {"generated_at": utc_now(), "statuses": statuses})
    print(json.dumps({"statuses": statuses}, ensure_ascii=False, indent=2))
    return 0 if all(status["status"] in {"completed", "skipped"} for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
