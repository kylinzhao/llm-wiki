#!/usr/bin/env python3
"""Deterministic LLM Wiki seed builder.

This script creates the stable file structure that Codex refines afterwards.
It intentionally does not summarize, classify, or normalize semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from wiki_preflight import raw_evidence_preflight_failed

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".html",
    ".htm",
    ".csv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
}

REQUIRED_DIRS = [
    "wiki/sources",
    "wiki/concepts",
    "wiki/entities",
    "wiki/truth",
    "wiki/conflicts",
    "wiki/evidence",
    "wiki/proposals",
    "wiki/reference",
    "wiki/operations",
    "wiki/code/codebases",
    "wiki/code/capabilities",
    "wiki/code/traceability",
    "docs",
    "graph",
    "staging/health",
    "staging/graph",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._\-\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "source"


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_bytes()
    if limit is not None:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def title_for(path: Path) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        for line in read_text(path, limit=32_000).splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def discover_sources(raw_dir: Path) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []
    used_slugs: set[str] = set()
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel = path.relative_to(raw_dir)
        base = slugify(str(rel.with_suffix("")).replace("/", "-"))
        slug = base
        counter = 2
        while slug in used_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        used_slugs.add(slug)
        stat = path.stat()
        sources.append(
            {
                "title": title_for(path),
                "slug": slug,
                "raw_path": f"raw/{rel.as_posix()}",
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "sha256": sha256_file(path),
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            }
        )
    return sources


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_page(source: dict[str, object]) -> str:
    return f"""# {source['title']}

> Deterministic seed page. Codex must replace pending sections with source-grounded summary and AI-native refinement.

## Source

- Raw path: `{source['raw_path']}`
- SHA-256: `{source['sha256']}`
- Size: `{source['size_bytes']}` bytes
- Modified: `{source['mtime']}`

## Summary

Pending AI-native summary.

## Key Facts

- Pending extraction from source evidence.

## Business Links

- Concepts: pending
- Entities: pending
- Related layered pages: pending

## Evidence Notes

Use this page as a source evidence node. Do not copy sensitive values from raw materials.
"""


def index_page(sources: list[dict[str, object]], codebases: list[str]) -> str:
    source_lines = "\n".join(
        f"- [[sources/{source['slug']}|{source['title']}]]"
        for source in sources
    ) or "- No source pages discovered yet."
    code_lines = "\n".join(
        f"- [[code/codebases/{codebase}/index|{codebase}]]"
        for codebase in codebases
    ) or "- No raw-code codebases discovered."
    return f"""# LLM Wiki

Generated: {utc_now()}

## Entry Points

- [[overview|Overview]]
- [[concepts/index|Concepts]]
- [[entities/index|Entities]]
- [[truth/index|Truth]]
- [[conflicts/index|Conflicts]]
- [[evidence/index|Evidence]]
- [[proposals/index|Proposals]]
- [[reference/index|Reference]]
- [[operations/index|Operations]]
- [[code/index|Code Wiki]]

## Sources

{source_lines}

## Codebases

{code_lines}
"""


def simple_page(title: str, body: str) -> str:
    return f"# {title}\n\n{body.rstrip()}\n"


def create_layer_pages(project: Path) -> None:
    pages = {
        "wiki/overview.md": (
            "Overview",
            "Pending synthesis from `BUSINESS_CONTEXT.md`, `wiki/sources/`, and optional `wiki/code/` evidence.",
        ),
        "wiki/concepts/index.md": (
            "Concepts",
            "Canonical business concepts go here after AI-native refinement.",
        ),
        "wiki/entities/index.md": (
            "Entities",
            "Canonical entities, aliases, and conflicts go here.",
        ),
        "wiki/truth/index.md": (
            "Truth",
            "Stable cross-source truths go here.",
        ),
        "wiki/conflicts/index.md": (
            "Conflicts",
            "Conflicting requirements, terminology, and unresolved business calls go here.",
        ),
        "wiki/evidence/index.md": (
            "Evidence",
            "High-value evidence indexes go here.",
        ),
        "wiki/proposals/index.md": (
            "Proposals",
            "Product, process, or implementation proposals go here.",
        ),
        "wiki/reference/index.md": (
            "Reference",
            "Stable reference material, glossaries, and external boundaries go here.",
        ),
        "wiki/operations/index.md": (
            "Operations",
            "SOPs, operating procedures, runbooks, and support flows go here.",
        ),
        "wiki/code/index.md": (
            "Code Wiki",
            "Codebase facts, capability pages, and traceability matrices live under this directory.",
        ),
        "wiki/code/capabilities/index.md": (
            "Code Capabilities",
            "Cross-layer business capability implementation pages go here.",
        ),
        "wiki/code/traceability/index.md": (
            "Traceability",
            "Requirement-to-code traceability matrices go here.",
        ),
    }
    for rel, (title, body) in pages.items():
        write_if_missing(project / rel, simple_page(title, body))


def create_codebase_pages(project: Path, codebases: list[str]) -> None:
    for codebase in codebases:
        path = project / "wiki" / "code" / "codebases" / codebase / "index.md"
        write_if_missing(
            path,
            simple_page(
                f"Codebase: {codebase}",
                "Pending code scan. Record stack, entry points, module boundaries, APIs, services, jobs, data access, and evidence gaps.",
            ),
        )


def create_docs(project: Path) -> None:
    write_if_missing(
        project / "docs" / "retrieval-playbook.md",
        """# Retrieval Playbook

