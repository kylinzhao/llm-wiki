#!/usr/bin/env python3
"""Run the deterministic LLM Wiki update pipeline."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import yaml
from wiki_preflight import raw_code_evidence_preflight_failed, raw_evidence_preflight_failed


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


def resolve_rss_config(project: Path) -> Path:
    manifest = load_yaml_dict(project / "kb.manifest.yaml")
    rss_path = manifest.get("rss_config_path", "config/rss-feeds.yaml")
    config_path = Path(rss_path)
    if not config_path.is_absolute():
        config_path = project / config_path
    return config_path


def rss_sync_enabled(project: Path) -> bool:
    config_path = resolve_rss_config(project)
    config = load_yaml_dict(config_path)
    feeds = config.get("feeds")
    if not isinstance(feeds, list):
        return False
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        if feed.get("enabled") is False:
            continue
        if str(feed.get("url") or "").strip():
            return True
    return False


def auto_raw_sync_command(project: Path) -> str | None:
    if not rss_sync_enabled(project):
        return None
    config_path = resolve_rss_config(project)
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
    args = parser.parse_args()

    project = Path(args.project).resolve()
    err = raw_evidence_preflight_failed(project)
    if err:
        print(err, file=sys.stderr)
        return 2

    tools = project / "tools"
    raw_sync_command = args.raw_sync_command.strip()
    if not raw_sync_command and not args.no_auto_raw_sync:
        raw_sync_command = auto_raw_sync_command(project) or ""

    if raw_sync_command:
        code = run_shell(raw_sync_command, project)
        if code != 0:
            return code

    code = run_code_sync(project, args.code_sync_command, args.no_auto_code_sync)
    if code != 0:
        return code

    steps = [
        (tools / "build_wiki.py", []),
        (tools / "scan_code.py", []),
        (tools / "build_traceability.py", []),
        (tools / "health.py", ["--json"]),
        (tools / "build_graph.py", []),
        (tools / "anchor_check.py", []),
    ]
    if args.graphify:
        steps.insert(2, (tools / "graphify_code.py", ["--all"]))

    exit_code = 0
    for script, extra in steps:
        if not script.is_file():
            print(f"missing script: {script}", file=sys.stderr)
            return 2
        if script.name in {"scan_code.py", "graphify_code.py"}:
            code_err = raw_code_evidence_preflight_failed(project)
            if code_err:
                print(code_err, file=sys.stderr)
                return 2
        code = run_python_script(script, project, extra)
        if code != 0:
            exit_code = code
            if script.name != "health.py":
                break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
