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
import shutil
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


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


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
    if match:
        return match.group(1)
    metadata = source_page_metadata(path)
    raw_hash = metadata.get("raw_hash") if isinstance(metadata, dict) else None
    if isinstance(raw_hash, str) and re.fullmatch(r"[a-f0-9]{8,64}", raw_hash):
        return raw_hash
    return None


def source_page_metadata(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"## Source Metadata\s*```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def source_page_raw_rel(path: Path) -> str | None:
    metadata = source_page_metadata(path)
    raw_rel = metadata.get("raw_rel") if isinstance(metadata, dict) else None
    if isinstance(raw_rel, str) and raw_rel.strip():
        return raw_rel.strip()
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    match = re.search(r"Raw path:\s*`([^`]+)`", text)
    return match.group(1).strip() if match else None


def hash_matches(existing: str | None, current: str) -> bool:
    if not existing:
        return False
    return current.startswith(existing) or existing.startswith(current)


def is_operational_metadata_source(source: dict[str, object]) -> bool:
    raw_path = str(source.get("raw_path") or "")
    return (
        raw_path.startswith("raw/.obsidian-wiki-export/")
        or raw_path == "raw/export-state.json"
        or raw_path.startswith("raw/progress/")
        or raw_path.startswith("raw/rss/")
        or raw_path.startswith("raw/staging/rss/")
    )


def legacy_source_page_for(source: dict[str, object], source_dir: Path) -> Path | None:
    raw_path = str(source.get("raw_path") or "")
    slug = str(source.get("slug") or "")
    if not raw_path.endswith("/index.md") or not slug.endswith("-index"):
        return None
    return source_dir / f"{slug[:-len('-index')]}.md"


def maybe_migrate_legacy_source_page(source: dict[str, object], canonical_page: Path) -> None:
    legacy_page = legacy_source_page_for(source, canonical_page.parent)
    if legacy_page is None or not legacy_page.is_file():
        return
    raw_rel = source_page_raw_rel(legacy_page)
    if raw_rel != source.get("raw_path"):
        return
    if canonical_page.exists():
        legacy_page.unlink()
        return
    canonical_page.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_page), str(canonical_page))


def is_refreshable_seed_source_page(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return "Deterministic seed page." in text


def source_refinement_state(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = source_page_metadata(path)
    state = metadata.get("ai_refinement_state") if isinstance(metadata, dict) else None
    if isinstance(state, str) and state.strip():
        return state.strip()
    if "Pending AI-native summary" in text or "Deterministic seed page." in text:
        return "pending"
    return "applied"


def build_refinement_plan(
    project: Path,
    sources: list[dict[str, object]],
    stale_sources: list[dict[str, object]],
    orphan_source_pages: list[str],
) -> dict[str, object]:
    stale_pages = {str(item.get("page") or "") for item in stale_sources}
    required_source_pages: list[dict[str, object]] = []
    allowed_write_paths: list[str] = []
    for source in sources:
        wiki_path = f"wiki/sources/{source['slug']}.md"
        page = project / wiki_path
        state = source_refinement_state(page)
        is_stale = wiki_path in stale_pages
        if state in {"pending", "stale", "missing"} or is_stale:
            reason = "stale_raw_page" if is_stale else "new_raw_page"
            required_source_pages.append(
                {
                    "raw_path": source["raw_path"],
                    "wiki_path": wiki_path,
                    "reason": reason,
                    "required": True,
                    "current_state": "stale" if is_stale else state,
                }
            )
            allowed_write_paths.append(wiki_path)

    candidate_dependents = [
        {"path": "wiki/overview.md", "reason": "layered_summary_candidate"},
        {"path": "wiki/concepts/index.md", "reason": "linked_concept_candidate"},
        {"path": "wiki/entities/index.md", "reason": "entity_name_candidate"},
    ]
    if orphan_source_pages:
        candidate_dependents.append({"path": "wiki/sources/index.md", "reason": "source_index_candidate"})
    for item in candidate_dependents:
        if (project / item["path"]).exists():
            allowed_write_paths.append(item["path"])

    allowed_write_paths.append("staging/refinement-status.md")
    semantic_update_required = bool(required_source_pages)
    trigger = "raw_changed" if semantic_update_required else "none"
    return {
        "version": 1,
        "semantic_update_required": semantic_update_required,
        "trigger": trigger,
        "required_source_pages": required_source_pages,
        "candidate_dependents": candidate_dependents if semantic_update_required else [],
        "allowed_write_paths": sorted(dict.fromkeys(allowed_write_paths)),
        "forbidden_write_paths": ["raw/**", "raw-code/**"],
        "verification": ["tools/check_refinement.py", "tools/health.py --json", "tools/build_graph.py"],
        "user_next_command": "llm-wiki update" if semantic_update_required else "",
        "user_next_action": (
            "Continue `llm-wiki update` to complete source-grounded AI-native refinement, "
            "record refinement status, then close with health and graph checks."
            if semantic_update_required
            else ""
        ),
    }


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
        "checkpoint": "Deterministic seed is complete; semantic refinement remains part of llm-wiki update.",
        "next_command": "llm-wiki update",
        "next_action": "Continue llm-wiki update for source-grounded AI-native refinement and validation closure.",
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
    plan = build_refinement_plan(project, sources, stale_sources, orphan_source_pages)
    write(project / "staging" / "refinement-plan.json", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")


def main_for_project(project: Path) -> int:
    project = project.resolve()
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
        maybe_migrate_legacy_source_page(source, page)
        existing_sha = source_page_sha(page)
        created = write_if_missing(page, source_page(source))
        if not created and not hash_matches(existing_sha, str(source["sha256"])) and is_refreshable_seed_source_page(page):
            write(page, source_page(source))
            existing_sha = str(source["sha256"])
        if (
            not created
            and not hash_matches(existing_sha, str(source["sha256"]))
            and not is_operational_metadata_source(source)
        ):
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
        if path.name != "index.md" and path.name not in current_pages
    )
    update_status(project, sources, codebases, stale_sources, orphan_source_pages)

    print(f"project={project}")
    print(f"sources={len(sources)}")
    print(f"stale_sources={len(stale_sources)}")
    print(f"orphan_source_pages={len(orphan_source_pages)}")
    print(f"codebases={len(codebases)}")
    print("status=deterministic_seed_complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()
    return main_for_project(Path(args.project))


if __name__ == "__main__":
    raise SystemExit(main())
