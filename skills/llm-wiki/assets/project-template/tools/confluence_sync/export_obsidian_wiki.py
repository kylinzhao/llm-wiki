#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import shlex
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qs, urlparse


EXPORTER_SCRIPT = Path(__file__).with_name("export_confluence_tree.py")
DEFAULT_RSS_MAX_RESULTS = 200
AUTH_ENV_FILE = Path(os.environ.get("LLM_WIKI_AUTH_ENV_FILE", "~/.llm-wiki/guazi-sso.env")).expanduser()
SSO_ENV_KEYS = (
    "GUAZI_SSO_SKILL_ROOT",
    "GUAZI_SSO_USER_NAME",
    "GUAZI_SSO_PASSWORD",
    "GUAZI_SSO_APPLY_PHONE",
)
AUTH_ENV_KEYS = SSO_ENV_KEYS + ("JIRA_TOKEN",)
SSO_SKILL_CANDIDATES = (
    str(Path(__file__).with_name("guazi-sso-login")),
    "~/.codex/skills/guazi-sso-login",
    "~/.codex/skills/guazi-sso",
    "~/.claude/skills/guazi-sso-login",
    "~/.claude/skills/guazi-sso",
    "~/.cursor/skills/guazi-sso-login",
    "~/.cursor/skills/guazi-sso",
)


def extract_page_id(page_url: str) -> str:
    parsed = urlparse(page_url)
    page_id = parse_qs(parsed.query).get("pageId", [None])[0]
    if not page_id:
        raise ValueError(f"Could not find pageId in URL: {page_url}")
    return str(page_id)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
        "--sso-skill-root",
        default=os.environ.get("GUAZI_SSO_SKILL_ROOT", ""),
        help="Path to guazi-sso-login skill root (directory containing run.sh).",
    )
    parser.add_argument(
        "--auto-cookie-from-sso",
        action="store_true",
        help="When cookie is missing, call guazi-sso-login wiki --validate --plain automatically.",
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
    parser.add_argument(
        "--jira-cookie",
        default=os.environ.get("JIRA_COOKIE", ""),
        help="Optional Jira Cookie header for Jira API requests.",
    )
    parser.add_argument(
        "--jira-chdsso",
        default=os.environ.get("JIRA_CHDSSO", ""),
        help="Optional CHDSSO token used as `chdsso` header for Jira API requests.",
    )
    parser.add_argument(
        "--auto-jira-chdsso-from-sso",
        action="store_true",
        help="When jira-chdsso is missing, call guazi-sso-login chdsso --validate --plain automatically.",
    )
    parser.add_argument(
        "--jira-chdsso-env",
        choices=("test", "pre", "online"),
        default=os.environ.get("JIRA_CHDSSO_ENV", "test"),
        help="Target env for auto-fetched Jira CHDSSO token. Default: test.",
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
            "(otherwise defaults to staging/wiki-export-state for project raw/ exports)."
        ),
    )
    parser.add_argument(
        "--updated-since",
        default="",
        help=(
            "Only persist pages whose updated_at/created_at is on or after this time "
            "(YYYY-MM-DD or ISO-8601 datetime)."
        ),
    )
    return parser.parse_args(argv)


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


