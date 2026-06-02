#!/usr/bin/env python3
"""Seed requirement-to-code traceability files from source and code manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from wiki_preflight import raw_code_evidence_preflight_failed, raw_evidence_preflight_failed


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def stable_id(parts: list[object]) -> str:
    payload = "\n".join(str(part).strip() for part in parts if part is not None)
    return "tr_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def build_code_seed_row(codebase: dict[str, object]) -> str:
    codebase_id = str(codebase.get("codebase_id", "unknown"))
    stack = ", ".join(str(item) for item in codebase.get("stack", []) or [])
    upstream_type = str(codebase.get("upstream_type") or "none")
    notes = "Deterministic code scan only."
    if upstream_type != "none":
        notes = "Derived upstream topic matched; direct code anchor still required."
    return f"| [[code/codebases/{codebase_id}/index|{codebase_id}]] | {stack} | pending | partial | {notes} |"


def looks_like_placeholder_traceability(existing: str) -> bool:
    stripped = existing.strip()
    if not stripped:
        return True
    placeholders = [
        "在这里沉淀需求到代码的可审计追踪矩阵。",
        "Replace this row with verified requirement-to-code links.",
        "No code anchor candidates found.",
    ]
    return any(item in stripped for item in placeholders) and "strong" not in stripped


def extract_verified_traceability(existing: str) -> str:
    heading = "## Verified Traceability"
    start = existing.find(heading)
    if start == -1:
        if existing.strip() and not looks_like_placeholder_traceability(existing):
            return f"""## Previous Traceability Content

The previous traceability page did not use the current section format. It is preserved here for manual migration.

