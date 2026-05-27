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

QUERY_ROUTING_HEADING = "## Query Routing"
CWIKI_AUTH_HEADING = "## Cwiki Authentication"
LEGACY_CWIKI_HEADINGS = ("## Cwiki 原始文档同步",)


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
        if target.exists() and not (force or engine_only):
            skipped.append(str(rel))
            continue

        shutil.copy2(path, target)
        copied.append(str(rel))

    return copied, skipped


def extract_template_section(heading: str) -> str:
    template_agents = TEMPLATE_ROOT / "AGENTS.md"
    text = template_agents.read_text(encoding="utf-8")
    start = text.find(heading)
    if start == -1:
        raise SystemExit(f"Missing {heading!r} in {template_agents}")

    next_heading = text.find("\n## ", start + len(heading))
    if next_heading == -1:
        section = text[start:].strip()
    else:
        section = text[start:next_heading].strip()
    return section + "\n"


def extract_template_query_routing() -> str:
    return extract_template_section(QUERY_ROUTING_HEADING)


def extract_template_cwiki_auth() -> str:
    return extract_template_section(CWIKI_AUTH_HEADING)


def replace_section(text: str, heading: str, replacement: str) -> tuple[str, bool]:
    start = text.find(heading)
    if start == -1:
        return text, False
    next_heading = text.find("\n## ", start + len(heading))
    end = len(text) if next_heading == -1 else next_heading
    return text[:start].rstrip() + "\n\n" + replacement.rstrip() + "\n\n" + text[end:].lstrip(), True


def insert_after_first_heading(text: str, section: str) -> str:
    if text.startswith("# "):
        first_break = text.find("\n")
        insert_at = first_break + 1 if first_break != -1 else len(text)
        return text[:insert_at].rstrip() + "\n\n" + section + "\n" + text[insert_at:].lstrip()
    return "# LLM Wiki Project Rules\n\n" + section + "\n" + text.lstrip()


def refresh_agent_rules(project: Path) -> str:
    agents = project / "AGENTS.md"
    query_routing = extract_template_query_routing()
    cwiki_auth = extract_template_cwiki_auth()

    if not agents.is_file():
        agents.write_text("# LLM Wiki Project Rules\n\n" + query_routing + "\n" + cwiki_auth, encoding="utf-8")
        return "created"

    text = agents.read_text(encoding="utf-8")
    original = text

    if QUERY_ROUTING_HEADING not in text:
        text = insert_after_first_heading(text, query_routing)

    replaced = False
    text, replaced = replace_section(text, CWIKI_AUTH_HEADING, cwiki_auth)
    if not replaced:
        for legacy_heading in LEGACY_CWIKI_HEADINGS:
            text, replaced = replace_section(text, legacy_heading, cwiki_auth)
            if replaced:
                break
    if not replaced:
        text = insert_after_first_heading(text, cwiki_auth)

    if text == original:
        return "already_present"

    agents.write_text(text.rstrip() + "\n", encoding="utf-8")
    return "updated"


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
    parser.add_argument(
        "--refresh-agent-rules",
        action="store_true",
        help="Merge current LLM Wiki agent query-routing rules into AGENTS.md without overwriting existing content.",
    )
    parser.add_argument(
        "--agent-rules-only",
        action="store_true",
        help="Only merge current LLM Wiki agent query-routing rules into AGENTS.md; do not copy template files.",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not TEMPLATE_ROOT.is_dir():
        raise SystemExit(f"Missing project template: {TEMPLATE_ROOT}")

    project.mkdir(parents=True, exist_ok=True)
    if args.agent_rules_only:
        agent_rules_status = refresh_agent_rules(project)
        print(f"project={project}")
        print(f"template={TEMPLATE_ROOT}")
        print(f"agent_rules={agent_rules_status}")
        return 0

    copied, skipped = copy_tree(TEMPLATE_ROOT, project, args.force, args.engine_only)
    merged_deps = merge_pyproject_dependencies(project) if args.engine_only else []
    agent_rules_status = refresh_agent_rules(project) if args.refresh_agent_rules else None
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
    if agent_rules_status:
        print(f"agent_rules={agent_rules_status}")
    print("next_commands:")
    print("  llm-wiki update")
    print("  # optional after the text layer is healthy and high-value image evidence exists:")
    print("  llm-wiki image")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
