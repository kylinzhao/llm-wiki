#!/usr/bin/env python3
"""Update the installed LLM Wiki skill bundle from a local bundle checkout."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]


def run(command: list[str], cwd: Path) -> int:
    print("+ " + " ".join(command))
    return subprocess.call(command, cwd=cwd)


def default_bundle_root() -> Path | None:
    # Source checkout layout: <bundle>/skills/llm-wiki/scripts/this_file.py
    candidate = SCRIPT_PATH.parents[3]
    if (candidate / "install.sh").is_file() and (candidate / "skills" / "llm-wiki").is_dir():
        return candidate
    return None


def resolve_bundle_root(source: str | None) -> Path:
    if source:
        root = Path(source).expanduser().resolve()
    else:
        root = default_bundle_root()
        if root is None:
            raise SystemExit(
                "Could not infer the llm-wiki skill bundle checkout from this installed skill. "
                "Pass --source /path/to/llm-wiki-skill."
            )

    if not (root / "install.sh").is_file():
        raise SystemExit(f"Missing install.sh in bundle source: {root}")
    if not (root / "skills" / "llm-wiki").is_dir():
        raise SystemExit(f"Missing skills/llm-wiki in bundle source: {root}")
    return root


def is_git_worktree(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        help="Local llm-wiki-skill bundle checkout. Required when this script is running from a copied installed skill.",
    )
    parser.add_argument(
        "--client",
        default="auto",
        choices=["auto", "codex", "claude", "cursor", "all"],
        help="Client skill directory to update. Defaults to auto.",
    )
    parser.add_argument("--mode", default="--copy", choices=["--copy", "--link"], help="Install mode.")
    parser.add_argument("--backup", action="store_true", help="Back up existing installed skills before updating.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing installed skills without backup.")
    parser.add_argument(
        "--backup-dir",
        help=(
            "Backup destination directory passed to install.sh --backup-dir. "
            "Defaults to $LLM_WIKI_SKILL_BACKUP_DIR or ~/.llm-wiki-skill-backups."
        ),
    )
    parser.add_argument("--no-pull", action="store_true", help="Do not git pull the source checkout before installing.")
    args = parser.parse_args()

    if args.backup and args.force:
        raise SystemExit("Choose only one of --backup or --force.")

    bundle_root = resolve_bundle_root(args.source)
    if not args.no_pull and is_git_worktree(bundle_root):
        code = run(["git", "pull", "--ff-only"], bundle_root)
        if code != 0:
            return code

    install_command = ["./install.sh", args.mode, "--client", args.client]
    if args.backup:
        install_command.append("--backup")
    if args.force:
        install_command.append("--force")
    if args.backup_dir:
        install_command.extend(["--backup-dir", args.backup_dir])
    if not args.backup and not args.force:
        install_command.append("--backup")

    return run(install_command, bundle_root)


if __name__ == "__main__":
    raise SystemExit(main())
