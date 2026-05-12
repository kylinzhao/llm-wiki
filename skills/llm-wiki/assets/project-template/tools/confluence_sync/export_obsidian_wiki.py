#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse


EXPORTER_SCRIPT = Path(__file__).with_name("export_confluence_tree.py")
DEFAULT_RSS_MAX_RESULTS = 200


def extract_page_id(page_url: str) -> str:
    parsed = urlparse(page_url)
    page_id = parse_qs(parsed.query).get("pageId", [None])[0]
    if not page_id:
        raise ValueError(f"Could not find pageId in URL: {page_url}")
    return str(page_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a Confluence/wiki page to Obsidian-friendly Markdown."
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Confluence page URL with pageId. Required unless --update reads a saved output directory.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refresh exported pages by polling the saved Confluence RSS/Atom feed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="During --update, detect changed pages and write a report without modifying raw files.",
    )
    parser.add_argument(
        "--init-from-existing",
        action="store_true",
        help="Create update state by scanning an existing flat raw export directory.",
    )
    parser.add_argument(
        "--cookie",
        default=os.environ.get("COOKIE_HEADER", ""),
        help="Raw Cookie header. Falls back to COOKIE_HEADER env var.",
    )
    parser.add_argument(
        "--prompt-cookie",
        action="store_true",
        help="Prompt for the wiki Cookie header with hidden input before running.",
    )
    parser.add_argument(
        "--no-cookie-prompt",
        action="store_true",
        help="Do not prompt interactively when Cookie is missing.",
    )
    parser.add_argument(
        "--open-login",
        action="store_true",
        help="Open https://cwiki.guazi.com before prompting for Cookie.",
    )
    parser.add_argument(
        "--jira-token",
        default=os.environ.get("JIRA_TOKEN", ""),
        help="Optional Jira bearer token. Used to read Jira issue pages and extract linked wiki docs.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--current-only",
        action="store_true",
        help="Export only the current page.",
    )
    mode_group.add_argument(
        "--levels",
        type=int,
        help="Export the page plus N descendant levels. Root is level 0.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory. Defaults to ./wiki-export-<pageId>.",
    )
    parser.add_argument(
        "--project-dir",
        default="",
        help=(
            "Project directory containing raw/. When provided, output dir defaults "
            "to <project-dir>/raw."
        ),
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=1.0,
        help="Seconds to wait between page requests.",
    )
    parser.add_argument(
        "--rss-max-results",
        type=int,
        default=0,
        help=(
            "Maximum number of RSS feed entries to scan during --update. "
            "Default 0 means auto-size from the previous update time."
        ),
    )
    parser.add_argument(
        "--rss-include-new",
        action="store_true",
        help="During --update, also export feed pages that were not already tracked.",
    )
    parser.add_argument(
        "--rss-url",
        action="append",
        default=[],
        help="Override RSS/Atom feed URL.",
    )
    parser.add_argument(
        "--change-report-dir",
        default="",
        help="Directory for update change reports.",
    )
    parser.add_argument(
        "--metadata-dir",
        default="",
        help=(
            "Forwarded to export_confluence_tree.py — overrides default metadata location "
            "(otherwise resolved next to raw/)."
        ),
    )
    return parser.parse_args()


def resolve_depth(args: argparse.Namespace) -> int:
    if args.current_only:
        return 0
    if args.levels is None:
        return 0
    if args.levels < 0:
        raise ValueError("--levels must be >= 0")
    return args.levels


def default_output_dir(page_url: str) -> Path:
    page_id = extract_page_id(page_url)
    return Path.cwd() / f"wiki-export-{page_id}"


def normalize_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def command_needs_cookie(args: argparse.Namespace) -> bool:
    return not getattr(args, "init_from_existing", False)


def print_cookie_instructions() -> None:
    print(
        "\nWiki update needs a valid cwiki Cookie header.\n"
        "\n"
        "How to get it:\n"
        "1. Open https://cwiki.guazi.com in your normal browser and make sure you are logged in.\n"
        "2. Open DevTools -> Network, then refresh any cwiki page.\n"
        "3. Click a cwiki request, find Request Headers -> Cookie, and copy the full value.\n"
        "4. Paste it below. Input is hidden and is only passed to this run; it is not written to files.\n",
        file=sys.stderr,
    )


def maybe_prompt_for_cookie(args: argparse.Namespace) -> str:
    cookie = str(getattr(args, "cookie", "") or "").strip()
    if cookie:
        return cookie
    if not command_needs_cookie(args):
        return ""
    if getattr(args, "no_cookie_prompt", False):
        return ""
    if not getattr(args, "prompt_cookie", False) and not (sys.stdin.isatty() and sys.stderr.isatty()):
        return ""
    if getattr(args, "open_login", False):
        webbrowser.open("https://cwiki.guazi.com")
    print_cookie_instructions()
    return getpass.getpass("Paste cwiki Cookie header: ").strip()


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    project_dir_text = getattr(args, "project_dir", "").strip()
    if project_dir_text:
        project_dir = Path(project_dir_text).expanduser().resolve()
        return project_dir / "raw"
    cwd_raw_dir = Path.cwd() / "raw"
    if (getattr(args, "update", False) or getattr(args, "init_from_existing", False)) and cwd_raw_dir.exists():
        return cwd_raw_dir.resolve()
    urls = normalize_values(getattr(args, "url", []))
    if urls:
        return default_output_dir(urls[0])
    raise ValueError("--output-dir is required when --update is used without --url")


def build_command(args: argparse.Namespace) -> list[str]:
    depth = resolve_depth(args)
    output_dir = resolve_output_dir(args)
    urls = normalize_values(getattr(args, "url", []))
    rss_urls = normalize_values(getattr(args, "rss_url", []))
    command = [
        sys.executable,
        str(EXPORTER_SCRIPT),
        "--depth",
        str(depth),
        "--output-dir",
        str(output_dir),
        "--request-interval",
        str(args.request_interval),
    ]
    for url in urls:
        command.extend(["--url", url])
    if args.update:
        command.append("--update")
    if getattr(args, "dry_run", False):
        command.append("--dry-run")
    if getattr(args, "init_from_existing", False):
        command.append("--init-from-existing")
    if args.rss_max_results:
        command.extend(["--rss-max-results", str(args.rss_max_results)])
    if args.rss_include_new:
        command.append("--rss-include-new")
    for rss_url in rss_urls:
        command.extend(["--rss-url", rss_url])
    if getattr(args, "change_report_dir", "").strip():
        command.extend(["--change-report-dir", args.change_report_dir.strip()])
    if getattr(args, "metadata_dir", "").strip():
        command.extend(["--metadata-dir", args.metadata_dir.strip()])
    if args.jira_token.strip():
        command.extend(["--jira-token", args.jira_token.strip()])
    return command


def main() -> int:
    args = parse_args()
    if not EXPORTER_SCRIPT.exists():
        raise SystemExit(f"Exporter script not found: {EXPORTER_SCRIPT}")
    command = build_command(args)
    env = os.environ.copy()
    cookie = maybe_prompt_for_cookie(args)
    if cookie:
        env["COOKIE_HEADER"] = cookie
    raise SystemExit(subprocess.call(command, env=env))


if __name__ == "__main__":
    main()
