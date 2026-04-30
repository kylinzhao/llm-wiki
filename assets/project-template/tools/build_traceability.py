#!/usr/bin/env python3
"""Seed requirement-to-code traceability files from source and code manifests."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    source_manifest = read_json(project / "staging" / "source-manifest.json", {"sources": []})
    code_summary = read_json(project / "staging" / "code-graph" / "summary.json", {"codebases": []})
    sources = source_manifest.get("sources", []) if isinstance(source_manifest, dict) else []
    codebases = code_summary.get("codebases", []) if isinstance(code_summary, dict) else []

    source_rows = "\n".join(
        f"| [[sources/{source['slug']}|{source['title']}]] | pending | pending | missing | Codex must map requirement facts. |"
        for source in sources
    ) or "| pending | pending | pending | missing | No source manifest found. |"
    code_rows = "\n".join(
        f"| [[code/codebases/{codebase['codebase_id']}/index|{codebase['codebase_id']}]] | {', '.join(codebase.get('stack', []))} | pending | partial | Deterministic code scan only. |"
        for codebase in codebases
    ) or "| pending | pending | pending | missing | No codebase scan found. |"

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

## Evidence Strength Vocabulary

- `strong`: direct source and direct code anchor both exist.
- `partial`: source links to module/service family, but method, field, message, or runtime condition is incomplete.
- `inferred`: naming, adjacency, or graphify relation suggests a link, but direct evidence is missing.
- `external`: implementation boundary is outside available code.
- `missing`: no usable code or requirement evidence yet.

Codex must replace seed rows with verified requirement points, pages, APIs, services, tables, messages, jobs, and anchors.
"""
    write(project / "wiki" / "code" / "traceability" / "index.md", content)
    write(project / "staging" / "traceability-seed.json", json.dumps({"generated_at": utc_now(), "source_count": len(sources), "codebase_count": len(codebases)}, ensure_ascii=False, indent=2) + "\n")
    print(f"sources={len(sources)}")
    print(f"codebases={len(codebases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

