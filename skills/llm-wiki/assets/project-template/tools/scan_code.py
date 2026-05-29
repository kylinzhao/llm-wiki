#!/usr/bin/env python3
"""Deterministically scan raw-code/* and seed code wiki pages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from code_candidates import build_code_candidates
from code_freshness import compute_freshness
from code_intelligence import collect_upstream_summary, resolve_code_intelligence
from wiki_preflight import raw_code_evidence_preflight_failed, wiki_expects_raw_code

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".venv",
    "venv",
    "__pycache__",
}

CODE_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".vue",
    ".java",
    ".kt",
    ".py",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".rs",
    ".swift",
    ".m",
    ".mm",
    ".sql",
    ".graphql",
    ".proto",
    ".yaml",
    ".yml",
    ".json",
    ".xml",
}

HTTP_ANNOTATION_RE = re.compile(
    r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(?:\(\s*)?(?:value\s*=\s*)?[\"']([^\"']+)[\"']",
    re.MULTILINE,
)
URI_RE = re.compile(r"[\"']((?:/api|/openapi|/v\d+|/ajax|/admin|/app|/graphql|/rpc)[A-Za-z0-9_./:{}?$=&%-]*)[\"']")
ROUTE_RE = re.compile(r"(?:path|route|url)\s*[:=]\s*[\"'](/[^\"']*)[\"']")
CLASS_RE = re.compile(r"\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")
FUNCTION_RE = re.compile(r"\b(function|def|func)\s+([A-Za-z_][A-Za-z0-9_]*)")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path, limit: int = 300_000) -> str:
    return path.read_bytes()[:limit].decode("utf-8", errors="replace")


def iter_code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS:
            files.append(path)
    return files


def detect_stack(root: Path) -> list[str]:
    markers = {
        "package.json": "node",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "vite.config.ts": "vite",
        "vite.config.js": "vite",
        "next.config.js": "nextjs",
        "next.config.mjs": "nextjs",
        "pom.xml": "maven-java",
        "build.gradle": "gradle",
        "build.gradle.kts": "gradle-kotlin",
        "go.mod": "go",
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "Cargo.toml": "rust",
        "Gemfile": "ruby",
    }
    found: set[str] = set()
    for marker, stack in markers.items():
        if (root / marker).exists():
            found.add(stack)
    return sorted(found) or ["unknown"]


def classify_file(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix().lower()
    name = path.name.lower()
    if "controller" in rel or "handler" in rel:
        return "controller"
    if "route" in rel or "router" in rel or "/pages/" in rel or "/app/" in rel:
        return "route"
    if "service" in rel:
        return "service"
    if "component" in rel or name.endswith(".vue") or name.endswith(".tsx") or name.endswith(".jsx"):
        return "component"
    if "dao" in rel or "repository" in rel or "mapper" in rel:
        return "data-access"
    if "job" in rel or "task" in rel or "cron" in rel:
        return "job"
    if "kafka" in rel or "mq" in rel or "message" in rel:
        return "async"
    if name.endswith((".proto", ".graphql")):
        return "api-contract"
    return "module"


def extract_facts(path: Path, root: Path) -> dict[str, object]:
    text = read_text(path)
    rel = path.relative_to(root).as_posix()
    endpoints = []
    for method, uri in HTTP_ANNOTATION_RE.findall(text):
        endpoints.append({"kind": "annotation", "method": method, "uri": uri})
    for uri in URI_RE.findall(text):
        endpoints.append({"kind": "uri", "method": "unknown", "uri": uri})
    routes = sorted(set(ROUTE_RE.findall(text)))
    symbols = []
    for kind, name in CLASS_RE.findall(text)[:30]:
        symbols.append({"kind": kind, "name": name})
    for kind, name in FUNCTION_RE.findall(text)[:30]:
        symbols.append({"kind": kind, "name": name})
    return {
        "path": f"raw-code/{root.name}/{rel}",
        "role": classify_file(path, root),
        "extension": path.suffix.lower(),
        "endpoints": endpoints[:80],
        "routes": routes[:80],
        "symbols": symbols,
    }


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def codebase_page(
    codebase: str,
    stack: list[str],
    facts: list[dict[str, object]],
    upstream_summary: dict[str, object],
) -> str:
    roles: dict[str, int] = {}
    endpoints = []
    routes = []
    for fact in facts:
        roles[str(fact["role"])] = roles.get(str(fact["role"]), 0) + 1
        endpoints.extend(fact["endpoints"])  # type: ignore[arg-type]
        routes.extend(fact["routes"])  # type: ignore[arg-type]
    role_lines = "\n".join(f"- {role}: {count}" for role, count in sorted(roles.items())) or "- No code files scanned."
    endpoint_lines = "\n".join(
        f"- `{item.get('method', 'unknown')}` `{item.get('uri')}`"
        for item in endpoints[:80]
    ) or "- No endpoint-like strings discovered."
    route_lines = "\n".join(f"- `{route}`" for route in sorted(set(routes))[:80]) or "- No route-like strings discovered."
    upstream_type = str(upstream_summary.get("upstream_type") or "none")
    upstream_section = ""
    if upstream_type != "none":
        upstream_section = f"""