{existing.strip()}"""
        return ""
    next_heading = existing.find("\n## ", start + len(heading))
    if next_heading == -1:
        return existing[start:].strip()
    return existing[start:next_heading].strip()


def codebase_id_from_summary(codebase: dict[str, object]) -> str:
    return str(codebase.get("codebase_id") or codebase.get("id") or "unknown")


def collect_code_anchor_candidates(project: Path, codebases: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for codebase in codebases:
        codebase_id = codebase_id_from_summary(codebase)
        manifest = read_json(project / "staging" / "code-graph" / codebase_id / "manifest.json", {})
        facts = manifest.get("facts", []) if isinstance(manifest, dict) else []
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            path = str(fact.get("path") or "")
            role = str(fact.get("role") or "module")
            if not path:
                continue
            signals: list[str] = []
            endpoints = fact.get("endpoints", [])
            if isinstance(endpoints, list):
                for endpoint in endpoints:
                    if isinstance(endpoint, dict) and endpoint.get("uri"):
                        method = str(endpoint.get("method") or "unknown")
                        signals.append(f"{method} {endpoint.get('uri')}")
            routes = fact.get("routes", [])
            if isinstance(routes, list):
                signals.extend(str(route) for route in routes if route)
            symbols = fact.get("symbols", [])
            if isinstance(symbols, list):
                for symbol in symbols[:10]:
                    if isinstance(symbol, dict) and symbol.get("name"):
                        signals.append(f"{symbol.get('kind', 'symbol')} {symbol.get('name')}")
            signal_strength = "candidate"
            if not signals:
                signals = ["file"]
                signal_strength = "file-only"
            for signal in signals:
                candidates.append(
                    {
                        "codebase_id": codebase_id,
                        "path": path,
                        "role": role,
                        "signal": signal,
                        "candidate_capability": "pending",
                        "evidence_strength": signal_strength,
                        "notes": "Deterministic code anchor candidate; requirement link is not claimed without direct requirement evidence.",
                    }
                )
    return candidates


def build_code_anchor_rows(candidates: list[dict[str, object]], limit: int = 200) -> str:
    if not candidates:
        return "| pending | pending | pending | pending | missing | No code anchor candidates found. |"
    rows = []
    for candidate in candidates[:limit]:
        rows.append(
            "| [[code/codebases/{codebase}/index|{codebase}]] | {role} | `{path}` | `{signal}` | {capability} | {strength} |".format(
                codebase=markdown_cell(candidate["codebase_id"]),
                role=markdown_cell(candidate["role"]),
                path=markdown_cell(candidate["path"]),
                signal=markdown_cell(candidate["signal"]),
                capability=markdown_cell(candidate["candidate_capability"]),
                strength=markdown_cell(candidate["evidence_strength"]),
            )
        )
    if len(candidates) > limit:
        rows.append(f"| ... | ... | ... | ... | ... | {len(candidates) - limit} more candidates in `staging/traceability-candidates.json`. |")
    return "\n".join(rows)


def normalize_link(raw: dict[str, object]) -> dict[str, object]:
    code = raw.get("code", [])
    if isinstance(code, str):
        code = [code]
    if not isinstance(code, list):
        code = []
    link = {
        "id": str(raw.get("id") or stable_id([raw.get("source"), raw.get("requirement"), "|".join(str(item) for item in code)])),
        "requirement": str(raw.get("requirement") or ""),
        "source": str(raw.get("source") or ""),
        "code": [str(item) for item in code],
        "strength": str(raw.get("strength") or "inferred"),
        "status": str(raw.get("status") or "proposed"),
        "note": str(raw.get("note") or ""),
    }
    for key in ("updated_by", "decision_note", "previously_rejected"):
        if key in raw:
            link[key] = raw[key]
    return link


def load_traceability_state(project: Path) -> dict[str, object]:
    state = read_json(project / "staging" / "traceability" / "state.json", {})
    if not isinstance(state, dict):
        state = {}
    links = state.get("links", [])
    if not isinstance(links, list):
        links = []
    return {
        "schema_version": int(state.get("schema_version") or 1),
        "updated_at": str(state.get("updated_at") or utc_now()),
        "links": [normalize_link(link) for link in links if isinstance(link, dict)],
    }


def load_worker_proposals(project: Path) -> list[dict[str, object]]:
    proposals: list[dict[str, object]] = []
    runs_root = project / "staging" / "traceability" / "runs"
    if not runs_root.is_dir():
        return proposals
    for path in sorted(runs_root.glob("*/proposals.json")):
        payload = read_json(path, {})
        links = payload.get("links", []) if isinstance(payload, dict) else payload
        if not isinstance(links, list):
            continue
        proposals.extend(normalize_link(item) for item in links if isinstance(item, dict))
    return proposals


def load_candidate_proposals(project: Path, sources: list[object]) -> list[dict[str, object]]:
    proposals: list[dict[str, object]] = []
    source = next((item for item in sources if isinstance(item, dict) and item.get("slug")), {})
    source_ref = f"wiki/sources/{source.get('slug')}.md" if isinstance(source, dict) and source.get("slug") else ""
    root = project / "staging" / "code-graph"
    if not root.is_dir():
        return proposals
    for path in sorted(root.glob("*/anchor-candidates.json")):
        payload = read_json(path, {})
        candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            code_anchor = str(candidate.get("code_anchor") or "")
            if not code_anchor:
                continue
            strength = str(candidate.get("evidence_strength") or "candidate")
            if strength in {"candidate", "file-only"}:
                strength = "partial"
            if strength == "strong":
                strength = "partial"
            proposals.append(
                normalize_link(
                    {
                        "id": stable_id([source_ref, code_anchor, "candidate"]),
                        "requirement": source.get("title", "candidate requirement") if isinstance(source, dict) else "candidate requirement",
                        "source": source_ref,
                        "code": [code_anchor],
                        "strength": strength,
                        "status": "proposed",
                        "note": "Generated from deterministic code candidate; direct requirement-to-code verification is still required.",
                    }
                )
            )
    return proposals


def code_anchor_path(anchor: object) -> str:
    value = str(anchor)
    return value.split("#", 1)[0].split(":", 1)[0]


def link_has_missing_code_anchor(project: Path, link: dict[str, object]) -> bool:
    code = link.get("code", [])
    if isinstance(code, str):
        code = [code]
    if not isinstance(code, list):
        return False
    for anchor in code:
        path = code_anchor_path(anchor)
        if path.startswith("raw-code/") and not (project / path).exists():
            return True
    return False


def validate_traceability_links(project: Path, links: list[dict[str, object]]) -> list[dict[str, object]]:
    validated: list[dict[str, object]] = []
    for link in links:
        item = dict(link)
        if link_has_missing_code_anchor(project, item):
            item["status"] = "stale"
            if str(item.get("strength")) == "strong":
                item["strength"] = "partial"
            note = str(item.get("note") or "")
            suffix = "missing code anchor; verify or remove this traceability link."
            item["note"] = f"{note} {suffix}".strip()
        validated.append(item)
    return validated


def merge_traceability_state(project: Path, generated_proposals: list[dict[str, object]] | None = None) -> dict[str, object]:
    state = load_traceability_state(project)
    proposals = [*(generated_proposals or []), *load_worker_proposals(project)]
    existing_by_id = {str(link["id"]): link for link in state["links"] if isinstance(link, dict) and link.get("id")}
    merged_by_id = dict(existing_by_id)
    protected_statuses = {"confirmed", "rejected"}
    for proposal in proposals:
        link_id = str(proposal["id"])
        existing = existing_by_id.get(link_id)
        if existing and str(existing.get("status")) in protected_statuses:
            merged = dict(proposal)
            merged["status"] = existing.get("status")
            for key in ("decision_note", "updated_by", "verified_by", "verified_at", "rejected_by", "rejected_at", "rejection_reason"):
                if key in existing:
                    merged[key] = existing[key]
            merged_by_id[link_id] = merged
        else:
            merged_by_id[link_id] = proposal
    state["updated_at"] = utc_now()
    state["links"] = validate_traceability_links(
        project,
        sorted(merged_by_id.values(), key=lambda item: str(item.get("id", ""))),
    )
    write(
        project / "staging" / "traceability" / "state.json",
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )
    return state


STRENGTH_LABELS = {
    "strong": "强证据",
    "partial": "部分证据",
    "inferred": "可能相关线索",
    "external": "外部系统边界",
    "missing": "缺失证据",
}


def render_links_table(links: list[dict[str, object]], empty: str) -> str:
    if not links:
        return f"| pending | pending | pending | {empty} |"
    rows = []
    for link in links:
        code = link.get("code", [])
        if isinstance(code, list):
            code_text = "; ".join(f"`{markdown_cell(item)}`" for item in code) or "pending"
        else:
            code_text = f"`{markdown_cell(code)}`"
        rows.append(
            "| {requirement} | {strength} | {code} | {note} |".format(
                requirement=markdown_cell(link.get("requirement", "")),
                strength=markdown_cell(STRENGTH_LABELS.get(str(link.get("strength")), str(link.get("strength", "")))),
                code=code_text,
                note=markdown_cell(link.get("note", "")),
            )
        )
    return "\n".join(rows)


def render_state_sections(state: dict[str, object]) -> str:
    links = [link for link in state.get("links", []) if isinstance(link, dict)]
    verified = [link for link in links if str(link.get("status")) == "confirmed"]
    proposed = [
        link
        for link in links
        if str(link.get("status")) == "proposed" and str(link.get("strength")) not in {"missing", "external"}
    ]
    rejected = [link for link in links if str(link.get("status")) == "rejected"]
    gaps = [link for link in links if str(link.get("strength")) in {"missing", "external"} and str(link.get("status")) != "rejected"]
    return f"""## Verified Traceability

