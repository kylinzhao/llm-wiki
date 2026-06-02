#!/usr/bin/env python3
"""Split references/commands.md into references/commands/*.md for lazy loading."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS_MD = ROOT / "skills/llm-wiki/references/commands.md"
OUT_DIR = ROOT / "skills/llm-wiki/references/commands"

# ## `llm-wiki foo` -> foo.md; ### under Other Commands handled separately
NAMED_SECTIONS = {
    "fast": "fast.md",
    "update": "update.md",
    "backfill": "backfill.md",
    "maintain-all": "maintain-all.md",
    "update-skill": "update-skill.md",
    "add-wiki": "add-wiki.md",
    "add-code": "add-code.md",
    "doctor": "doctor.md",
    "review-requirement": "review-requirement.md",
}

# Only subsections that are NOT already top-level ## `llm-wiki …` sections
OTHER_SUBSECTIONS = {
    "init": "init.md",
    "query": "query.md",
    "query-plus": "query-plus.md",
    "image": "image.md",
}


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (title, body) for each top-level ## section after the title."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            if current_title or current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title or current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def main() -> int:
    text = COMMANDS_MD.read_text(encoding="utf-8")
    sections = split_sections(text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    shared_parts: list[str] = []
    written: list[str] = []

    preamble = ""
    for title, body in sections:
        if not title:
            preamble = body.strip()
            continue
        if title == "Other Commands":
            # Parse ### subsections
            chunks = re.split(r"(?=^### `llm-wiki )", body, flags=re.MULTILINE)
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue
                m = re.match(r"^### `llm-wiki ([^`]+)`", chunk)
                if not m:
                    continue
                cmd = m.group(1).strip()
                if cmd in OTHER_SUBSECTIONS and cmd not in NAMED_SECTIONS:
                    fname = OTHER_SUBSECTIONS[cmd]
                    header = f"## `llm-wiki {cmd}`\n\n"
                    (OUT_DIR / fname).write_text(header + chunk.split("\n", 1)[1].strip() + "\n", encoding="utf-8")
                    written.append(fname)
            continue

        m = re.match(r"`llm-wiki ([^`]+)`", title)
        if m:
            cmd = m.group(1)
            fname = NAMED_SECTIONS.get(cmd)
            if fname:
                (OUT_DIR / fname).write_text(f"## {title}\n\n{body}\n", encoding="utf-8")
                written.append(fname)
                continue

        # Shared preamble sections
        shared_parts.append(f"## {title}\n\n{body}")

    intro = "# Commands\n\n"
    if preamble:
        intro += preamble + "\n\n"
    shared_text = intro + "# Shared command protocol\n\n" + "\n\n".join(shared_parts) + "\n"
    (OUT_DIR / "_shared.md").write_text(shared_text, encoding="utf-8")
    written.insert(0, "_shared.md")

  # Thin index for humans and backward-compatible grep
    index_lines = [
        "# Commands (index)",
        "",
        "Agent 执行单条 `llm-wiki` 子命令时**不要**加载本文件全文；只加载：",
        "",
        "1. `references/commands/_shared.md`",
        "2. `references/commands/<command>.md`（与当前子命令对应）",
        "",
        "完整协议已按命令拆分在 `references/commands/` 目录。",
        "",
        "| 子命令 | 文件 |",
        "| --- | --- |",
    ]
    for cmd, fname in sorted({**NAMED_SECTIONS, **OTHER_SUBSECTIONS}.items(), key=lambda x: x[1]):
        index_lines.append(f"| `llm-wiki {cmd}` | [`{fname}`](./commands/{fname}) |")
    index_lines.append("")
    COMMANDS_MD.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    print("Wrote:", ", ".join(sorted(set(written))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
