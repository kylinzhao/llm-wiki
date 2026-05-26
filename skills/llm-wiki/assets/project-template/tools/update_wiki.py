#!/usr/bin/env python3
"""Run the deterministic LLM Wiki update pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

import yaml
from agent_rules import refresh_agent_rules
from gplus_quality import inspect_gplus_quality
from wiki_preflight import raw_code_evidence_preflight_failed, raw_evidence_preflight_failed


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_python_script(script: Path, project: Path, extra: Sequence[str] | None = None) -> int:
    command = [sys.executable, str(script), "--project", str(project)]
    if extra:
        command.extend(extra)
    print("+ " + " ".join(command))
    return subprocess.call(command)


def run_shell(command: str, project: Path) -> int:
    print("+ " + command)
    return subprocess.call(command, cwd=project, shell=True)


def run_command(command: str | Sequence[str], cwd: Path) -> int:
    if isinstance(command, str):
        display = command
        shell = True
    else:
        display = shlex.join(command)
        shell = False
    print("+ " + display)
    return subprocess.call(command, cwd=cwd, shell=shell)


def load_yaml_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_json_if_present(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_failure_report(project: Path, failed_step: str, returncode: int, details: dict[str, object] | None = None) -> None:
    report_dir = project / "staging" / "update"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "status": "failed",
        "generated_at": utc_now(),
        "failed_step": failed_step,
        "returncode": returncode,
        "details": details or {},
    }
    (report_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# LLM Wiki Update Report",
        "",
        "- Status: `failed`",
        f"- Failed step: `{failed_step}`",
        f"- Return code: `{returncode}`",
        f"- Generated at: `{payload['generated_at']}`",
        "",
        "## Failure Details",
        "",
    ]
    for key, value in (details or {}).items():
        lines.append(f"- {key}: `{value}`")
    if not details:
        lines.append("- No structured details were available.")
    (report_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_success_report(project: Path, skipped_steps: list[str] | None = None) -> None:
    report_dir = project / "staging" / "update"
    report_dir.mkdir(parents=True, exist_ok=True)
    health = read_json_if_present(project / "staging" / "health" / "latest.json")
    gplus_quality = inspect_gplus_quality(project, health if isinstance(health, dict) else {})
    payload = {
        "version": 1,
        "status": "ok",
        "generated_at": utc_now(),
        "skipped_steps": skipped_steps or [],
        "gplus_quality": gplus_quality,
    }
    (report_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# LLM Wiki Update Report",
        "",
        "- Status: `ok`",
        f"- Generated at: `{payload['generated_at']}`",
        "",
        "## Skipped Steps",
        "",
    ]
    if skipped_steps:
        for step in skipped_steps:
            lines.append(f"- `{step}`")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## G+ Semantic Quality",
            "",
            f"- Status: `{gplus_quality['status']}`",
            f"- Source pages: `{gplus_quality['metrics']['source_pages']}`",
            f"- Non-index concept pages: `{gplus_quality['metrics']['non_index_concept_pages']}`",
            f"- Concept coverage: `{gplus_quality['metrics']['concept_coverage']}`",
            f"- Manual concept/entity link placeholders: `{gplus_quality['metrics']['manual_link_placeholders']}`",
            "",
        ]
    )
    if gplus_quality["findings"]:
        for item in gplus_quality["findings"]:
            lines.append(f"- `{item['severity']}` `{item['title']}`: {item['detail']}")
        lines.extend(
            [
                "",
                "Next action: run the Codex-native G+ semantic expansion pass in `llm-wiki update`; do not rebuild `raw/` solely for these findings.",
            ]
        )
    else:
        lines.append("- No G+ semantic underfit finding from deterministic heuristics.")
    (report_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def health_failure_details(project: Path) -> dict[str, object]:
    health = read_json_if_present(project / "staging" / "health" / "latest.json")
    if not isinstance(health, dict):
        return {}
    return {
        "status": health.get("status"),
        "ok": health.get("ok"),
        "stale_sources": len(health.get("stale_sources") or []),
        "orphan_source_pages": len(health.get("orphan_source_pages") or []),
        "broken_wikilinks": len(health.get("broken_wikilinks") or []),
        "missing_required_paths": len(health.get("missing_required_paths") or []),
        "evidence_gaps": len(health.get("evidence_gaps") or []),
    }


def resolve_rss_config(project: Path) -> Path:
    manifest = load_yaml_dict(project / "kb.manifest.yaml")
    rss_path = manifest.get("rss_config_path", "config/rss-feeds.yaml")
    config_path = Path(rss_path)
    if not config_path.is_absolute():
        config_path = project / config_path
    return config_path


def default_rss_settings(project: Path) -> dict[str, object]:
    config = load_yaml_dict(resolve_rss_config(project))
    return {
        "rate_limits": config.get(
            "rate_limits",
            {"default_min_interval_seconds": 60, "max_concurrency": 1, "per_host": {}},
        ),
        "retry": config.get("retry", {"max_attempts": 2, "backoff_seconds": 30}),
    }


def legacy_rss_config_sources(project: Path) -> list[dict[str, object]]:
    config = load_yaml_dict(resolve_rss_config(project))
    feeds = config.get("feeds")
    if not isinstance(feeds, list):
        return []
    sources: list[dict[str, object]] = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        feed_id = str(feed.get("id") or "").strip()
        url = str(feed.get("url") or "").strip()
        if not feed_id or not url:
            continue
        source_url = str(feed.get("source_url") or "").strip()
        confluence_page_id = confluence_page_id_from_legacy_feed(feed_id, source_url, url)
        if confluence_page_id:
            sources.append(
                {
                    "type": "confluence",
                    "enabled": feed.get("enabled", True),
                    "source_id": f"cwiki-{confluence_page_id}",
                    "page_id": confluence_page_id,
                    "url": source_url or f"https://cwiki.guazi.com/pages/viewpage.action?pageId={confluence_page_id}",
                    "site_base": confluence_site_base(source_url or url),
                    "depth": int(feed.get("depth", 3) or 3),
                    "weekly_from_title": "",
                    "space_key": "",
                    "rss_url": url,
                    "rss_url_is_custom": True,
                    "rss_max_results": int(feed.get("rss_max_results", 200) or 200),
                    "output_dir": "raw",
                    "metadata_dir": "staging/wiki-export",
                    "migrated_from": relative_path(resolve_rss_config(project), project),
                }
            )
            continue
        sources.append(
            {
                "type": "rss",
                "enabled": feed.get("enabled", True),
                "id": feed_id,
                "url": url,
                "source_url": source_url,
                "target_dir": str(feed.get("target_dir") or f"raw/rss/{feed_id}"),
                "migrated_from": relative_path(resolve_rss_config(project), project),
            }
        )
    return sources


def confluence_site_base(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://cwiki.guazi.com"


def confluence_page_id_from_legacy_feed(feed_id: str, source_url: str, feed_url: str) -> str:
    source_match = re.search(r"[?&]pageId=(\d+)", source_url)
    if source_match:
        return source_match.group(1)
    if feed_id.isdigit() and "cwiki.guazi.com" in feed_url:
        return feed_id
    return ""


def enabled_rss_sources(project: Path) -> list[dict[str, object]]:
    sources = ensure_upstream_wiki_sources(project)
    rss_sources: list[dict[str, object]] = []
    for source in sources:
        if str(source.get("type") or "") != "rss":
            continue
        if source.get("enabled") is False:
            continue
        source_id = str(source.get("id") or "").strip()
        url = str(source.get("url") or "").strip()
        if not source_id or not url:
            continue
        rss_sources.append(source)
    return rss_sources


def write_generated_rss_config(project: Path, sources: list[dict[str, object]]) -> Path:
    settings = default_rss_settings(project)
    feeds: list[dict[str, object]] = []
    for source in sources:
        source_id = str(source.get("id") or "").strip()
        url = str(source.get("url") or "").strip()
        feeds.append(
            {
                "id": source_id,
                "url": url,
                "source_url": str(source.get("source_url") or ""),
                "target_dir": str(source.get("target_dir") or f"raw/rss/{source_id}"),
                "enabled": source.get("enabled", True),
            }
        )
    generated = project / "staging" / "update" / "rss-feeds.generated.yaml"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(
        yaml.safe_dump(
            {
                "feeds": feeds,
                "rate_limits": settings["rate_limits"],
                "retry": settings["retry"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return generated


def rss_sync_enabled(project: Path) -> bool:
    manifest = load_manifest(project)
    phases = manifest.get("phases")
    if isinstance(phases, dict) and phases.get("rss_sync") is False:
        return False
    return bool(enabled_rss_sources(project))


def auto_raw_sync_command(project: Path) -> str | None:
    if not rss_sync_enabled(project):
        return None
    config_path = write_generated_rss_config(project, enabled_rss_sources(project))
    return " ".join(
        [
            shlex.quote(sys.executable),
            shlex.quote("tools/rss_sync.py"),
            "--config",
            shlex.quote(str(config_path)),
        ]
    )


def load_manifest(project: Path) -> dict:
    return load_yaml_dict(project / "kb.manifest.yaml")


def upstream_wiki_sources_path(project: Path) -> Path:
    return project / "upstream" / "wiki-sources.json"


def relative_path(path: Path, project: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_upstream_wiki_sources(project: Path) -> dict:
    payload = read_json_if_present(upstream_wiki_sources_path(project))
    return payload if isinstance(payload, dict) else {}


def write_upstream_wiki_sources(project: Path, sources: list[dict[str, object]]) -> None:
    write_json(
        upstream_wiki_sources_path(project),
        {
            "version": 1,
            "updated_at": utc_now(),
            "sources": sources,
        },
    )


def source_filters(source: dict[str, object]) -> dict[str, object]:
    filters = source.get("filters")
    return dict(filters) if isinstance(filters, dict) else {}


def source_updated_since(source: dict[str, object]) -> str:
    filters = source_filters(source)
    return str(filters.get("updated_since") or source.get("updated_since") or "").strip()


def normalize_upstream_source(source: dict[str, object], *, default_relationship: str = "additional") -> dict[str, object]:
    normalized = dict(source)
    source_type = str(normalized.get("type") or "").strip()
    if source_type == "confluence":
        page_id = str(normalized.get("page_id") or "").strip()
        if page_id and not str(normalized.get("source_id") or "").strip():
            normalized["source_id"] = f"cwiki-{page_id}"
    elif source_type == "rss":
        source_id = str(normalized.get("id") or normalized.get("source_id") or "").strip()
        if source_id and not str(normalized.get("source_id") or "").strip():
            normalized["source_id"] = f"rss-{source_id}"

    relationship = normalized.get("relationship")
    if not isinstance(relationship, dict):
        normalized["relationship"] = {"role": default_relationship}
    elif not str(relationship.get("role") or "").strip():
        relationship = dict(relationship)
        relationship["role"] = default_relationship
        normalized["relationship"] = relationship

    updated_since = str(normalized.pop("updated_since", "") or "").strip()
    filters = source_filters(normalized)
    if updated_since and not str(filters.get("updated_since") or "").strip():
        filters["updated_since"] = updated_since
    if filters:
        normalized["filters"] = filters
    return normalized


def export_state_to_upstream_sources(project: Path) -> list[dict[str, object]]:
    state_path = next(
        (
            candidate
            for candidate in [
                project / "staging" / "wiki-export" / "export-state.json",
                project / "staging" / "wiki-export-state" / "export-state.json",
                project / "raw" / "export-state.json",
            ]
            if candidate.is_file()
        ),
        project / "staging" / "wiki-export" / "export-state.json",
    )
    state = read_json_if_present(state_path)
    if not isinstance(state, dict):
        return []
    roots = state.get("roots")
    if not isinstance(roots, list):
        return []
    sources: list[dict[str, object]] = []
    for root in roots:
        if not isinstance(root, dict):
            continue
        page_id = str(root.get("page_id") or "").strip()
        url = str(root.get("url") or "").strip()
        if not page_id or not url:
            continue
        sources.append(
            {
                "type": "confluence",
                "enabled": True,
                "source_id": f"cwiki-{page_id}",
                "page_id": page_id,
                "url": url,
                "site_base": str(root.get("site_base") or ""),
                "depth": int(root.get("depth_limit", 0) or 0),
                "weekly_from_title": str(root.get("weekly_from_title") or ""),
                "space_key": str(root.get("space_key") or ""),
                "rss_url": str(root.get("rss_url") or ""),
                "rss_url_is_custom": bool(root.get("rss_url_is_custom", False)),
                "rss_max_results": int(root.get("rss_max_results", 200) or 200),
                "output_dir": "raw",
                "metadata_dir": relative_path(state_path.parent, project),
                "migrated_from": relative_path(state_path, project),
            }
        )
    return sources


def ensure_upstream_wiki_sources(project: Path) -> list[dict[str, object]]:
    config = load_upstream_wiki_sources(project)
    existing = config.get("sources")
    sources = (
        [
            normalize_upstream_source(dict(item), default_relationship="additional")
            for item in existing
            if isinstance(item, dict)
        ]
        if isinstance(existing, list)
        else []
    )
    migrated = export_state_to_upstream_sources(project)
    migrated.extend(legacy_rss_config_sources(project))
    migrated = [
        normalize_upstream_source(source, default_relationship="primary" if not sources and index == 0 else "additional")
        for index, source in enumerate(migrated)
    ]
    if not migrated:
        return sources

    def source_key(source: dict[str, object]) -> str:
        source_type = str(source.get("type") or "")
        if source_type == "confluence":
            return f"confluence:{source.get('page_id')}"
        if source_type == "rss":
            return f"rss:{source.get('id')}"
        return json.dumps(source, sort_keys=True, ensure_ascii=False)

    by_key = {source_key(source): source for source in sources}
    changed = False
    for source in migrated:
        key = source_key(source)
        if key not in by_key:
            by_key[key] = source
            changed = True
    if changed or not upstream_wiki_sources_path(project).is_file():
        merged = [by_key[key] for key in sorted(by_key)]
        write_upstream_wiki_sources(project, merged)
        return merged
    return sources


def confluence_sync_commands(project: Path) -> list[list[str]]:
    sources = ensure_upstream_wiki_sources(project)
    commands: list[list[str]] = []
    exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
    if not exporter.is_file():
        return []

    saved_state_groups: dict[str, list[dict[str, object]]] = {}
    for source in sources:
        if str(source.get("type") or "") != "confluence":
            continue
        if source.get("enabled") is False:
            continue
        page_id = str(source.get("page_id") or "").strip()
        if not page_id:
            continue
        metadata_dir_text = str(source.get("metadata_dir") or "staging/wiki-export")
        metadata_dir = project / metadata_dir_text if not Path(metadata_dir_text).is_absolute() else Path(metadata_dir_text)
        output_dir_text = str(source.get("output_dir") or "raw")
        output_dir = project / output_dir_text if not Path(output_dir_text).is_absolute() else Path(output_dir_text)
        has_state = (metadata_dir / "export-state.json").is_file() or (output_dir / "export-state.json").is_file()
        if has_state:
            saved_state_groups.setdefault(str(metadata_dir), []).append(source)
            continue
        command = [
            sys.executable,
            str(exporter),
            "--project-dir",
            str(project),
            "--metadata-dir",
            str(metadata_dir),
            "--levels",
            str(int(source.get("depth", 0) or 0)),
        ]
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        command.extend(["--url", url])
        sso_skill_root = os.environ.get("GUAZI_SSO_SKILL_ROOT", "").strip()
        command.append("--auto-cookie-from-sso")
        if sso_skill_root:
            command.extend(["--sso-skill-root", sso_skill_root])
        updated_since = source_updated_since(source)
        if updated_since:
            command.extend(["--updated-since", updated_since])
        rss_url = str(source.get("rss_url") or "").strip()
        if page_id and rss_url:
            command.extend(["--rss-url", f"{page_id}={rss_url}"])
        commands.append(command)

    for metadata_dir, grouped_sources in sorted(saved_state_groups.items()):
        command = [
            sys.executable,
            str(exporter),
            "--project-dir",
            str(project),
            "--metadata-dir",
            metadata_dir,
            "--update",
        ]
        sso_skill_root = os.environ.get("GUAZI_SSO_SKILL_ROOT", "").strip()
        command.append("--auto-cookie-from-sso")
        if sso_skill_root:
            command.extend(["--sso-skill-root", sso_skill_root])
        updated_since_values = {
            source_updated_since(source)
            for source in grouped_sources
            if source_updated_since(source)
        }
        if len(updated_since_values) == 1:
            command.extend(["--updated-since", next(iter(updated_since_values))])
        for source in grouped_sources:
            page_id = str(source.get("page_id") or "").strip()
            rss_url = str(source.get("rss_url") or "").strip()
            if page_id and rss_url:
                command.extend(["--rss-url", f"{page_id}={rss_url}"])
        if any(source.get("rss_include_new") is not False for source in grouped_sources):
            command.append("--rss-include-new")
        commands.append(command)
    return commands


def run_confluence_sync(project: Path) -> int:
    for command in confluence_sync_commands(project):
        code = run_command(command, project)
        if code != 0:
            return code
    return 0


def git_worktree_dirty(path: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return False
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return bool(status.stdout.strip())


def is_git_worktree(path: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def iter_codebases(project: Path) -> list[Path]:
    raw_code = project / "raw-code"
    if not raw_code.is_dir():
        return []
    return sorted(path for path in raw_code.iterdir() if path.is_dir())


def normalize_code_sync_command(value: object) -> str | list[str] | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    return None


def manifest_code_sync_specs(project: Path) -> list[dict[str, object]]:
    manifest = load_manifest(project)
    overrides = manifest.get("overrides")
    if not isinstance(overrides, dict):
        return []
    entries = overrides.get("raw_code_update_commands")
    if not isinstance(entries, list):
        return []

    specs: list[dict[str, object]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise SystemExit(f"Invalid kb.manifest.yaml overrides.raw_code_update_commands[{index - 1}]: expected mapping.")
        command = normalize_code_sync_command(entry.get("command"))
        if not command:
            raise SystemExit(
                f"Invalid kb.manifest.yaml overrides.raw_code_update_commands[{index - 1}].command: expected non-empty string or string list."
            )
        codebase = entry.get("codebase")
        cwd_value = entry.get("cwd")
        if codebase and not isinstance(codebase, str):
            raise SystemExit(
                f"Invalid kb.manifest.yaml overrides.raw_code_update_commands[{index - 1}].codebase: expected string."
            )
        if cwd_value and not isinstance(cwd_value, str):
            raise SystemExit(
                f"Invalid kb.manifest.yaml overrides.raw_code_update_commands[{index - 1}].cwd: expected string."
            )
        if not codebase and not cwd_value:
            raise SystemExit(
                f"Invalid kb.manifest.yaml overrides.raw_code_update_commands[{index - 1}]: set codebase or cwd."
            )

        if cwd_value:
            cwd = Path(cwd_value)
            if not cwd.is_absolute():
                cwd = project / cwd
        else:
            cwd = project / "raw-code" / str(codebase)
        specs.append({"label": str(codebase or cwd.name), "cwd": cwd, "command": command})
    return specs


def default_code_sync_specs(project: Path) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for path in iter_codebases(project):
        if is_git_worktree(path):
            specs.append({"label": path.name, "cwd": path, "command": ["git", "pull", "--ff-only"]})
    return specs


def cli_code_sync_specs(project: Path, command_value: object) -> list[dict[str, object]]:
    command = normalize_code_sync_command(command_value)
    if not command:
        return []
    return [{"label": path.name, "cwd": path, "command": command} for path in iter_codebases(project)]


def run_code_sync(project: Path, cli_command: object, skip_auto: bool) -> int:
    specs = cli_code_sync_specs(project, cli_command)
    if not specs and not skip_auto:
        specs = manifest_code_sync_specs(project)
    if not specs and not skip_auto:
        specs = default_code_sync_specs(project)
    for spec in specs:
        cwd = spec["cwd"]
        assert isinstance(cwd, Path)
        if not cwd.is_dir():
            print(f"missing raw-code updater target: {cwd}", file=sys.stderr)
            return 2
        if git_worktree_dirty(cwd):
            print(
                f"dirty_raw_code_worktree: {cwd} has uncommitted changes. "
                "Refusing to auto-update this codebase; clean or stash it first.",
                file=sys.stderr,
            )
            return 2
        command = spec["command"]
        assert isinstance(command, (str, list))
        code = run_command(command, cwd)
        if code != 0:
            return code
    return 0


def deterministic_steps(tools: Path, graphify: bool = False) -> list[tuple[Path, list[str]]]:
    steps = [
        (tools / "build_wiki.py", []),
        (tools / "cjira_registry.py", ["--refresh"]),
        (tools / "scan_code.py", []),
        (tools / "build_traceability.py", []),
        (tools / "health.py", ["--json"]),
        (tools / "build_graph.py", []),
        (tools / "anchor_check.py", []),
    ]
    if graphify:
        steps.insert(3, (tools / "graphify_code.py", ["--all"]))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument(
        "--raw-sync-command",
        default="",
        help="Optional shell command that refreshes raw/ before the deterministic update steps.",
    )
    parser.add_argument(
        "--no-auto-raw-sync",
        action="store_true",
        help="Skip automatic RSS-based raw sync even when enabled feeds are configured.",
    )
    parser.add_argument(
        "--graphify",
        action="store_true",
        help="Also run graphify for all raw-code codebases. Missing graphify is recorded as skipped.",
    )
    parser.add_argument(
        "--code-sync-command",
        nargs="+",
        help=(
            "Optional command to run inside each raw-code/<codebase_id>/ before scan_code. "
            "Example: --code-sync-command git pull --ff-only"
        ),
    )
    parser.add_argument(
        "--no-auto-code-sync",
        action="store_true",
        help="Skip both manifest-configured and default raw-code auto-update commands.",
    )
    parser.add_argument(
        "--no-agent-rules-refresh",
        action="store_true",
        help="Skip automatic AGENTS.md query-routing rule maintenance.",
    )
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not args.no_agent_rules_refresh:
        print(f"agent_rules={refresh_agent_rules(project)}")

    err = raw_evidence_preflight_failed(project)
    if err:
        print(err, file=sys.stderr)
        write_failure_report(project, "raw_evidence_preflight", 2, {"error": err})
        return 2

    tools = project / "tools"
    raw_sync_command = args.raw_sync_command.strip()
    no_auto_raw_sync = args.no_auto_raw_sync or os.environ.get("LLM_WIKI_NO_AUTO_RAW_SYNC") == "1"
    no_auto_code_sync = args.no_auto_code_sync or os.environ.get("LLM_WIKI_NO_AUTO_CODE_SYNC") == "1"
    skipped_steps: list[str] = []
    if no_auto_raw_sync:
        skipped_steps.append("auto_raw_sync")
        skipped_steps.append("confluence_sync")
    if no_auto_code_sync:
        skipped_steps.append("auto_code_sync")

    if not raw_sync_command and not no_auto_raw_sync:
        raw_sync_command = auto_raw_sync_command(project) or ""

    if not no_auto_raw_sync:
        code = run_confluence_sync(project)
        if code != 0:
            write_failure_report(project, "confluence_sync", code)
            return code

    if raw_sync_command:
        code = run_shell(raw_sync_command, project)
        if code != 0:
            write_failure_report(project, "raw_sync", code)
            return code

    code = run_code_sync(project, args.code_sync_command, no_auto_code_sync)
    if code != 0:
        write_failure_report(project, "code_sync", code)
        return code

    steps = deterministic_steps(tools, graphify=bool(args.graphify))

    exit_code = 0
    for script, extra in steps:
        if not script.is_file():
            print(f"missing script: {script}", file=sys.stderr)
            return 2
        if script.name in {"scan_code.py", "graphify_code.py"}:
            code_err = raw_code_evidence_preflight_failed(project)
            if code_err:
                print(code_err, file=sys.stderr)
                write_failure_report(project, "raw_code_evidence_preflight", 2, {"error": code_err})
                return 2
        code = run_python_script(script, project, extra)
        if code != 0:
            exit_code = code
            details = health_failure_details(project) if script.name == "health.py" else {}
            write_failure_report(project, script.stem, code, details)
            if script.name != "health.py":
                break
    if exit_code == 0:
        write_success_report(project, skipped_steps=skipped_steps)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