| Requirement | Strength | Code | Notes |
| --- | --- | --- | --- |
{render_links_table(verified, "No confirmed traceability links.")}

## Proposed Traceability

| Requirement | Strength | Code | Notes |
| --- | --- | --- | --- |
{render_links_table(proposed, "No proposed traceability links.")}

## Traceability Gaps

| Requirement | Strength | Code | Notes |
| --- | --- | --- | --- |
{render_links_table(gaps, "No traceability gaps.")}

## Rejected Traceability

| Requirement | Strength | Code | Notes |
| --- | --- | --- | --- |
{render_links_table(rejected, "No rejected traceability links.")}
"""


def build_traceability(project: Path) -> dict[str, int]:
    source_manifest = read_json(project / "staging" / "source-manifest.json", {"sources": []})
    code_summary = read_json(project / "staging" / "code-graph" / "summary.json", {"codebases": []})
    sources = source_manifest.get("sources", []) if isinstance(source_manifest, dict) else []
    codebases = code_summary.get("codebases", []) if isinstance(code_summary, dict) else []
    sources = sources if isinstance(sources, list) else []
    codebases = codebases if isinstance(codebases, list) else []
    codebase_dicts = [item for item in codebases if isinstance(item, dict)]

    source_rows = "\n".join(
        f"| [[sources/{source['slug']}|{source['title']}]] | pending | pending | missing | Requirement point extraction and code mapping not yet verified. |"
        for source in sources
        if isinstance(source, dict) and "slug" in source and "title" in source
    ) or "| pending | pending | pending | missing | No source manifest found. |"
    code_rows = "\n".join(build_code_seed_row(codebase) for codebase in codebase_dicts) or "| pending | pending | pending | missing | No codebase scan found. |"
    candidates = collect_code_anchor_candidates(project, codebase_dicts)
    traceability_path = project / "wiki" / "code" / "traceability" / "index.md"
    existing = traceability_path.read_text(encoding="utf-8") if traceability_path.is_file() else ""
    verified_traceability = extract_verified_traceability(existing)
    state = merge_traceability_state(project, generated_proposals=load_candidate_proposals(project, sources))
    state_sections = render_state_sections(state)

    content = f"""# Traceability Matrix

