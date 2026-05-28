#!/usr/bin/env python3
"""Migrate a KB project to Gateway raw-published mode."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


CANONICAL_METADATA_DIR = "staging/wiki-export-state"
RAW_PUBLISHED_IGNORES = [
    "raw/progress/",
    "raw/export-state.json",
    "raw/.obsidian-wiki-export/",
    "raw/rss/",
    "raw/staging/rss/",
    "raw-code/",
    ".DS_Store",
    "**/.DS_Store",
    "__pycache__/",
    ".pytest_cache/",
    "graphify-out/",
]
WHOLE_RAW_IGNORES = {"raw", "raw/", "/raw", "/raw/"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def git_dirty(project: Path) -> bool:
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project, capture_output=True, text=True)
    if probe.returncode != 0:
        return False
    status = subprocess.run(["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True)
    return bool(status.stdout.strip())


def gitignore_lines(project: Path) -> list[str]:
    path = project / ".gitignore"
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def raw_is_ignored(project: Path) -> bool:
    for line in gitignore_lines(project):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped in WHOLE_RAW_IGNORES:
            return True
    return False


def rewrite_gitignore(project: Path) -> bool:
    existing = gitignore_lines(project)
    kept: list[str] = []
    for line in existing:
        stripped = line.strip()
        if stripped in WHOLE_RAW_IGNORES:
            continue
        if stripped in RAW_PUBLISHED_IGNORES:
            continue
        kept.append(line)
    if kept and kept[-1].strip():
        kept.append("")
    kept.extend(RAW_PUBLISHED_IGNORES)
    next_text = "\n".join(kept).rstrip() + "\n"
    path = project / ".gitignore"
    old_text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if old_text == next_text:
        return False
    path.write_text(next_text, encoding="utf-8")
    return True


def normalize_metadata_dir(value: object, project: Path) -> tuple[str, str | None]:
    text = str(value or "").strip()
    if not text or text == "staging/wiki-export":
        return CANONICAL_METADATA_DIR, None
    path_value = Path(text)
    if not path_value.is_absolute():
        return path_value.as_posix(), None
    try:
        return path_value.resolve().relative_to(project.resolve()).as_posix(), None
    except ValueError:
        return text, "metadata_dir_outside_project"


def source_config_path(project: Path) -> Path:
    return project / "upstream" / "wiki-sources.json"


def normalize_wiki_sources(project: Path, *, apply: bool) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    path = source_config_path(project)
    payload = read_json(path)
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return warnings, blockers
    changed = False
    for source in sources:
        if not isinstance(source, dict) or source.get("type") != "confluence":
            continue
        metadata_dir, blocker = normalize_metadata_dir(source.get("metadata_dir"), project)
        if blocker:
            blockers.append(blocker)
            continue
        if source.get("metadata_dir") == "staging/wiki-export":
            warnings.append("legacy_wiki_export_metadata_dir")
        if source.get("metadata_dir") != metadata_dir:
            source["metadata_dir"] = metadata_dir
            changed = True
    if apply and changed:
        write_json(path, payload)
    return warnings, blockers


def ensure_manifest_raw(project: Path) -> bool:
    path = project / "kb.manifest.yaml"
    payload = read_yaml(path)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
        payload["evidence"] = evidence
    if evidence.get("raw") is True:
        return False
    evidence["raw"] = True
    write_yaml(path, payload)
    return True


def raw_index_exists(project: Path) -> bool:
    raw = project / "raw"
    return raw.is_dir() and any(raw.glob("**/index.md"))


def copy_if_missing(src: Path, dst: Path) -> bool:
    if not src.exists() or dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def copy_legacy_state(project: Path) -> list[str]:
    actions: list[str] = []
    canonical = project / CANONICAL_METADATA_DIR
    for legacy_dir in [project / "staging" / "wiki-export", project / "raw"]:
        if copy_if_missing(legacy_dir / "export-state.json", canonical / "export-state.json"):
            actions.append(f"copied:{legacy_dir / 'export-state.json'}")
        if copy_if_missing(legacy_dir / "progress", canonical / "progress"):
            actions.append(f"copied:{legacy_dir / 'progress'}")
    return actions


def build_report(project: Path, *, status: str, warnings: list[str], blockers: list[str], actions: list[str]) -> dict[str, object]:
    return {
        "version": 1,
        "status": status,
        "generated_at": utc_now(),
        "project": str(project),
        "warnings": sorted(dict.fromkeys(warnings)),
        "blockers": sorted(dict.fromkeys(blockers)),
        "actions": actions,
    }


def write_report(project: Path, report: dict[str, object]) -> None:
    report_dir = project / "staging" / "migrations"
    write_json(report_dir / "raw-publish-mode-latest.json", report)
    lines = [
        "# Raw Publish Mode Migration",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Warnings",
        *[f"- `{item}`" for item in report["warnings"]],
        "",
        "## Blockers",
        *[f"- `{item}`" for item in report["blockers"]],
        "",
        "## Actions",
        *[f"- `{item}`" for item in report["actions"]],
        "",
    ]
    (report_dir / "raw-publish-mode-latest.md").write_text("\n".join(lines), encoding="utf-8")


def check_project(project: Path) -> dict[str, object]:
    warnings: list[str] = []
    blockers: list[str] = []
    actions: list[str] = []
    if raw_is_ignored(project):
        warnings.append("raw_ignored")
    if not raw_index_exists(project):
        warnings.append("raw_index_missing")
    source_warnings, source_blockers = normalize_wiki_sources(project, apply=False)
    warnings.extend(source_warnings)
    blockers.extend(source_blockers)
    status = "blocked" if blockers else "needs_migration" if warnings else "ok"
    return build_report(project, status=status, warnings=warnings, blockers=blockers, actions=actions)


def apply_project(project: Path, *, allow_dirty: bool = False) -> dict[str, object]:
    if not allow_dirty and git_dirty(project):
        report = build_report(project, status="blocked", warnings=[], blockers=["dirty_worktree"], actions=[])
        write_report(project, report)
        return report
    warnings: list[str] = []
    blockers: list[str] = []
    actions: list[str] = []
    if rewrite_gitignore(project):
        actions.append("rewrote:.gitignore")
    if ensure_manifest_raw(project):
        actions.append("updated:kb.manifest.yaml")
    source_warnings, source_blockers = normalize_wiki_sources(project, apply=True)
    warnings.extend(source_warnings)
    blockers.extend(source_blockers)
    actions.extend(copy_legacy_state(project))
    if not raw_index_exists(project):
        warnings.append("raw_index_missing")
    status = "blocked" if blockers else "applied"
    report = build_report(project, status=status, warnings=warnings, blockers=blockers, actions=actions)
    write_report(project, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--project", default=".")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    report = check_project(project) if args.check else apply_project(project, allow_dirty=args.allow_dirty)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={report['status']}")
        for blocker in report["blockers"]:
            print(f"blocker={blocker}")
        for warning in report["warnings"]:
            print(f"warning={warning}")
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