## Upstream Code Intelligence

- Type: `{upstream_type}`
- Discovery mode: `{upstream_summary.get('discovery_mode', 'unknown')}`
- Root: `{upstream_summary.get('root', '')}`
- Preferred entry: `{upstream_summary.get('preferred_entry', upstream_summary.get('index_path', ''))}`
- Adapter status: `{upstream_summary.get('adapter_status', 'unknown')}`
- Topics: {upstream_summary.get('topic_count', 0)}
- Concepts: {upstream_summary.get('concept_count', 0)}
- Source map entries: {upstream_summary.get('source_map_entries', 0)}
- Adapter warnings: {upstream_summary.get('warning_count', 0)}

This upstream wiki is a derived hint. Direct code anchors are still required before claiming implementation certainty.
"""
    return f"""# Codebase: {codebase}

## Scan Status

- Stack markers: {", ".join(stack)}
- Files scanned: {len(facts)}
- Graphify status: see `staging/code-graph/{codebase}/graphify-status.json`

## Module Roles

{role_lines}

## Endpoint Candidates

{endpoint_lines}

## Route Candidates

{route_lines}
{upstream_section}

## Evidence Boundary

This page is deterministic code evidence. Do not link it to requirement facts unless direct requirement and code evidence are available.
"""


def scan_codebase(project: Path, root: Path) -> dict[str, object]:
    codebase = root.name
    files = iter_code_files(root)
    facts = [extract_facts(path, root) for path in files]
    stack = detect_stack(root)
    upstream = resolve_code_intelligence(project, codebase)
    upstream_summary = collect_upstream_summary(project, codebase, upstream)

    out_dir = project / "staging" / "code-graph" / codebase
    freshness = compute_freshness(project, codebase, root, files, facts)
    write(
        out_dir / "manifest.json",
        json.dumps(
            {
                "codebase_id": codebase,
                "generated_at": utc_now(),
                "root": f"raw-code/{codebase}",
                "stack": stack,
                "file_count": len(files),
                "facts": facts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    endpoint_rows = [
        {
            "path": fact["path"],
            "role": fact["role"],
            "endpoint": endpoint,
        }
        for fact in facts
        for endpoint in fact["endpoints"]  # type: ignore[union-attr]
    ]
    write(out_dir / "endpoint-map.json", json.dumps(endpoint_rows, ensure_ascii=False, indent=2) + "\n")
    write(out_dir / "upstream-summary.json", json.dumps(upstream_summary, ensure_ascii=False, indent=2) + "\n")
    write(out_dir / "freshness.json", json.dumps(freshness, ensure_ascii=False, indent=2) + "\n")
    write(
        project / "wiki" / "code" / "codebases" / codebase / "index.md",
        codebase_page(codebase, stack, facts, upstream_summary),
    )
    candidate_summary = build_code_candidates(project, codebase)
    return {
        "codebase_id": codebase,
        "stack": stack,
        "file_count": len(files),
        "endpoint_candidates": len(endpoint_rows),
        "upstream_type": upstream_summary.get("upstream_type", "none"),
        "structural_change_level": freshness.get("structural_change_level", "none"),
        "anchor_candidates": candidate_summary.get("anchor_candidate_count", 0),
        "capability_candidates": candidate_summary.get("capability_candidate_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--codebase", help="Only scan one raw-code/<codebase_id>.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    raw_code = project / "raw-code"
    if not raw_code.is_dir():
        err = raw_code_evidence_preflight_failed(project)
        if err:
            print(err, file=sys.stderr)
            return 2
        print("raw-code/ not found; code scan skipped")
        return 0

    roots = [raw_code / args.codebase] if args.codebase else sorted(path for path in raw_code.iterdir() if path.is_dir())
    if wiki_expects_raw_code(project) and not roots:
        print(
            "empty_raw_code_evidence: raw-code/ has no codebase directories while code wiki expects "
            "implementation evidence. Populate raw-code/<codebase_id>/, then rerun scan_code.",
            file=sys.stderr,
        )
        return 2
    results = []
    for root in roots:
        if not root.is_dir():
            raise SystemExit(f"Missing codebase directory: {root}")
        results.append(scan_codebase(project, root))

    write(project / "staging" / "code-graph" / "summary.json", json.dumps({"generated_at": utc_now(), "codebases": results}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"codebases": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
