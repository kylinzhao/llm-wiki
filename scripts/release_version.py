#!/usr/bin/env python3
"""Update llm-wiki bundle release version files before publishing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VERSION_FILES = [
    Path("skills/llm-wiki/VERSION"),
    Path("dist/llm-wiki-skill/VERSION"),
]
README_FILES = [
    Path("README.md"),
    Path("skills/llm-wiki/README.md"),
    Path("dist/llm-wiki-skill/README.md"),
]
MANIFEST = Path("dist/llm-wiki-skill/manifest.json")


def write_version_file(path: Path, version: str, engine_version: str) -> None:
    path.write_text(f"version: {version}\nengine_version: {engine_version}\n", encoding="utf-8")


def replace_or_insert_version_block(text: str, version: str, engine_version: str) -> str:
    block = f"## 版本\n\n- `version`: `{version}`\n- `engine_version`: `{engine_version}`\n"
    pattern = re.compile(r"## 版本\n\n- `version`: `[^`]+`\n- `engine_version`: `[^`]+`\n")
    if pattern.search(text):
        return pattern.sub(block, text, count=1)

    marker = "## 2. 适用场景"
    if marker in text:
        return text.replace(marker, block + "\n" + marker, 1)
    return text.rstrip() + "\n\n" + block


def insert_engine_note(text: str, engine_version: str, note: str) -> str:
    line = f"- **`{engine_version}`**：{note}"
    if line in text:
        return text

    if "## Engine 发行（`engine-v*`）" in text:
        marker = "## Engine 发行（`engine-v*`）\n\n"
        return text.replace(marker, marker + line + "\n", 1)

    if "### Engine 发行记录" in text:
        marker = "### Engine 发行记录\n\n"
        return text.replace(marker, marker + line + "\n", 1)

    text = replace_or_insert_version_block(text, "", "")
    marker = "## 版本\n\n- `version`: ``\n- `engine_version`: ``\n"
    release = f"\n### Engine 发行记录\n\n{line}\n"
    return text.replace(marker, marker + release, 1)


def update_release(project: Path, version: str, engine_version: str, note: str) -> None:
    project = project.resolve()
    for rel in VERSION_FILES:
        write_version_file(project / rel, version, engine_version)

    manifest_path = project / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for rel in README_FILES:
        path = project / rel
        text = path.read_text(encoding="utf-8")
        if rel.name == "README.md" and rel.parts[0] != "README.md":
            text = replace_or_insert_version_block(text, version, engine_version)
        text = insert_engine_note(text, engine_version, note)
        text = text.replace("- `version`: ``", f"- `version`: `{version}`")
        text = text.replace("- `engine_version`: ``", f"- `engine_version`: `{engine_version}`")
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="llm-wiki-skill repository root")
    parser.add_argument("--version", required=True, help="Bundle version, for example 1.0.2")
    parser.add_argument("--engine-version", required=True, help="Engine version tag, for example engine-v1.0.2")
    parser.add_argument("--note", required=True, help="Release note sentence in Chinese")
    args = parser.parse_args()

    update_release(Path(args.project), args.version, args.engine_version, args.note)
    print(f"version={args.version}")
    print(f"engine_version={args.engine_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
