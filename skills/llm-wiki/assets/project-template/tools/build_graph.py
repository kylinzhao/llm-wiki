#!/usr/bin/env python3
"""Build a simple graph from wiki Markdown pages and wikilinks."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def title_for(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def node_aliases(node_id: str) -> set[str]:
    aliases = {node_id}
    aliases.add(node_id.rsplit("/", 1)[-1])
    if node_id.endswith("/index"):
        aliases.add(node_id[: -len("/index")])
    if node_id.startswith("sources/") and node_id.endswith("-index"):
        aliases.add(node_id[: -len("-index")])
    return aliases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    wiki = project / "wiki"
    if not wiki.is_dir():
        raise SystemExit("Missing wiki/ directory. Run tools/build_wiki.py first.")

    pages = sorted(path for path in wiki.rglob("*.md") if path.is_file())
    nodes = []
    edges = []
    node_ids = set()
    for page in pages:
        rel = page.relative_to(wiki).with_suffix("").as_posix()
        node_ids.update(node_aliases(rel))
        nodes.append(
            {
                "id": rel,
                "path": f"wiki/{page.relative_to(wiki).as_posix()}",
                "title": title_for(page),
            }
        )

    for page in pages:
        source = page.relative_to(wiki).with_suffix("").as_posix()
        text = page.read_text(encoding="utf-8", errors="replace")
        for target in WIKILINK_RE.findall(text):
            normalized = target.strip().removesuffix(".md")
            edges.append(
                {
                    "source": source,
                    "target": normalized,
                    "target_exists": normalized in node_ids,
                }
            )

    graph_dir = project / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (graph_dir / "edges.json").write_text(json.dumps(edges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "generated_at": utc_now(),
        "nodes": len(nodes),
        "edges": len(edges),
        "broken_edges": sum(1 for edge in edges if not edge["target_exists"]),
    }
    staging_graph = project / "staging" / "graph"
    staging_graph.mkdir(parents=True, exist_ok=True)
    (staging_graph / "latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (graph_dir / "summary.md").write_text(
        "# Graph Summary\n\n"
        f"- Generated: {summary['generated_at']}\n"
        f"- Nodes: {summary['nodes']}\n"
        f"- Edges: {summary['edges']}\n"
        f"- Broken edges: {summary['broken_edges']}\n",
        encoding="utf-8",
    )

    print(f"nodes={summary['nodes']}")
    print(f"edges={summary['edges']}")
    print(f"broken_edges={summary['broken_edges']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
