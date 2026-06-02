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
from gplus_quality import inspect_gplus_quality
from health import local_jira_auth_configured
from refinement_contract import summarize_refinement_contract


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_for_stability(value: object) -> object:
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if key == "generated_at":
                continue
            if key == "project":
                normalized[key] = "."
                continue
            if key == "path" and isinstance(item, str) and item.endswith("AGENTS.md"):
                normalized[key] = "AGENTS.md"
                continue
            normalized[key] = normalize_for_stability(item)
        return normalized
    if isinstance(value, list):
        return [normalize_for_stability(item) for item in value]
    return value


def stable_output_report(report: dict[str, Any]) -> dict[str, Any]:
    stable = dict(report)
    stable["project"] = "."
    agent_rules = stable.get("agent_rules")
    if isinstance(agent_rules, dict):
        stable["agent_rules"] = {
            **agent_rules,
            "path": "AGENTS.md" if agent_rules.get("path") else "",
        }
    return stable


def write_stable_report(path: Path, report: dict[str, Any]) -> None:
    next_report = stable_output_report(report)
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = None
        if normalize_for_stability(current) == normalize_for_stability(next_report):
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(next_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def finding(
    severity: str,
    title: str,
    detail: str,
    *,
    blocking: bool = False,
    promote_when_no_p1: bool = False,
) -> dict[str, Any]:
    payload = {
        "severity": severity,
        "blocking": blocking,
        "title": title,
        "detail": detail,
    }
    if promote_when_no_p1:
        payload["promote_when_no_p1"] = True
    return payload


def promote_important_p2_when_no_p1(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if any(item.get("blocking") is True or item.get("severity") in {"P0", "P1"} for item in findings):
        return findings
    promoted: list[dict[str, Any]] = []
    for item in findings:
        if item.get("severity") == "P2" and item.get("promote_when_no_p1") is True:
            next_item = dict(item)
            next_item["severity"] = "P1"
            next_item["promoted_from"] = "P2"
            next_item["detail"] = f"{next_item.get('detail', '')} Promoted from P2 because no P1 issue is currently active."
            promoted.append(next_item)
        else:
            promoted.append(item)
    return promoted


def build_report(project: Path) -> dict[str, Any]:
    health = run_health(project)
    agent_rules = inspect_agent_rules(project)
    gplus_quality = inspect_gplus_quality(project, health if isinstance(health, dict) else {})
    refinement_contract = summarize_refinement_contract(project)
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
    raw_image_assets = int(health.get("raw_image_assets") or 0)
    image_notes = int(health.get("image_notes") or 0)
    image_evidence_status = str(health.get("image_evidence_status") or "unknown")
    if raw_image_assets and image_evidence_status == "unknown":
        findings.append(
            finding(
                "P2",
                "image_evidence_status_unknown",
                (
                    f"raw/ contains {raw_image_assets} image asset(s), {image_notes} image note(s) exist, "
                    "but image evidence status is still unknown. Run `llm-wiki image` after source refinement "
                    "to screen high-value visual evidence."
                ),
                promote_when_no_p1=True,
            )
        )

    drawio_repair = health.get("drawio_repair", {})
    if isinstance(drawio_repair, dict) and drawio_repair.get("missing_evidence_count"):
        findings.append(
            finding(
                "P1",
                "drawio_evidence_missing",
                (
                    f"{drawio_repair.get('missing_evidence_count')} draw.io diagram(s) do not have generated "
                    ".drawio.md Mermaid evidence. Run llm-wiki update to repair them before relying on visual flow evidence."
                ),
                blocking=False,
            )
        )
    last_drawio_report = drawio_repair.get("last_report", {}) if isinstance(drawio_repair, dict) else {}
    if isinstance(last_drawio_report, dict) and last_drawio_report.get("unparsed_count"):
        findings.append(
            finding(
                "P1",
                "drawio_unparsed",
                f"{last_drawio_report.get('unparsed_count')} draw.io diagram(s) could not be parsed deterministically.",
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

    for item in gplus_quality["findings"]:
        next_item = dict(item)
        if next_item.get("severity") == "P2":
            next_item["promote_when_no_p1"] = True
        findings.append(next_item)
    if refinement_contract["status"] == "needs_refinement":
        findings.append(
            finding(
                "P1",
                "source_refinement_pending",
                (
                    f"{refinement_contract['pending_count']} required source page(s) still need AI-native "
                    "source refinement/status records. `llm-wiki update` must process this queue automatically; "
                    "it is not a user-only follow-up."
                ),
                blocking=False,
            )
        )
    cjira_registry = health.get("cjira_registry")
    if isinstance(cjira_registry, dict):
        stale_status_pages = int(cjira_registry.get("stale_status_pages") or 0)
        low_confidence_pages = int(cjira_registry.get("low_confidence_pages") or 0)
        if stale_status_pages or low_confidence_pages:
            if local_jira_auth_configured():
                detail = (
                    f"Cjira registry has {stale_status_pages} stale status page(s) and "
                    f"{low_confidence_pages} low-confidence primary selection(s). Run `llm-wiki update` "
                    "to refresh stale statuses and review low-confidence mappings before relying on lifecycle answers."
                )
            else:
                detail = (
                    f"Cjira registry has {stale_status_pages} stale status page(s) and "
                    f"{low_confidence_pages} low-confidence primary selection(s). Refresh Jira auth/status "
                    "and review low-confidence mappings before relying on lifecycle answers."
                )
            findings.append(
                finding(
                    "P2",
                    "cjira_status_quality_gaps",
                    detail,
                    promote_when_no_p1=True,
                )
            )
    orphan_source_pages = health.get("orphan_source_pages")
    if isinstance(orphan_source_pages, list) and orphan_source_pages:
        sample = json.dumps(orphan_source_pages[:5], ensure_ascii=False)
        findings.append(
            finding(
                "P2",
                "orphan_source_pages",
                f"{len(orphan_source_pages)} source page(s) are not mapped back to a raw source. Sample: {sample}",
                promote_when_no_p1=True,
            )
        )
    findings = promote_important_p2_when_no_p1(findings)

    p0_count = sum(1 for item in findings if item.get("severity") == "P0" or item.get("blocking") is True)
    summary = (
        "No blocking LLM Wiki issues found."
        if p0_count == 0
        else f"{p0_count} blocking LLM Wiki issue(s) found."
    )
    return {
        "schemaVersion": "doctor.v1",
        "generated_at": utc_now(),
        "project": ".",
        "summary": summary,
        "findings": findings,
        "maxSeverity": max_severity(findings),
        "p0Count": p0_count,
        "health": {
            "ok": health.get("ok"),
            "status": health.get("status"),
            "wiki_pages": health.get("wiki_pages"),
            "source_pages": health.get("source_pages"),
            "raw_drawio_assets": health.get("raw_drawio_assets"),
            "drawio_repair": health.get("drawio_repair"),
        },
        "gplus_quality": gplus_quality,
        "refinement_contract": refinement_contract,
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
    write_stable_report(out, report)

    if args.json:
      print(json.dumps(stable_output_report(report), ensure_ascii=False, indent=2))
    else:
      print(f"doctor={'pass' if report['p0Count'] == 0 else 'fail'}")
      print(f"p0={report['p0Count']} maxSeverity={report['maxSeverity']}")
      print(f"report={out}")

    return 0 if report["p0Count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