1. Read `BUSINESS_CONTEXT.md` first when present.
2. Identify the query type.
3. Check `wiki/overview.md`, then the relevant layered pages.
4. Expand through `wiki/concepts/` and `wiki/entities/`.
5. Use `wiki/sources/` for requirement evidence.
6. Use `wiki/code/` only for code implementation evidence.
7. Separate requirement proof, code proof, inference, and missing evidence.
""",
    )
    write_if_missing(
        project / "docs" / "build-and-maintenance.md",
        """# Build And Maintenance

Standard deterministic commands:

```bash
uv run python tools/build_wiki.py
uv run python tools/scan_code.py
uv run python tools/build_traceability.py
uv run python tools/health.py --json
uv run python tools/build_graph.py
uv run python tools/anchor_check.py
```

Use Codex-native work for summaries, entity normalization, source refinement, capability judgment, and traceability reasoning.
Local scripts only scan, seed, validate, and build graph files.
""",
    )
    write_if_missing(
        project / "docs" / "tooling-dependencies.md",
        """# Tooling Dependencies

Required:

- Python 3.10+
- `uv`

Optional:

- `graphify` for code graph extraction when `raw-code/` exists.

The bundled Python scripts use the standard library only and do not call local model SDKs.
""",
    )
    write_if_missing(
        project / "docs" / "implementation-workflow.md",
        """# Implementation Workflow

Run:

```bash
uv run python tools/update_wiki.py
```

If `raw-code/` exists and graphify is available:

```bash
uv run python tools/update_wiki.py --graphify
```

After deterministic seeding, use Codex to complete source summaries, layered pages, concepts, entities, capabilities, and traceability evidence strength.
""",
    )


def source_page_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"SHA-256:\s*`?([a-f0-9]{64})`?", text)
    return match.group(1) if match else None


def update_status(
    project: Path,
    sources: list[dict[str, object]],
    codebases: list[str],
    stale_sources: list[dict[str, object]],
    orphan_source_pages: list[str],
) -> None:
    status = {
        "task_id": "deterministic-build",
        "phase": "C",
        "status": "deterministic_seed_complete",
        "updated_at": utc_now(),
        "source_count": len(sources),
        "codebases": codebases,
        "stale_source_count": len(stale_sources),
        "orphan_source_page_count": len(orphan_source_pages),
        "checkpoint": "Run AI-native source refinement next, then health and graph.",
        "next_action": "Complete first-pass summaries and layered refinement with Codex.",
    }
    write(project / "staging" / "refinement-status.md", "# Refinement Status\n\n```json\n" + json.dumps(status, ensure_ascii=False, indent=2) + "\n```\n")
    write(project / "staging" / "source-manifest.json", json.dumps({"generated_at": utc_now(), "sources": sources}, ensure_ascii=False, indent=2) + "\n")
    write(
        project / "staging" / "source-drift.json",
        json.dumps(
            {
                "generated_at": utc_now(),
                "stale_sources": stale_sources,
                "orphan_source_pages": orphan_source_pages,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    err = raw_evidence_preflight_failed(project)
    if err:
        raise SystemExit(err)
    raw_dir = project / "raw"
    if not raw_dir.is_dir():
        raw_dir.mkdir(parents=True, exist_ok=True)

    for rel in REQUIRED_DIRS:
        (project / rel).mkdir(parents=True, exist_ok=True)

    sources = discover_sources(raw_dir)
    stale_sources: list[dict[str, object]] = []
    for source in sources:
        page = project / "wiki" / "sources" / f"{source['slug']}.md"
        existing_sha = source_page_sha(page)
        created = write_if_missing(page, source_page(source))
        if not created and existing_sha != source["sha256"]:
            stale_sources.append(
                {
                    "slug": source["slug"],
                    "title": source["title"],
                    "raw_path": source["raw_path"],
                    "previous_sha256": existing_sha,
                    "current_sha256": source["sha256"],
                    "page": f"wiki/sources/{source['slug']}.md",
                }
            )

    codebases = []
    raw_code = project / "raw-code"
    if raw_code.is_dir():
        codebases = sorted(path.name for path in raw_code.iterdir() if path.is_dir() and not path.name.startswith("."))

    create_layer_pages(project)
    create_codebase_pages(project, codebases)
    create_docs(project)
    write(project / "wiki" / "index.md", index_page(sources, codebases))
    current_pages = {f"{source['slug']}.md" for source in sources}
    source_dir = project / "wiki" / "sources"
    orphan_source_pages = sorted(
        f"wiki/sources/{path.name}"
        for path in source_dir.glob("*.md")
        if path.name not in current_pages
    )
    update_status(project, sources, codebases, stale_sources, orphan_source_pages)

    print(f"project={project}")
    print(f"sources={len(sources)}")
    print(f"stale_sources={len(stale_sources)}")
    print(f"orphan_source_pages={len(orphan_source_pages)}")
    print(f"codebases={len(codebases)}")
    print("status=deterministic_seed_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
