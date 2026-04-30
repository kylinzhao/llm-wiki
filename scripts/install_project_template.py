#!/usr/bin/env python3
"""Install the bundled LLM Wiki project template into a target project."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"


def copy_tree(src: Path, dst: Path, force: bool) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []

    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            skipped.append(str(rel))
            continue

        shutil.copy2(path, target)
        copied.append(str(rel))

    return copied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default=".",
        help="Target LLM Wiki project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template files. Use only when intentionally refreshing generated scaffolding.",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not TEMPLATE_ROOT.is_dir():
        raise SystemExit(f"Missing project template: {TEMPLATE_ROOT}")

    project.mkdir(parents=True, exist_ok=True)
    copied, skipped = copy_tree(TEMPLATE_ROOT, project, args.force)

    print(f"project={project}")
    print(f"template={TEMPLATE_ROOT}")
    print(f"copied={len(copied)}")
    for item in copied:
        print(f"  + {item}")
    if skipped:
        print(f"skipped_existing={len(skipped)}")
        for item in skipped:
            print(f"  = {item}")
    print("next_commands:")
    print("  uv run python tools/update_wiki.py")
    print("  # optional when raw-code/ exists and graphify is installed:")
    print("  uv run python tools/update_wiki.py --graphify")
    print("  # or run graphify alone:")
    print("  uv run python tools/graphify_code.py --all")
    print("  uv run python tools/health.py --json")
    print("  uv run python tools/build_graph.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
