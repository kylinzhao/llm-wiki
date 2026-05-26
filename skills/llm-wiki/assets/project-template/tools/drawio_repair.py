#!/usr/bin/env python3
"""Repair draw.io evidence files under raw/.

This is a deterministic maintenance step. It does not infer business meaning;
it only converts draw.io graph cells into Mermaid text evidence and links that
evidence from the nearest raw page ``index.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from drawio_diagram import DrawioDiagram, drawio_to_mermaid


DRAWIO_EXTENSIONS = {".drawio", ".dio"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_drawio_files(project: Path) -> list[Path]:
    raw = project / "raw"
    if not raw.is_dir():
        return []
    return sorted(
        path
        for path in raw.rglob("*")
        if path.is_file()
        and path.suffix.lower() in DRAWIO_EXTENSIONS
        and not path.name.startswith(".")
    )


def raw_page_index(project: Path, drawio_path: Path) -> Path | None:
    raw = project / "raw"
    try:
        drawio_path.relative_to(raw)
    except ValueError:
        return None
    for parent in [drawio_path.parent, *drawio_path.parents]:
        if parent == raw.parent:
            break
        candidate = parent / "index.md"
        if candidate.is_file():
            return candidate
        if parent == raw:
            break
    return None


def rel_from_page(page_index: Path, target: Path) -> str:
    return target.relative_to(page_index.parent).as_posix()


def evidence_path_for(drawio_path: Path) -> Path:
    return drawio_path.with_suffix(drawio_path.suffix + ".md")


def evidence_markdown(project: Path, drawio_path: Path, diagrams: list[DrawioDiagram]) -> str:
    raw_rel = drawio_path.relative_to(project).as_posix()
    lines = [
        f"# Draw.io Evidence: {drawio_path.name}",
        "",
        f"- Source attachment: `{raw_rel}`",
        f"- SHA-256: `{sha256_file(drawio_path)}`",
        "",
    ]
    for diagram in diagrams:
        lines.extend(
            [
                f"## {diagram.name}",
                "",
                f"- Nodes: `{diagram.node_count}`",
                f"- Edges: `{diagram.edge_count}`",
                "",
                "```mermaid",
                diagram.mermaid,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def page_section(page_index: Path, drawio_path: Path, evidence_path: Path, diagrams: list[DrawioDiagram]) -> str:
    rel_drawio = rel_from_page(page_index, drawio_path)
    rel_evidence = rel_from_page(page_index, evidence_path)
    lines = [
        f"### {drawio_path.name}",
        "",
        f"- 附件: [`{rel_drawio}`]({rel_drawio})",
        f"- 结构化证据: [`{rel_evidence}`]({rel_evidence})",
        "",
    ]
    for diagram in diagrams:
        lines.extend(
            [
                f"#### {diagram.name}",
                "",
                f"- Nodes: `{diagram.node_count}`",
                f"- Edges: `{diagram.edge_count}`",
                "",
                "```mermaid",
                diagram.mermaid,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def replace_drawio_section(text: str, section: str) -> str:
    pattern = re.compile(r"(?ms)^## Draw\.io Diagrams\n.*?(?=^## |\Z)")
    replacement = "## Draw.io Diagrams\n\n" + section.rstrip() + "\n\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1).rstrip() + "\n"
    return text.rstrip() + "\n\n" + replacement


def repair_drawio_file(project: Path, drawio_path: Path, *, check: bool = False) -> dict[str, object]:
    rel = drawio_path.relative_to(project).as_posix()
    evidence_path = evidence_path_for(drawio_path)
    page_index = raw_page_index(project, drawio_path)
    text = drawio_path.read_text(encoding="utf-8", errors="replace")
    diagrams = drawio_to_mermaid(text, fallback_name=drawio_path.stem)
    record: dict[str, object] = {
        "path": rel,
        "evidence_path": evidence_path.relative_to(project).as_posix(),
        "page_index": page_index.relative_to(project).as_posix() if page_index else "",
        "diagram_count": len(diagrams),
        "node_count": sum(diagram.node_count for diagram in diagrams),
        "edge_count": sum(diagram.edge_count for diagram in diagrams),
        "status": "converted" if diagrams else "unparsed",
        "changed": False,
    }
    if not diagrams:
        return record

    evidence_text = evidence_markdown(project, drawio_path, diagrams)
    evidence_changed = not evidence_path.is_file() or evidence_path.read_text(encoding="utf-8", errors="replace") != evidence_text
    if evidence_changed:
        record["changed"] = True
        if not check:
            evidence_path.write_text(evidence_text, encoding="utf-8")

    if page_index is None:
        record["status"] = "converted_without_page_index"
        return record

    section = page_section(page_index, drawio_path, evidence_path, diagrams)
    page_text = page_index.read_text(encoding="utf-8", errors="replace")
    updated_page_text = replace_drawio_section(page_text, section)
    if updated_page_text != page_text:
        record["changed"] = True
        if not check:
            page_index.write_text(updated_page_text, encoding="utf-8")
    return record


def build_report(project: Path, *, check: bool = False) -> dict[str, object]:
    records = [repair_drawio_file(project, path, check=check) for path in iter_drawio_files(project)]
    converted = [record for record in records if str(record.get("status")) in {"converted", "converted_without_page_index"}]
    unparsed = [record for record in records if record.get("status") == "unparsed"]
    missing_evidence = [
        record
        for record in converted
        if not (project / str(record.get("evidence_path") or "")).is_file()
    ]
    return {
        "generated_at": utc_now(),
        "project": str(project),
        "check": check,
        "drawio_count": len(records),
        "converted_count": len(converted),
        "unparsed_count": len(unparsed),
        "missing_evidence_count": len(missing_evidence),
        "changed_count": sum(1 for record in records if record.get("changed") is True),
        "records": records,
    }


def write_report(project: Path, report: dict[str, object]) -> None:
    out = project / "staging" / "drawio" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--check", action="store_true", help="Only report missing or stale generated evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON report only.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    report = build_report(project, check=bool(args.check))
    if not args.check:
        write_report(project, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "drawio="
            f"{report['drawio_count']} converted={report['converted_count']} "
            f"unparsed={report['unparsed_count']} changed={report['changed_count']}"
        )
    return 1 if report["unparsed_count"] or report["missing_evidence_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
