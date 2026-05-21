#!/usr/bin/env python3
"""Install the bundled LLM Wiki project template into a target project."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"

ENGINE_PREFIXES = (
    "tools/",
    "docs/tooling-dependencies.md",
    "docs/implementation-workflow.md",
)


def copy_tree(src: Path, dst: Path, force: bool, engine_only: bool = False) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []

    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        rel_text = rel.as_posix()
        if engine_only and not any(
            rel_text == prefix.rstrip("/") or rel_text.startswith(prefix) for prefix in ENGINE_PREFIXES
        ):
            continue
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


def parse_dependency_lines(pyproject: Path) -> list[str]:
    if not pyproject.is_file():
        return []
    lines = pyproject.read_text(encoding="utf-8").splitlines()
    deps: list[str] = []
    in_deps = False
    for line in lines:
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps and stripped == "]":
            break
        if in_deps and stripped.startswith('"'):
            deps.append(stripped.rstrip(",").strip('"'))
    return deps


def merge_pyproject_dependencies(project: Path) -> list[str]:
    template_deps = parse_dependency_lines(TEMPLATE_ROOT / "pyproject.toml")
    if not template_deps:
        return []

    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        shutil.copy2(TEMPLATE_ROOT / "pyproject.toml", pyproject)
        return template_deps

    text = pyproject.read_text(encoding="utf-8")
    existing = set(parse_dependency_lines(pyproject))
    missing = [dep for dep in template_deps if dep not in existing]
    if not missing:
        return []

    marker = "dependencies = ["
    start = text.find(marker)
    if start == -1:
        text = text.rstrip() + "\n\ndependencies = [\n" + "".join(f'  "{dep}",\n' for dep in missing) + "]\n"
    else:
        close = text.find("\n]", start)
        if close == -1:
            raise SystemExit(f"Could not parse dependencies block in {pyproject}")
        insert = "".join(f'  "{dep}",\n' for dep in missing)
        text = text[: close + 1] + insert + text[close + 1 :]
    pyproject.write_text(text, encoding="utf-8")
    return missing


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
    parser.add_argument(
        "--engine-only",
        action="store_true",
        help="Refresh only engine-owned files such as tools/ and engine docs; preserve project evidence/config files.",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not TEMPLATE_ROOT.is_dir():
        raise SystemExit(f"Missing project template: {TEMPLATE_ROOT}")

    project.mkdir(parents=True, exist_ok=True)
    copied, skipped = copy_tree(TEMPLATE_ROOT, project, args.force, args.engine_only)
    merged_deps = merge_pyproject_dependencies(project) if args.engine_only else []
    # build_wiki.py requires raw/; the template does not ship evidence files (often gitignored).
    (project / "raw").mkdir(parents=True, exist_ok=True)

    print(f"project={project}")
    print(f"template={TEMPLATE_ROOT}")
    print(f"copied={len(copied)}")
    for item in copied:
        print(f"  + {item}")
    if skipped:
        print(f"skipped_existing={len(skipped)}")
        for item in skipped:
            print(f"  = {item}")
    if merged_deps:
        print(f"merged_dependencies={len(merged_deps)}")
        for item in merged_deps:
            print(f"  ~ {item}")
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