Generated: {utc_now()}

## Requirement Seeds

| Requirement Source | Requirement Point | Linked Capability | Evidence Strength | Notes |
| --- | --- | --- | --- | --- |
{source_rows}

## Code Evidence Seeds

| Codebase | Stack | Candidate Capability | Evidence Strength | Notes |
| --- | --- | --- | --- | --- |
{code_rows}

## Code Anchor Candidates

| Codebase | Role | Code Anchor | Signal | Candidate Capability | Evidence Strength |
| --- | --- | --- | --- | --- | --- |
{build_code_anchor_rows(candidates)}

{state_sections}

{verified_traceability}

## Evidence Strength Vocabulary

- `strong`: direct source and direct code anchor both exist.
- `partial`: source links to module/service family, but method, field, message, or runtime condition is incomplete.
- `candidate`: deterministic code scanner found an endpoint, route, symbol, or file anchor; no requirement link is claimed yet.
- `file-only`: deterministic code scanner found a code file but no endpoint, route, or symbol signal.
- `inferred`: naming, adjacency, or graphify relation suggests a requirement-code link, but direct evidence is missing.
- `external`: implementation boundary is outside available code.
- `missing`: no usable code or requirement evidence yet.

Verified traceability rows must only claim requirement-to-code evidence after checking requirement sources, capability pages, and direct code anchors. Deterministic candidates are useful inputs, not implementation proof by themselves.
"""
    write(traceability_path, content)
    write(
        project / "staging" / "traceability-candidates.json",
        json.dumps({"generated_at": utc_now(), "candidates": candidates}, ensure_ascii=False, indent=2) + "\n",
    )
    write(
        project / "staging" / "traceability-seed.json",
        json.dumps(
            {
                "generated_at": utc_now(),
                "source_count": len(sources),
                "codebase_count": len(codebase_dicts),
                "code_anchor_candidate_count": len(candidates),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return {"sources": len(sources), "codebases": len(codebase_dicts), "code_anchor_candidates": len(candidates)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    err = raw_evidence_preflight_failed(project)
    if err:
        print(err, file=sys.stderr)
        return 2
    code_err = raw_code_evidence_preflight_failed(project)
    if code_err:
        print(code_err, file=sys.stderr)
        return 2

    result = build_traceability(project)
    print(f"sources={result['sources']}")
    print(f"codebases={result['codebases']}")
    print(f"code_anchor_candidates={result['code_anchor_candidates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
