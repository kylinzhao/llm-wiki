#!/usr/bin/env python3
"""Run structured LLM Wiki diagnostics.

The doctor is stricter than health about producing actionable findings, but
only blocking P0 findings should stop an automated publish.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_rules import inspect_agent_rules


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def run_health(project: Path) -> dict[str, Any]:
    health_path = project / "tools" / "health.py"
    if not health_path.is_file():
        return {"ok": False, "status": "fail", "missing_required_paths": ["tools/health.py"]}

    result = subprocess.run(
        [sys.executable, str(health_path), "--project", str(project), "--json"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout.strip():
        parsed = read_json_from_text(result.stdout)
        if isinstance(parsed, dict):
            return parsed
    return read_json(project / "staging" / "health" / "latest.json", {})


def read_json_from_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def severity_rank(severity: str | None) -> int:
    return {"P0": 3, "P1": 2, "P2": 1}.get(str(severity or ""), 0)


def max_severity(findings: list[dict[str, Any]]) -> str | None:
    current: str | None = None
    for finding in findings:
        severity = str(finding.get("severity") or "")
        if severity_rank(severity) > severity_rank(current):
            current = severity
    return current


def finding(severity: str, title: str, detail: str, *, blocking: bool = False) -> dict[str, Any]:
    return {
        "severity": severity,
        "blocking": blocking,
        "title": title,
        "detail": detail,
    }


def build_report(project: Path) -> dict[str, Any]:
    health = run_health(project)
    agent_rules = inspect_agent_rules(project)
    findings: list[dict[str, Any]] = []

    if health.get("ok") is not True:
        findings.append(
            finding(
                "P0",
                "health_failed",
                "tools/health.py did not report ok=true; fix health blockers before publishing.",
                blocking=True,
            )
        )

    missing_required_paths = health.get("missing_required_paths", [])
    if missing_required_paths:
        findings.append(
            finding(
                "P0",
                "missing_required_paths",
                ", ".join(str(item) for item in missing_required_paths),
                blocking=True,
            )
        )

    broken_wikilinks = health.get("broken_wikilinks", [])
    if broken_wikilinks:
        sample = json.dumps(broken_wikilinks[:20], ensure_ascii=False)
        findings.append(
            finding(
                "P0",
                "broken_wikilinks",
                f"{len(broken_wikilinks)} broken wikilinks found. Sample: {sample}",
                blocking=True,
            )
        )

    stale_sources = health.get("stale_sources", [])
    if stale_sources:
        sample = json.dumps(stale_sources[:20], ensure_ascii=False)
        findings.append(
            finding(
                "P0",
                "stale_sources",
                f"{len(stale_sources)} stale source pages found. Sample: {sample}",
                blocking=True,
            )
        )

    evidence_gaps = health.get("evidence_gaps", [])
    if evidence_gaps:
        findings.append(
            finding(
                "P0",
                "evidence_gaps",
                "; ".join(str(item) for item in evidence_gaps),
                blocking=True,
            )
        )

    image_evidence_gaps = health.get("image_evidence_gaps", [])
    if image_evidence_gaps:
        findings.append(
            finding(
                "P1",
                "image_evidence_gaps",
                "; ".join(str(item) for item in image_evidence_gaps),
                blocking=False,
            )
        )

    if not agent_rules.get("ok"):
        findings.append(
            finding(
                "P1",
                "agent_query_routing_missing",
                "AGENTS.md is missing the LLM Wiki Query Routing rules. Run llm-wiki update to repair it automatically.",
                blocking=False,
            )
        )

    p0_count = sum(1 for item in findings if item.get("severity") == "P0" or item.get("blocking") is True)
    summary = (
        "No blocking LLM Wiki issues found."
        if p0_count == 0
        else f"{p0_count} blocking LLM Wiki issue(s) found."
    )
    return {
        "schemaVersion": "doctor.v1",
        "generated_at": utc_now(),
        "project": str(project),
        "summary": summary,
        "findings": findings,
        "maxSeverity": max_severity(findings),
        "p0Count": p0_count,
        "health": {
            "ok": health.get("ok"),
            "status": health.get("status"),
            "wiki_pages": health.get("wiki_pages"),
            "source_pages": health.get("source_pages"),
        },
        "agent_rules": agent_rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report only.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    report = build_report(project)
    out = project / "staging" / "doctor" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
      print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
      print(f"doctor={'pass' if report['p0Count'] == 0 else 'fail'}")
      print(f"p0={report['p0Count']} maxSeverity={report['maxSeverity']}")
      print(f"report={out}")

    return 0 if report["p0Count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