def print_auth_instructions() -> None:
    print(
        "\nCwiki sync needs authentication.\n"
        "\n"
        "Security boundary:\n"
        "- The llm-wiki skill does not upload your username, password, phone, Jira token, Cookie, or token.\n"
        "- It does not write secrets into the KB project. When you choose persistent SSO, values are written only to your computer.\n"
        "- The local env file is ~/.llm-wiki/guazi-sso.env with user-only permissions, and is loaded by future llm-wiki updates.\n"
        "- guazi-sso-login exchanges the SSO credentials for a Cookie/login cache locally and reuses it until it expires.\n"
        "- Secrets are not written to raw/, wiki/, upstream/, staging reports, command arguments, or git files by this skill.\n"
        "- If you type secrets in the agent chat window, they may enter the current agent session context or local session history depending on the engine.\n"
        "\n"
        "Recommended terminal setup: run `bash tools/confluence_sync/init_auth_env.sh` from the KB project root, then return and continue update.\n"
        "\n"
        "If the project template is not installed yet, run the skill-level script instead: `bash ${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/init_auth_env.sh`.\n"
        "\n"
        "The Cwiki login helper is bundled with llm-wiki. Jira issue reading prefers JIRA_TOKEN; CHDSSO is only a fallback. A full COOKIE_HEADER is only a one-off fallback, not the recommended path.\n",
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


def shell_quote_env_value(value: str) -> str:
    return shlex.quote(value)


def load_auth_env_file(path: Path = AUTH_ENV_FILE) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in AUTH_ENV_KEYS:
            try:
                parsed = shlex.split(value, posix=True)
                values[key] = parsed[0] if parsed else ""
            except ValueError:
                values[key] = value.strip().strip("'\"")
    return {key: value for key, value in values.items() if value}


def discover_sso_skill_root(env: dict[str, str] | None = None) -> str:
    env = env or os.environ
    for value in [env.get("GUAZI_SSO_SKILL_ROOT", ""), load_auth_env_file().get("GUAZI_SSO_SKILL_ROOT", "")]:
        if value and (Path(value).expanduser() / "run.sh").is_file():
            return str(Path(value).expanduser())
    for candidate in SSO_SKILL_CANDIDATES:
        root = Path(candidate).expanduser()
        if (root / "run.sh").is_file():
            return str(root)
    return ""


def write_auth_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    lines = [
        "# Local llm-wiki SSO credentials. Do not commit.",
        "# Used by tools/confluence_sync/export_obsidian_wiki.py.",
    ]
    for key in AUTH_ENV_KEYS:
        value = values.get(key, "")
        if value:
            lines.append(f"{key}={shell_quote_env_value(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def apply_auth_env_defaults(args: argparse.Namespace, env: dict[str, str]) -> None:
    if not str(getattr(args, "sso_skill_root", "") or "").strip() and env.get("GUAZI_SSO_SKILL_ROOT"):
        args.sso_skill_root = env["GUAZI_SSO_SKILL_ROOT"]
    if not str(getattr(args, "sso_skill_root", "") or "").strip():
        discovered = discover_sso_skill_root(env)
        if discovered:
            args.sso_skill_root = discovered
            env["GUAZI_SSO_SKILL_ROOT"] = discovered
    if all(env.get(key) for key in SSO_ENV_KEYS):
        args.auto_cookie_from_sso = True
    if not str(getattr(args, "jira_token", "") or "").strip() and env.get("JIRA_TOKEN"):
        args.jira_token = env["JIRA_TOKEN"]


def maybe_prompt_for_auth(args: argparse.Namespace) -> dict[str, str]:
    if str(getattr(args, "cookie", "") or "").strip():
        return {}
    if getattr(args, "auto_cookie_from_sso", False):
        return {}
    if not command_needs_cookie(args):
        return {}
    if getattr(args, "no_cookie_prompt", False):
        return {}
    interactive = sys.stdin.isatty() and sys.stderr.isatty()
    if not getattr(args, "prompt_cookie", False) and not interactive:
        print_auth_instructions()
        return {}
    if getattr(args, "open_login", False):
        webbrowser.open("https://cwiki.guazi.com")
    print_auth_instructions()
    mode = input("Choose auth mode [sso/cookie] (default: sso): ").strip().lower() or "sso"
    if mode == "cookie":
        cookie = getpass.getpass("Paste full COOKIE_HEADER: ").strip()
        if cookie:
            return {"COOKIE_HEADER": cookie}
        return {}
    sso_skill_root = str(getattr(args, "sso_skill_root", "") or "").strip() or discover_sso_skill_root()
    if not sso_skill_root:
        print(
            "没有找到内置 guazi-sso-login 登录工具。这是 llm-wiki 安装不完整，请先更新 llm-wiki skill 或同步项目 tools。",
            file=sys.stderr,
        )
        return {}
    user_name = input("请输入瓜子用户名: ").strip()
    password = getpass.getpass("请输入瓜子密码（输入时不会显示）: ").strip()
    apply_phone = input("请输入手机号: ").strip()
    jira_token = getpass.getpass("请输入 Jira 令牌（输入时不会显示，没有可直接回车）: ").strip()
    if not user_name or not password or not apply_phone:
        return {}
    args.sso_skill_root = sso_skill_root
    args.auto_cookie_from_sso = True
    if jira_token:
        args.jira_token = jira_token
    values = {
        "GUAZI_SSO_SKILL_ROOT": sso_skill_root,
        "GUAZI_SSO_USER_NAME": user_name,
        "GUAZI_SSO_PASSWORD": password,
        "GUAZI_SSO_APPLY_PHONE": apply_phone,
        "JIRA_TOKEN": jira_token,
    }
    write_auth_env_file(AUTH_ENV_FILE, values)
    return values


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
    if getattr(args, "sso_skill_root", "").strip():
        command.extend(["--sso-skill-root", args.sso_skill_root.strip()])
    if getattr(args, "auto_cookie_from_sso", False):
        command.append("--auto-cookie-from-sso")
    if getattr(args, "updated_since", "").strip():
        command.extend(["--updated-since", args.updated_since.strip()])
    if args.jira_token.strip():
        # Passed through the child environment instead of argv so tokens do not appear in process lists.
        pass
    if getattr(args, "jira_cookie", "").strip():
        command.extend(["--jira-cookie", args.jira_cookie.strip()])
    if getattr(args, "jira_chdsso", "").strip():
        command.extend(["--jira-chdsso", args.jira_chdsso.strip()])
    if getattr(args, "auto_jira_chdsso_from_sso", False):
        command.append("--auto-jira-chdsso-from-sso")
    if getattr(args, "jira_chdsso_env", "").strip():
        command.extend(["--jira-chdsso-env", args.jira_chdsso_env.strip()])
    return command


def main() -> int:
    args = parse_args()
    if not EXPORTER_SCRIPT.exists():
        raise SystemExit(f"Exporter script not found: {EXPORTER_SCRIPT}")
    env = os.environ.copy()
    env.update(load_auth_env_file())
    apply_auth_env_defaults(args, env)
    env.update(maybe_prompt_for_auth(args))
    if str(getattr(args, "jira_token", "") or "").strip():
        env["JIRA_TOKEN"] = args.jira_token.strip()
    command = build_command(args)
    raise SystemExit(subprocess.call(command, env=env))


if __name__ == "__main__":
    main()
