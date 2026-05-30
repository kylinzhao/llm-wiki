#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import hashlib
import json
import os
import random
import re
import shlex
import subprocess
import sys
import time
import zipfile
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drawio_diagram import drawio_to_mermaid


DEFAULT_DEPTH = 3
DEFAULT_RSS_MAX_RESULTS = 200
AUTO_RSS_MIN_RESULTS = 50
AUTO_RSS_RESULTS_PER_DAY = 50
AUTO_RSS_MAX_RESULTS = 200
USER_AGENT = "Codex-Confluence-Markdown-Exporter/1.0"
RATE_LIMIT_RETRIES = 5
RATE_LIMIT_BACKOFF_SECONDS = 3.0
REQUEST_INTERVAL_SECONDS = 1.0
ASSET_REQUEST_INTERVAL_SECONDS = 0.0
BLOCK_TAGS = {
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}


class FetchError(RuntimeError):
    def __init__(self, status_code: int, url: str, body: str):
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"Request failed with {status_code} for {url}: {body[:300]}")


class WikiAuthenticationError(RuntimeError):
    pass


AUTH_ENV_FILE = Path(os.environ.get("LLM_WIKI_AUTH_ENV_FILE", "~/.llm-wiki/guazi-sso.env")).expanduser()
SSO_ENV_KEYS = (
    "GUAZI_SSO_USER_NAME",
    "GUAZI_SSO_PASSWORD",
    "GUAZI_SSO_APPLY_PHONE",
)
AUTH_ENV_KEYS = SSO_ENV_KEYS + ("COOKIE_HEADER",)
SSO_SKILL_CANDIDATES = (
    str(Path(__file__).with_name("guazi-sso-login")),
    "~/.codex/skills/guazi-sso-login",
    "~/.claude/skills/guazi-sso-login",
    "~/.cursor/skills/guazi-sso-login",
)


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


def discover_sso_skill_root() -> str:
    for candidate in SSO_SKILL_CANDIDATES:
        root = Path(candidate).expanduser()
        if (root / "run.sh").is_file():
            return str(root)
    return ""


def cookie_refresh_help(reason: str) -> str:
    return "\n".join(
        [
            reason,
            "",
            "Wiki authentication needs a valid local login state.",
            "Supported auth setup paths:",
            "1. SSO mode: provide Guazi username, password, and phone so the bundled login helper can cache a local Cwiki login state.",
            "2. Cookie mode: paste a full COOKIE_HEADER into ~/.llm-wiki/guazi-sso.env when the SSO token service is unreachable, for example outside non-intranet/VPN access.",
            "The llm-wiki skill does not upload credentials or write them into the KB project; persistent auth values live only on this computer in ~/.llm-wiki/guazi-sso.env.",
            "",
            "Terminal setup: run `bash tools/confluence_sync/init_auth_env.sh` from the KB project root, choose SSO or Cookie mode, then retry the sync.",
            "If the project template is not installed yet, run `bash ${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki/scripts/init_auth_env.sh`.",
            "",
            "Do not commit credentials or paste them into project files.",
        ]
    )


def run_guazi_sso_skill(
    skill_root: str,
    subcommand: str,
    *,
    extra_args: list[str] | None = None,
) -> str:
    root = Path(skill_root).expanduser().resolve()
    run_sh = root / "run.sh"
    if not run_sh.is_file():
        raise RuntimeError(f"guazi-sso-login run.sh not found: {run_sh}")
    command = ["bash", str(run_sh), subcommand]
    if extra_args:
        command.extend(extra_args)
    env = os.environ.copy()
    for key, value in load_auth_env_file().items():
        env.setdefault(key, value)
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit={result.returncode}"
        raise RuntimeError(f"guazi-sso-login {subcommand} failed: {detail}")
    output = (result.stdout or "").strip()
    if not output:
        raise RuntimeError(f"guazi-sso-login {subcommand} returned empty output.")
    return output


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def sso_env_setup_help() -> str:
    return "\n".join(
        [
            "To enable auto-login, run `bash tools/confluence_sync/init_auth_env.sh` and choose SSO or Cookie mode.",
            "SSO mode can also be set by exporting credentials in the current environment:",
            "Optional for Jira CHDSSO auto-refresh:",
            "  export GUAZI_CHDSSO_TEST_PHONE='<phone>'",
            "  export GUAZI_CHDSSO_TEST_CODE='<code>'",
            "  # or PRE/ONLINE variants:",
            "  export GUAZI_CHDSSO_PRE_PHONE='...'; export GUAZI_CHDSSO_PRE_CODE='...'",
            "  export GUAZI_CHDSSO_ONLINE_PHONE='...'; export GUAZI_CHDSSO_ONLINE_CODE='...'",
            "Cookie mode can be set globally in ~/.llm-wiki/guazi-sso.env as COOKIE_HEADER='<full cookie header>'.",
        ]
    )


@dataclass
class PageNode:
    page_id: str
    title: str
    url: str
    depth: int
    html: str
    storage_html: str = ""
    author: str = ""
    last_editor: str = ""
    created_at: str = ""
    updated_at: str = ""
    version_number: int = 0
    children: list["PageNode"] = field(default_factory=list)


@dataclass(frozen=True)
class RootSpec:
    page_id: str
    url: str
    site_base: str
    depth_limit: int
    weekly_from_title: str = ""


@dataclass(frozen=True)
class FeedEntry:
    page_id: str
    title: str
    url: str
    updated_at: str
    published_at: str = ""
    version_number: Optional[int] = None


@dataclass(frozen=True)
class UpdateResult:
    root_page_id: str
    scanned_count: int
    updated_page_ids: list[str]
    skipped_page_ids: list[str]
    ignored_page_ids: list[str]
    change_records: list[dict[str, Any]] = field(default_factory=list)
    change_report_path: str = ""
    dry_run: bool = False


WEEKLY_TITLE_RE = re.compile(r"^(?P<prefix>.+?)(?P<year>\d{4})M(?P<month>\d{1,2})W(?P<week>\d{1,2})$")
JIRA_BROWSE_PATH_RE = re.compile(r"^(?P<prefix>.*?)/browse/(?P<issue>[A-Z][A-Z0-9_]+-\d+)$")
FEED_ENTRY_ID_RE = re.compile(r"page-(?P<page_id>\d+)-(?P<version>\d+)")
ATOM_NS = "{http://www.w3.org/2005/Atom}"
EXPORT_STATE_VERSION = 1


def page_node_to_dict(page: PageNode) -> dict[str, Any]:
    return {
        "page_id": page.page_id,
        "title": page.title,
        "url": page.url,
        "depth": page.depth,
        "html": page.html,
        "author": page.author,
        "last_editor": page.last_editor,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
        "version_number": page.version_number,
    }


def page_node_from_dict(data: dict[str, Any]) -> PageNode:
    return PageNode(
        page_id=str(data["page_id"]),
        title=data.get("title", ""),
        url=data.get("url", ""),
        depth=int(data.get("depth", 0)),
        html=data.get("html", ""),
        author=data.get("author", ""),
        last_editor=data.get("last_editor", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        version_number=int(data.get("version_number", 0) or 0),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a Confluence page tree to local Markdown files."
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Confluence page URL with pageId. Repeat to export multiple roots.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refresh previously exported pages by polling the saved RSS/Atom feed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="During --update, detect changed pages and write a report without modifying raw files.",
    )
    parser.add_argument(
        "--init-from-existing",
        action="store_true",
        help=(
            "Scan an existing flat raw export directory and create export-state/progress "
            "metadata for future --update runs."
        ),
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
        "--output-dir",
        default="confluence-export",
        help="Directory to write Markdown files into.",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help="Maximum descendant depth to export. Root is depth 0.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=REQUEST_INTERVAL_SECONDS,
        help="Seconds to wait between requests.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of pages to fetch in this export run.",
    )
    parser.add_argument(
        "--weekly-from",
        action="append",
        default=[],
        help=(
            "Filter direct child weekly report pages for a root page. "
            "Format: <rootPageId>=<title>, for example "
            "336124238=商家服务周报2025M10W2"
        ),
    )
    parser.add_argument(
        "--depth-for",
        action="append",
        default=[],
        help=(
            "Override crawl depth for a specific root page. "
            "Format: <rootPageId>=<depth>, for example 336124238=3"
        ),
    )
    parser.add_argument(
        "--jira-token",
        default=os.environ.get("JIRA_TOKEN", ""),
        help="Optional Jira bearer token used to resolve wiki links from Jira issue pages.",
    )
    parser.add_argument(
        "--jira-cookie",
        default=os.environ.get("JIRA_COOKIE", ""),
        help="Optional Jira Cookie header used to resolve wiki links from Jira issue pages.",
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
        help=(
            "Override RSS/Atom feed URL. Repeat for multiple roots, or use "
            "<rootPageId>=<url>."
        ),
    )
    parser.add_argument(
        "--change-report-dir",
        default="",
        help=(
            "Directory for durable update reports. Defaults to ../staging/wiki-sync "
            "when --output-dir is named raw, otherwise <output-dir>/update-reports."
        ),
    )
    parser.add_argument(
        "--metadata-dir",
        default="",
        help=(
            "Directory for export-state.json, progress/*.json, and manifest-*.json. "
            "When omitted and --output-dir ends with raw/, defaults to <project>/staging/wiki-export-state."
        ),
    )
    parser.add_argument(
        "--updated-since",
        default="",
        help=(
            "Only persist pages whose updated_at/created_at is on or after this time "
            "(ISO-8601, for example 2026-01-01 or 2026-01-01T00:00:00+08:00)."
        ),
    )
    return parser.parse_args()


def extract_page_id(page_url: str) -> str:
    parsed = urlparse(page_url)
    page_id = parse_qs(parsed.query).get("pageId", [None])[0]
    if not page_id:
        raise ValueError(f"Could not find pageId in URL: {page_url}")
    return page_id


def derive_site_base(page_url: str) -> str:
    parsed = urlparse(page_url)
    match = re.match(r"^(.*?)/pages/viewpage\.action$", parsed.path)
    if not match:
        raise ValueError(
            "Unsupported Confluence page URL format. Expected path ending with /pages/viewpage.action"
        )
    base_path = match.group(1)
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


def parse_page_value_args(entries: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for entry in entries:
        page_id, separator, value = entry.partition("=")
        if not separator or not page_id.strip() or not value.strip():
            raise ValueError(
                f"Invalid page-scoped argument '{entry}'. Expected format <pageId>=<value>."
            )
        parsed[page_id.strip()] = value.strip()
    return parsed


def parse_page_int_args(entries: list[str]) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for page_id, value in parse_page_value_args(entries).items():
        try:
            parsed[page_id] = int(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid integer value '{value}' for page-scoped argument '{page_id}'."
            ) from exc
    return parsed


def build_root_specs(
    page_urls: list[str],
    weekly_from_map: dict[str, str],
    depth_map: dict[str, int],
    default_depth: int,
) -> list[RootSpec]:
    root_specs: list[RootSpec] = []
    seen: set[str] = set()
    for page_url in page_urls:
        page_id = extract_page_id(page_url)
        if page_id in seen:
            continue
        seen.add(page_id)
        root_specs.append(
            RootSpec(
                page_id=page_id,
                url=page_url,
                site_base=derive_site_base(page_url),
                depth_limit=depth_map.get(page_id, default_depth),
                weekly_from_title=weekly_from_map.get(page_id, ""),
            )
        )
    return root_specs


def parse_weekly_title(title: str) -> Optional[tuple[str, int, int, int]]:
    match = WEEKLY_TITLE_RE.match(title.strip())
    if not match:
        return None
    return (
        match.group("prefix"),
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("week")),
    )


def build_depth_one_child_filter(
    weekly_from_title: str,
) -> Optional[Callable[[dict[str, Any]], bool]]:
    if not weekly_from_title:
        return None
    threshold = parse_weekly_title(weekly_from_title)
    if threshold is None:
        raise ValueError(f"Unsupported weekly title format: {weekly_from_title}")
    threshold_prefix = threshold[0]
    threshold_date = threshold[1:]

    def include_child(child_payload: dict[str, Any]) -> bool:
        child_title = str(child_payload.get("title", "")).strip()
        parsed_title = parse_weekly_title(child_title)
        if parsed_title is None:
            return False
        return parsed_title[0] == threshold_prefix and parsed_title[1:] >= threshold_date

    return include_child


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\- ]+", "", value, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s\-]+", "-", slug)
    return slug or "untitled"


def resolve_cookie_header(
    cookie_header: str,
    *,
    sso_skill_root: str,
    auto_cookie_from_sso: bool,
) -> str:
    cookie = cookie_header.strip()
    if cookie:
        return cookie
    sso_skill_root = sso_skill_root.strip() or discover_sso_skill_root()
    if sso_skill_root:
        try:
            return run_guazi_sso_skill(
                sso_skill_root,
                "wiki",
                extra_args=["--validate", "--plain"],
            )
        except RuntimeError as exc:
            message = str(exc)
            if "E_MISSING_CREDENTIALS" in message:
                raise RuntimeError(message + "\n\n" + sso_env_setup_help()) from exc
            raise
    return ""


def resolve_jira_chdsso(
    jira_chdsso: str,
    *,
    sso_skill_root: str,
    auto_jira_chdsso_from_sso: bool,
    jira_chdsso_env: str,
) -> str:
    token = jira_chdsso.strip()
    if token:
        return token
    if auto_jira_chdsso_from_sso and sso_skill_root.strip():
        try:
            return run_guazi_sso_skill(
                sso_skill_root,
                "chdsso",
                extra_args=["--env", jira_chdsso_env, "--validate", "--plain"],
            )
        except RuntimeError as exc:
            message = str(exc)
            if "E_MISSING_CREDENTIALS" in message:
                raise RuntimeError(message + "\n\n" + sso_env_setup_help()) from exc
            raise
    return ""


def build_session(cookie_header: str, timeout: int) -> requests.Session:
    if not cookie_header.strip():
        raise WikiAuthenticationError(
            cookie_refresh_help("Missing wiki Cookie header. Pass --cookie or set COOKIE_HEADER.")
        )
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "Cookie": cookie_header.strip(),
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
    )
    session.request_timeout = timeout
    session.rate_limit_retries = RATE_LIMIT_RETRIES
    session.rate_limit_backoff = RATE_LIMIT_BACKOFF_SECONDS
    session.request_interval = REQUEST_INTERVAL_SECONDS
    session.asset_request_interval = ASSET_REQUEST_INTERVAL_SECONDS
    session.last_request_at = None
    session.jira_token = ""
    session.jira_issue_cache = {}
    return session


def send_request(
    session: requests.Session,
    url: str,
    *,
    stream: bool = False,
    accept: str = "application/json",
    request_interval_override: Optional[float] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> requests.Response:
    retries = getattr(session, "rate_limit_retries", RATE_LIMIT_RETRIES)
    backoff = float(getattr(session, "rate_limit_backoff", RATE_LIMIT_BACKOFF_SECONDS))
    for attempt in range(retries + 1):
        if request_interval_override is None:
            request_interval = float(getattr(session, "request_interval", REQUEST_INTERVAL_SECONDS))
        else:
            request_interval = float(request_interval_override)
        last_request_at = getattr(session, "last_request_at", None)
        if last_request_at is not None and request_interval > 0:
            elapsed = time.monotonic() - last_request_at
            if elapsed < request_interval:
                time.sleep(request_interval - elapsed)
        headers = {"Accept": accept} if accept else {}
        if extra_headers:
            headers.update(extra_headers)
        if not headers:
            headers = None
        response = session.get(url, timeout=session.request_timeout, stream=stream, headers=headers)
        session.last_request_at = time.monotonic()
        if response.status_code == 429 and attempt < retries:
            retry_after = response.headers.get("Retry-After", "").strip()
            delay = backoff * (2**attempt)
            if retry_after:
                try:
                    delay = max(float(retry_after), 0.0)
                except ValueError:
                    pass
            time.sleep(delay)
            continue
        return response
    raise RuntimeError(f"Exceeded retry budget for {url}")


def fetch_json(session: requests.Session, url: str) -> dict:
    response = send_request(session, url)
    if response.status_code >= 400:
        raise FetchError(response.status_code, url, response.text)
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}") from exc


def fetch_json_with_headers(
    session: requests.Session,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    request_interval_override: Optional[float] = None,
) -> dict:
    response = send_request(
        session,
        url,
        accept="application/json",
        request_interval_override=request_interval_override,
        extra_headers=headers,
    )
    if response.status_code >= 400:
        raise FetchError(response.status_code, url, response.text)
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}") from exc


def content_endpoint(site_base: str, page_id: str) -> str:
    return f"{site_base}/rest/api/content/{quote(page_id)}?expand=body.view,body.storage,history,version"


def attachments_endpoint(site_base: str, page_id: str, filename: str = "") -> str:
    query = "limit=100"
    if filename:
        query += f"&filename={quote(filename)}"
    return f"{site_base}/rest/api/content/{quote(page_id)}/child/attachment?{query}"


def space_endpoint(site_base: str, page_id: str) -> str:
    return f"{site_base}/rest/api/content/{quote(page_id)}?expand=space"


def children_endpoint(site_base: str, page_id: str, start: int = 0, limit: int = 100) -> str:
    return (
        f"{site_base}/rest/api/content/{quote(page_id)}/child/page"
        f"?limit={limit}&start={start}"
    )


def page_url_from_api(site_base: str, page_id: str) -> str:
    return f"{site_base}/pages/viewpage.action?pageId={quote(page_id)}"


def page_from_payload(site_base: str, payload: dict, depth: int) -> PageNode:
    page_id = str(payload["id"])
    title = payload["title"]
    body = payload.get("body", {}).get("view", {}).get("value", "")
    storage_body = payload.get("body", {}).get("storage", {}).get("value", "")
    history = payload.get("history") or {}
    version = payload.get("version") or {}
    created_by = history.get("createdBy") or {}
    updated_by = version.get("by") or {}
    return PageNode(
        page_id=page_id,
        title=title,
        url=page_url_from_api(site_base, page_id),
        depth=depth,
        html=body,
        storage_html=storage_body,
        author=created_by.get("displayName", ""),
        last_editor=updated_by.get("displayName", ""),
        created_at=history.get("createdDate", ""),
        updated_at=version.get("when", ""),
        version_number=version.get("number", 0) or 0,
    )


def fetch_page(session: requests.Session, site_base: str, page_id: str, depth: int) -> PageNode:
    payload = fetch_json(session, content_endpoint(site_base, page_id))
    return page_from_payload(site_base, payload, depth)


def fetch_page_space_key(session: requests.Session, site_base: str, page_id: str) -> str:
    payload = fetch_json(session, space_endpoint(site_base, page_id))
    space = payload.get("space") or {}
    return str(space.get("key") or "")


def fetch_children(session: requests.Session, site_base: str, page_id: str) -> list[dict]:
    children: list[dict] = []
    start = 0
    limit = 100
    while True:
        payload = fetch_json(session, children_endpoint(site_base, page_id, start=start, limit=limit))
        batch = payload.get("results", [])
        children.extend(batch)
        if payload.get("_links", {}).get("next"):
            start += limit
            continue
        break
    return children


def build_rss_feed_url(site_base: str, space_key: str, max_results: int = 100) -> str:
    query = urlencode(
        {
            "types": "page",
            "spaces": space_key,
            "maxResults": str(max_results),
            "publicFeed": "false",
            "os_authType": "basic",
            "showContent": "false",
        }
    )
    return f"{site_base}/spaces/createrssfeed.action?{query}"


def normalize_user_url(url: str) -> str:
    return html_lib.unescape(url.strip())


def update_rss_url_max_results(rss_url: str, max_results: int) -> str:
    normalized = normalize_user_url(rss_url)
    parsed = urlparse(normalized)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    updated_pairs: list[tuple[str, str]] = []
    replaced = False
    for key, value in query_pairs:
        if key == "maxResults":
            updated_pairs.append((key, str(max_results)))
            replaced = True
        else:
            updated_pairs.append((key, value))
    if not replaced:
        updated_pairs.append(("maxResults", str(max_results)))
    return urlunparse(parsed._replace(query=urlencode(updated_pairs)))


def parse_atom_feed_entries(xml_text: str) -> list[FeedEntry]:
    root = ElementTree.fromstring(xml_text)
    entries: list[FeedEntry] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        entry_id = (entry.findtext(f"{ATOM_NS}id") or "").strip()
        updated_at = (entry.findtext(f"{ATOM_NS}updated") or "").strip()
        published_at = (entry.findtext(f"{ATOM_NS}published") or "").strip()
        link_url = ""
        for link in entry.findall(f"{ATOM_NS}link"):
            href = str(link.attrib.get("href") or "").strip()
            if not href:
                continue
            rel = str(link.attrib.get("rel") or "alternate").strip()
            if rel == "alternate":
                link_url = href
                break
            if not link_url:
                link_url = href

        id_match = FEED_ENTRY_ID_RE.search(entry_id)
        page_id = parse_qs(urlparse(link_url).query).get("pageId", [None])[0]
        if not page_id and id_match:
            page_id = id_match.group("page_id")
        if not page_id:
            continue
        version_number = int(id_match.group("version")) if id_match else None
        entries.append(
            FeedEntry(
                page_id=str(page_id),
                title=title,
                url=link_url,
                updated_at=updated_at,
                published_at=published_at,
                version_number=version_number,
            )
        )
    return entries


def fetch_rss_entries(session: requests.Session, rss_url: str) -> list[FeedEntry]:
    rss_url = normalize_user_url(rss_url)
    response = send_request(
        session,
        rss_url,
        accept="application/atom+xml, application/xml, text/xml, */*",
    )
    if response.status_code in {401, 403}:
        raise WikiAuthenticationError(
            cookie_refresh_help(
                f"Wiki RSS returned HTTP {response.status_code}; the cookie is missing or expired."
            )
        )
    if response.status_code >= 400:
        raise FetchError(response.status_code, rss_url, response.text)
    try:
        return parse_atom_feed_entries(response.text)
    except ElementTree.ParseError as exc:
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type.lower() or "<html" in response.text[:500].lower():
            raise WikiAuthenticationError(
                cookie_refresh_help(
                    "Wiki RSS returned an HTML page instead of Atom XML; the cookie is likely expired."
                )
            ) from exc
        raise


def extract_linked_page_ids(html: str, page_url: str, site_base: str) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    site_host = urlparse(site_base).netloc
    page_ids: set[str] = set()
    for anchor in soup.find_all("a"):
        resource_type = anchor.get("data-linked-resource-type", "").strip().lower()
        data_linked_resource_id = anchor.get("data-linked-resource-id", "").strip()
        if data_linked_resource_id.isdigit() and resource_type in {"", "page"}:
            page_ids.add(data_linked_resource_id)
            continue
        href = anchor.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc and parsed.netloc != site_host:
            continue
        linked_page_id = parse_qs(parsed.query).get("pageId", [None])[0]
        if linked_page_id:
            page_ids.add(str(linked_page_id))
    return page_ids


def extract_jira_issue_urls(html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    issue_urls: set[str] = set()
    for anchor in soup.find_all("a"):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if JIRA_BROWSE_PATH_RE.match(parsed.path):
            issue_urls.add(absolute)
    return issue_urls


def parse_jira_issue_url(issue_url: str) -> Optional[tuple[str, str]]:
    parsed = urlparse(issue_url)
    match = JIRA_BROWSE_PATH_RE.match(parsed.path)
    if not match:
        return None
    prefix = match.group("prefix")
    issue_key = match.group("issue")
    site_base = f"{parsed.scheme}://{parsed.netloc}{prefix}"
    return site_base.rstrip("/"), issue_key


def extract_confluence_page_ids_from_text(text: str, site_base: str) -> set[str]:
    page_ids: set[str] = set()
    site_host = urlparse(site_base).netloc
    for match in re.finditer(r"https?://[^\s\"'<>]+", text or ""):
        absolute = match.group(0).rstrip(").,]")
        parsed = urlparse(absolute)
        if parsed.netloc != site_host:
            continue
        linked_page_id = parse_qs(parsed.query).get("pageId", [None])[0]
        if linked_page_id:
            page_ids.add(str(linked_page_id))
    return page_ids


def extract_confluence_page_ids_from_value(value: Any, site_base: str) -> set[str]:
    page_ids: set[str] = set()
    if isinstance(value, str):
        page_ids.update(extract_confluence_page_ids_from_text(value, site_base))
        return page_ids
    if isinstance(value, dict):
        for nested_value in value.values():
            page_ids.update(extract_confluence_page_ids_from_value(nested_value, site_base))
        return page_ids
    if isinstance(value, list):
        for item in value:
            page_ids.update(extract_confluence_page_ids_from_value(item, site_base))
        return page_ids
    return page_ids


def fetch_jira_linked_page_ids(
    session: requests.Session,
    html: str,
    page_url: str,
    site_base: str,
) -> set[str]:
    jira_token = getattr(session, "jira_token", "").strip()
    jira_chdsso = getattr(session, "jira_chdsso", "").strip()
    jira_cookie = getattr(session, "jira_cookie", "").strip()
    if not jira_token and not jira_chdsso and not jira_cookie:
        return set()

    issue_cache: dict[str, set[str]] = getattr(session, "jira_issue_cache", {})
    linked_page_ids: set[str] = set()
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if jira_token:
        headers["Authorization"] = f"Bearer {jira_token}"
    if jira_chdsso:
        headers["chdsso"] = jira_chdsso
    if jira_cookie:
        headers["Cookie"] = jira_cookie

    for issue_url in extract_jira_issue_urls(html, page_url):
        if issue_url in issue_cache:
            linked_page_ids.update(issue_cache[issue_url])
            continue
        parsed_issue = parse_jira_issue_url(issue_url)
        if parsed_issue is None:
            continue
        jira_base, issue_key = parsed_issue
        api_url = (
            f"{jira_base}/rest/api/2/issue/{quote(issue_key)}"
            "?expand=renderedFields"
        )
        try:
            payload = fetch_json_with_headers(session, api_url, headers=headers, request_interval_override=0.0)
        except FetchError:
            continue
        issue_page_ids = extract_confluence_page_ids_from_value(payload, site_base)
        issue_cache[issue_url] = issue_page_ids
        linked_page_ids.update(issue_page_ids)

    session.jira_issue_cache = issue_cache
    return linked_page_ids


def extract_image_urls(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    page_host = urlparse(page_url).netloc
    urls: list[str] = []
    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-image-src") or ""
        src = src.strip()
        if not src:
            continue
        absolute = urljoin(page_url, src)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != page_host:
            continue
        urls.append(absolute)
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def tag_local_name(tag: Tag) -> str:
    return str(tag.name or "").split(":", 1)[-1].lower()


def tag_attr(tag: Tag, name: str) -> str:
    for key, value in tag.attrs.items():
        if str(key).split(":", 1)[-1].lower() == name.lower():
            return str(value or "")
    return ""


def extract_drawio_attachment_names(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    names: list[str] = []

    for macro in soup.find_all(lambda tag: isinstance(tag, Tag) and tag_local_name(tag) == "structured-macro"):
        macro_name = tag_attr(macro, "name").lower()
        if "drawio" not in macro_name and "diagramly" not in macro_name and "mxgraph" not in macro_name:
            continue
        for param in macro.find_all(lambda tag: isinstance(tag, Tag) and tag_local_name(tag) == "parameter"):
            param_name = tag_attr(param, "name").lower()
            if param_name in {"diagramname", "diagram", "name", "filename", "attachment"}:
                value = collapse_whitespace(param.get_text(" ", strip=True))
                if value:
                    names.append(value)
        for attachment in macro.find_all(lambda tag: isinstance(tag, Tag) and tag_local_name(tag) == "attachment"):
            value = tag_attr(attachment, "filename")
            if value:
                names.append(value)

    for attachment in soup.find_all(lambda tag: isinstance(tag, Tag) and tag_local_name(tag) == "attachment"):
        value = tag_attr(attachment, "filename")
        if value.lower().endswith((".drawio", ".dio", ".xml")):
            names.append(value)

    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        normalized = html_lib.unescape(name).strip()
        if not normalized:
            continue
        candidates = [normalized]
        if not normalized.lower().endswith((".drawio", ".dio", ".xml")):
            candidates.append(f"{normalized}.drawio")
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def extract_attachment_names_by_extension(html: str, extensions: tuple[str, ...]) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    names: list[str] = []
    lowered_extensions = tuple(ext.lower() for ext in extensions)

    for attachment in soup.find_all(lambda tag: isinstance(tag, Tag) and tag_local_name(tag) == "attachment"):
        value = tag_attr(attachment, "filename")
        if value.lower().endswith(lowered_extensions):
            names.append(value)

    for link in soup.find_all("a"):
        href = str(link.get("href") or "").strip()
        label = collapse_whitespace(link.get_text(" ", strip=True))
        for value in (href, label):
            parsed_name = Path(urlparse(value).path).name if value else ""
            if parsed_name.lower().endswith(lowered_extensions):
                names.append(parsed_name)

    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        normalized = html_lib.unescape(name).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def resolve_metadata_dir(output_dir: Path, metadata_dir_arg: str) -> Path:
    """Where export-state, manifests, and crawl progress live.

    For LLM Wiki projects, ``output_dir`` is typically ``.../raw``; metadata then defaults to
    ``.../staging/wiki-export-state`` so ``raw/`` only contains page folders and assets.
    """
    text = (metadata_dir_arg or "").strip()
    if text:
        return Path(text).expanduser().resolve()
    if output_dir.name == "raw":
        return (output_dir.parent / "staging" / "wiki-export-state").resolve()
    return output_dir.resolve()


def progress_file_path(metadata_dir: Path) -> Path:
    return metadata_dir / "crawl-progress.json"


def root_progress_file_path(metadata_dir: Path, root_page_id: str) -> Path:
    return metadata_dir / "progress" / f"{root_page_id}.json"


def resolve_existing_progress_file(metadata_dir: Path, output_dir: Path, root_page_id: str) -> Path:
    """Prefer metadata layout; fall back to legacy ``raw/progress`` when upgrading."""
    primary = root_progress_file_path(metadata_dir, root_page_id)
    if primary.exists():
        return primary
    legacy = output_dir / "progress" / f"{root_page_id}.json"
    if legacy.exists():
        return legacy
    return primary


def root_pages_dir_name(root_page_id: str) -> str:
    """Return empty string so pages live directly under output_dir (e.g. raw/<pageId>-slug/)."""
    return ""


def root_manifest_name(root_page_id: str) -> str:
    return f"manifest-{root_page_id}.json"


def save_progress_state(
    progress_file: Path,
    *,
    root_page_id: str,
    depth_limit: int,
    pages: dict[str, PageNode],
    queue: deque[tuple[str, int]],
    enqueued: set[str],
    page_paths: Optional[dict[str, str | Path]] = None,
) -> None:
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "root_page_id": root_page_id,
        "depth_limit": depth_limit,
        "pages": {page_id: page_node_to_dict(page) for page_id, page in pages.items()},
        "queue": [[page_id, depth] for page_id, depth in queue],
        "enqueued": sorted(enqueued),
    }
    if page_paths:
        payload["page_paths"] = {
            str(page_id): Path(path).as_posix()
            for page_id, path in page_paths.items()
            if str(page_id).strip() and str(path).strip()
        }
    temp_suffix = f".{os.getpid()}.{int(time.time() * 1000)}.{random.randint(1000, 9999)}.tmp"
    temp_file = progress_file.with_name(progress_file.name + temp_suffix)
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_file.replace(progress_file)


def load_progress_state(
    progress_file: Path,
    *,
    root_page_id: str,
    depth_limit: int,
) -> Optional[dict[str, Any]]:
    if not progress_file.exists():
        return None
    payload = json.loads(progress_file.read_text(encoding="utf-8"))
    if str(payload.get("root_page_id")) != str(root_page_id):
        return None
    if int(payload.get("depth_limit", -1)) != int(depth_limit):
        return None
    pages = {
        page_id: page_node_from_dict(page_data)
        for page_id, page_data in (payload.get("pages") or {}).items()
    }
    queue = deque((str(page_id), int(depth)) for page_id, depth in (payload.get("queue") or []))
    enqueued = {str(page_id) for page_id in (payload.get("enqueued") or [])}
    page_paths = {
        str(page_id): str(path)
        for page_id, path in (payload.get("page_paths") or {}).items()
        if str(page_id).strip() and str(path).strip()
    }
    return {"pages": pages, "queue": queue, "enqueued": enqueued, "page_paths": page_paths}


def crawl_pages(
    session: requests.Session,
    site_base: str,
    root_page_id: str,
    depth_limit: int,
    progress_file: Optional[Path] = None,
    max_pages: Optional[int] = None,
    depth_one_child_filter: Optional[Callable[[dict[str, Any]], bool]] = None,
) -> dict[str, PageNode]:
    if progress_file:
        state = load_progress_state(progress_file, root_page_id=root_page_id, depth_limit=depth_limit)
    else:
        state = None

    if state:
        pages = state["pages"]
        queue = state["queue"]
        enqueued = state["enqueued"]
    else:
        pages = {}
        queue = deque([(root_page_id, 0)])
        enqueued = {root_page_id}

    if max_pages is not None and max_pages <= 0:
        return pages

    if max_pages is not None and len(pages) >= max_pages:
        if progress_file:
            save_progress_state(
                progress_file,
                root_page_id=root_page_id,
                depth_limit=depth_limit,
                pages=pages,
                queue=queue,
                enqueued=enqueued,
            )
        return pages

    while queue:
        page_id, depth = queue.popleft()
        if page_id in pages:
            if progress_file:
                save_progress_state(
                    progress_file,
                    root_page_id=root_page_id,
                    depth_limit=depth_limit,
                    pages=pages,
                    queue=queue,
                    enqueued=enqueued,
                )
            continue
        try:
            page = fetch_page(session, site_base, page_id, depth=depth)
        except FetchError as exc:
            if exc.status_code == 404:
                if progress_file:
                    save_progress_state(
                        progress_file,
                        root_page_id=root_page_id,
                        depth_limit=depth_limit,
                        pages=pages,
                        queue=queue,
                        enqueued=enqueued,
                    )
                continue
            raise
        pages[page_id] = page
        if depth >= depth_limit:
            if progress_file:
                save_progress_state(
                    progress_file,
                    root_page_id=root_page_id,
                    depth_limit=depth_limit,
                    pages=pages,
                    queue=queue,
                    enqueued=enqueued,
                )
            continue

        child_payloads = fetch_children(session, site_base, page.page_id)
        if depth == 0 and depth_one_child_filter is not None:
            next_page_ids = {
                str(child_payload["id"])
                for child_payload in child_payloads
                if depth_one_child_filter(child_payload)
            }
        else:
            next_page_ids = {str(child_payload["id"]) for child_payload in child_payloads}
            next_page_ids.update(extract_linked_page_ids(page.html, page.url, site_base))
            next_page_ids.update(fetch_jira_linked_page_ids(session, page.html, page.url, site_base))

        for next_page_id in sorted(next_page_ids):
            if next_page_id in enqueued:
                continue
            enqueued.add(next_page_id)
            queue.append((next_page_id, depth + 1))

        if progress_file:
            save_progress_state(
                progress_file,
                root_page_id=root_page_id,
                depth_limit=depth_limit,
                pages=pages,
                queue=queue,
                enqueued=enqueued,
            )

        if max_pages is not None and len(pages) >= max_pages:
            break

    return pages


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fenced_code_block(text: str, info: str = "text") -> list[str]:
    fence = "```"
    while fence in text:
        fence += "`"
    return [f"{fence}{info}", text, fence]


def render_inline(
    node: NavigableString | Tag,
    base_url: str,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name == "br":
        return "\n"
    if name in {"strong", "b"}:
        return f"**{render_inline_children(node.children, base_url, page_links, image_links)}**"
    if name in {"em", "i"}:
        return f"*{render_inline_children(node.children, base_url, page_links, image_links)}*"
    if name == "code" and node.parent and node.parent.name != "pre":
        text = collapse_whitespace(node.get_text(" ", strip=True))
        return f"`{text}`" if text else ""
    if name == "a":
        text = collapse_whitespace(
            render_inline_children(node.children, base_url, page_links, image_links)
        ) or node.get_text(" ", strip=True)
        href = node.get("href", "").strip()
        target = urljoin(base_url, href) if href else ""
        linked_page_id = node.get("data-linked-resource-id", "").strip() or parse_qs(
            urlparse(target).query
        ).get("pageId", [None])[0]
        if linked_page_id and page_links and linked_page_id in page_links:
            target = page_links[linked_page_id]
        if text and target:
            return f"[{text}]({target})"
        return text or target
    if name == "img":
        alt = collapse_whitespace(node.get("alt", "image")) or "image"
        src = node.get("src", "").strip()
        target = urljoin(base_url, src) if src else ""
        if target and image_links and target in image_links:
            target = image_links[target]
        return f"![{alt}]({target})" if target else ""
    return render_inline_children(node.children, base_url, page_links, image_links)


def render_inline_children(
    children: Iterable[NavigableString | Tag],
    base_url: str,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    rendered = "".join(
        render_inline(child, base_url, page_links=page_links, image_links=image_links)
        for child in children
    )
    rendered = re.sub(r"[ \t]+\n", "\n", rendered)
    rendered = re.sub(r"\n[ \t]+", "\n", rendered)
    return rendered


def render_table(
    table: Tag,
    base_url: str,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    table_html = str(table)
    table_soup = BeautifulSoup(table_html, "html.parser")
    table_copy = table_soup.find("table")
    if table_copy is None:
        return ""

    for anchor in table_copy.find_all("a"):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        target = urljoin(base_url, href)
        linked_page_id = anchor.get("data-linked-resource-id", "").strip() or parse_qs(
            urlparse(target).query
        ).get("pageId", [None])[0]
        if linked_page_id and page_links and linked_page_id in page_links:
            anchor["href"] = page_links[linked_page_id]
        else:
            anchor["href"] = target

    for image in table_copy.find_all("img"):
        src = image.get("src") or image.get("data-image-src") or ""
        src = src.strip()
        if not src:
            continue
        target = urljoin(base_url, src)
        if image_links and target in image_links:
            image["src"] = image_links[target]
        else:
            image["src"] = target
        if image.has_attr("data-image-src"):
            del image["data-image-src"]

    for tag in [table_copy, *table_copy.find_all(True)]:
        allowed_attrs: set[str]
        name = tag.name.lower()
        if name in {"table", "thead", "tbody", "tfoot", "tr"}:
            allowed_attrs = set()
        elif name in {"th", "td"}:
            allowed_attrs = {"rowspan", "colspan", "scope"}
        elif name == "a":
            allowed_attrs = {"href"}
        elif name == "img":
            allowed_attrs = {"src", "alt"}
        elif name in {"br", "p"}:
            allowed_attrs = set()
        else:
            tag.unwrap()
            continue

        for attr_name in list(tag.attrs.keys()):
            if attr_name not in allowed_attrs:
                del tag.attrs[attr_name]

    return str(table_copy)


def render_block(
    node: NavigableString | Tag,
    base_url: str,
    indent: int = 0,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    if isinstance(node, NavigableString):
        text = collapse_whitespace(str(node))
        return text if text else ""
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name in {"script", "style", "noscript"}:
        return ""
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        text = collapse_whitespace(
            render_inline_children(node.children, base_url, page_links, image_links)
        )
        return f"{'#' * level} {text}".strip()
    if name == "p":
        return collapse_whitespace(render_inline_children(node.children, base_url, page_links, image_links))
    if name in {"div", "section", "article"}:
        has_block_children = any(
            isinstance(child, Tag) and child.name and child.name.lower() in BLOCK_TAGS
            for child in node.children
        )
        if has_block_children:
            return render_children(node.children, base_url, page_links, image_links)
        return collapse_whitespace(render_inline_children(node.children, base_url, page_links, image_links))
    if name == "li":
        return render_children(node.children, base_url, page_links, image_links)
    if name == "pre":
        code = node.get_text("\n", strip=False).strip("\n")
        return f"```\n{code}\n```" if code else ""
    if name == "blockquote":
        body = render_children(node.children, base_url, page_links, image_links)
        lines = [line for line in body.splitlines() if line.strip()]
        return "\n".join(f"> {line}" for line in lines)
    if name == "ul":
        items = []
        for li in node.find_all("li", recursive=False):
            text = render_children(li.children, base_url, page_links, image_links).strip() or collapse_whitespace(
                li.get_text(" ", strip=True)
            )
            text = text.replace("\n", "\n  ")
            items.append(f"{'  ' * indent}- {text}")
        return "\n".join(items)
    if name == "ol":
        items = []
        for idx, li in enumerate(node.find_all("li", recursive=False), start=1):
            text = render_children(li.children, base_url, page_links, image_links).strip() or collapse_whitespace(
                li.get_text(" ", strip=True)
            )
            text = text.replace("\n", "\n   ")
            items.append(f"{'  ' * indent}{idx}. {text}")
        return "\n".join(items)
    if name == "table":
        return render_table(node, base_url, page_links, image_links)
    if name == "hr":
        return "---"
    if name == "body":
        return render_children(node.children, base_url, page_links, image_links)
    inline = collapse_whitespace(render_inline(node, base_url, page_links, image_links))
    return inline


def render_children(
    children: Iterable[NavigableString | Tag],
    base_url: str,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    blocks = [
        render_block(child, base_url, page_links=page_links, image_links=image_links)
        for child in children
    ]
    cleaned = [block.strip() for block in blocks if block and block.strip()]
    output = "\n\n".join(cleaned)
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output.strip()


def html_to_markdown(
    html: str,
    base_url: str,
    page_links: Optional[dict[str, str]] = None,
    image_links: Optional[dict[str, str]] = None,
) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for macro in soup.select("ac\\:structured-macro, ri\\:page, ri\\:attachment, ri\\:url, ri\\:user"):
        macro.unwrap()
    body = soup.body or soup
    return render_children(body.children, base_url, page_links=page_links, image_links=image_links)


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^\w.\-]+", "-", value, flags=re.UNICODE).strip("-")
    return sanitized or "file"


def page_output_base_dir(output_dir: Path, pages_dir_name: str = "pages") -> Path:
    return output_dir / pages_dir_name if pages_dir_name else output_dir


def page_output_dir(output_dir: Path, page: PageNode, pages_dir_name: str = "pages") -> Path:
    return page_output_base_dir(output_dir, pages_dir_name) / f"{page.page_id}-{slugify(page.title)}"


def path_relative_to_base(path: Path, base_dir: Path) -> str:
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_page_path_override(output_dir: Path, override: str | Path) -> Path:
    override_path = Path(override)
    if override_path.is_absolute():
        return override_path
    return output_dir / override_path


def build_page_paths(
    pages: dict[str, PageNode],
    output_dir: Path,
    pages_dir_name: str = "pages",
    page_path_overrides: Optional[dict[str, str | Path]] = None,
) -> dict[str, Path]:
    overrides = page_path_overrides or {}
    paths: dict[str, Path] = {}
    for page_id, page in pages.items():
        override = overrides.get(page_id)
        if override:
            paths[page_id] = resolve_page_path_override(output_dir, override)
            continue
        paths[page_id] = page_output_dir(output_dir, page, pages_dir_name=pages_dir_name) / "index.md"
    return paths


def relpath_from(source: Path, target: Path) -> str:
    return os.path.relpath(target, start=source.parent).replace(os.sep, "/")


def asset_map_path(page_dir: Path) -> Path:
    return page_dir / ".asset-map.json"


def load_asset_map(page_dir: Path) -> dict[str, str]:
    path = asset_map_path(page_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            cleaned[key] = value
    return cleaned


def save_asset_map(page_dir: Path, asset_map: dict[str, str]) -> None:
    path = asset_map_path(page_dir)
    path.write_text(json.dumps(asset_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_asset_refs(markdown: str) -> set[str]:
    refs = set(re.findall(r"\((assets/[^)]+)\)", markdown))
    refs.update(re.findall(r'src="(assets/[^"]+)"', markdown))
    return refs


def parse_frontmatter_value(content: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", content)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def page_is_unchanged(page_path: Path, page: PageNode) -> bool:
    if not page_path.exists():
        return False
    content = page_path.read_text(encoding="utf-8")
    if parse_frontmatter_value(content, "page_id") != page.page_id:
        return False
    if parse_frontmatter_value(content, "source_url") != page.url:
        return False
    if parse_frontmatter_value(content, "updated_at") != page.updated_at:
        return False
    if parse_frontmatter_value(content, "version_number") != str(page.version_number):
        return False
    for asset_ref in local_asset_refs(content):
        if not (page_path.parent / asset_ref).exists():
            return False
    if extract_drawio_attachment_names(page.storage_html or page.html):
        if "## Draw.io Diagrams" not in content:
            return False
        if not list((page_path.parent / "assets").glob("*.drawio.md")):
            return False
    return True


def resolve_asset_filename(
    image_url: str,
    index: int,
    assets_dir: Path,
    asset_map: dict[str, str],
    reserved_names: set[str],
) -> str:
    mapped_name = asset_map.get(image_url, "").strip()
    if mapped_name:
        return mapped_name

    parsed = urlparse(image_url)
    filename = sanitize_filename(Path(parsed.path).name)
    if not Path(filename).suffix:
        filename = f"{filename or 'image'}-{index}.bin"

    if filename not in reserved_names:
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:10]
    candidate = f"{stem}-{digest}{suffix}"
    if candidate not in reserved_names:
        return candidate

    counter = 2
    while True:
        candidate = f"{stem}-{digest}-{counter}{suffix}"
        if candidate not in reserved_names:
            return candidate
        counter += 1


def download_page_images(
    session: Optional[requests.Session],
    html: str,
    page_url: str,
    page_dir: Path,
) -> dict[str, str]:
    if session is None:
        return {}
    assets_dir = page_dir / "assets"
    asset_map = load_asset_map(page_dir)
    image_links: dict[str, str] = {}
    reserved_names = {path.name for path in assets_dir.iterdir()} if assets_dir.exists() else set()
    for index, image_url in enumerate(extract_image_urls(html, page_url), start=1):
        assets_dir.mkdir(parents=True, exist_ok=True)
        filename = resolve_asset_filename(image_url, index, assets_dir, asset_map, reserved_names)
        image_path = assets_dir / filename
        reserved_names.add(filename)
        if image_path.exists():
            asset_map[image_url] = image_path.name
            image_links[image_url] = f"assets/{image_path.name}"
            continue
        response = send_request(
            session,
            image_url,
            stream=True,
            accept="*/*",
            request_interval_override=getattr(session, "asset_request_interval", 0.0),
        )
        if response.status_code >= 400:
            continue
        with image_path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
        asset_map[image_url] = image_path.name
        image_links[image_url] = f"assets/{image_path.name}"
    save_asset_map(page_dir, asset_map)
    return image_links


def attachment_download_url(site_base: str, payload: dict[str, Any]) -> str:
    links = payload.get("_links") if isinstance(payload, dict) else {}
    download = str((links or {}).get("download") or "").strip()
    base = str((links or {}).get("base") or site_base).strip() or site_base
    return urljoin(base, download) if download else ""


def fetch_attachment_payload(session: requests.Session, site_base: str, page_id: str, filename: str) -> dict[str, Any] | None:
    try:
        payload = fetch_json(session, attachments_endpoint(site_base, page_id, filename))
    except FetchError:
        return None
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        return None
    if not results:
        return None
    return results[0] if isinstance(results[0], dict) else None


def download_drawio_attachment(
    session: Optional[requests.Session],
    site_base: str,
    page: PageNode,
    filename: str,
    assets_dir: Path,
) -> tuple[Path, str] | None:
    if session is None:
        return None
    payload = fetch_attachment_payload(session, site_base, page.page_id, filename)
    if payload is None:
        return None
    download_url = attachment_download_url(site_base, payload)
    if not download_url:
        return None
    assets_dir.mkdir(parents=True, exist_ok=True)
    local_name = sanitize_filename(filename)
    if not Path(local_name).suffix:
        local_name = f"{local_name}.drawio"
    local_path = assets_dir / local_name
    if not local_path.exists():
        response = send_request(
            session,
            download_url,
            stream=True,
            accept="*/*",
            request_interval_override=getattr(session, "asset_request_interval", 0.0),
        )
        if response.status_code >= 400:
            return None
        with local_path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
    return local_path, download_url


def download_attachment(
    session: Optional[requests.Session],
    site_base: str,
    page: PageNode,
    filename: str,
    assets_dir: Path,
) -> tuple[Path, str] | None:
    if session is None:
        return None
    payload = fetch_attachment_payload(session, site_base, page.page_id, filename)
    if payload is None:
        return None
    download_url = attachment_download_url(site_base, payload)
    if not download_url:
        return None
    assets_dir.mkdir(parents=True, exist_ok=True)
    local_path = assets_dir / sanitize_filename(filename)
    if not local_path.exists():
        response = send_request(
            session,
            download_url,
            stream=True,
            accept="*/*",
            request_interval_override=getattr(session, "asset_request_interval", 0.0),
        )
        if response.status_code >= 400:
            return None
        with local_path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
    return local_path, download_url


def safe_extract_zip(zip_path: Path, target_dir: Path) -> list[Path]:
    extracted: list[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            repaired_name = repair_zip_member_name(member.filename)
            parts = Path(repaired_name).parts
            if any(part == "__MACOSX" or part == ".DS_Store" or part.startswith("._") for part in parts):
                continue
            destination = (target_dir / repaired_name).resolve()
            if not str(destination).startswith(str(target_root) + os.sep):
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                output.write(source.read())
            extracted.append(destination)
    return extracted


def repair_zip_member_name(name: str) -> str:
    repaired_parts: list[str] = []
    for part in Path(name).parts:
        try:
            repaired = part.encode("cp437").decode("utf-8")
        except UnicodeError:
            repaired = part
        repaired_parts.append(repaired)
    return "/".join(repaired_parts)


def extract_balanced_json(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def sketch_meaxure_summary(text: str) -> list[str]:
    match = re.search(r"\blet\s+data\s*=\s*\{", text)
    if not match:
        return []
    json_text = extract_balanced_json(text, match.end() - 1)
    if not json_text:
        return []
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    artboards = payload.get("artboards") if isinstance(payload, dict) else None
    if not isinstance(artboards, list):
        return []

    lines = ["", "#### Sketch MeaXure artboards", ""]
    for artboard in artboards[:30]:
        if not isinstance(artboard, dict):
            continue
        name = str(artboard.get("name") or "").strip()
        width = artboard.get("width")
        height = artboard.get("height")
        layers = artboard.get("layers")
        text_values: list[str] = []
        if isinstance(layers, list):
            for layer in layers:
                if not isinstance(layer, dict):
                    continue
                content = collapse_whitespace(str(layer.get("content") or ""))
                if content and content not in text_values:
                    text_values.append(content)
                if len(text_values) >= 8:
                    break
        label = name or "unnamed artboard"
        size = f" ({width}x{height})" if width and height else ""
        lines.append(f"- {label}{size}")
        if text_values:
            lines.append(f"  - Text: {' / '.join(text_values)}")
    return lines


def direct_text(tag: Tag) -> str:
    values: list[str] = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            value = collapse_whitespace(str(child))
            if value:
                values.append(value)
        elif isinstance(child, Tag) and child.name == "span":
            value = collapse_whitespace(child.get_text(" ", strip=True))
            if value and value != "*":
                values.append(value)
    return collapse_whitespace(" ".join(values))


def field_label(form_item: Tag) -> tuple[str, bool]:
    label = form_item.find(class_="label") or form_item.find("label")
    if not isinstance(label, Tag):
        return "", False
    raw = collapse_whitespace(label.get_text(" ", strip=True))
    required = "*" in raw or label.find("span", string=re.compile(r"\*")) is not None
    return raw.replace("*", "").strip(), required


def field_control_summary(form_item: Tag) -> tuple[str, str, str]:
    controls = form_item.find_all(["input", "textarea", "select"])
    if not controls:
        return "static", "", ""
    first = controls[0]
    if not isinstance(first, Tag):
        return "static", "", ""
    control_type = str(first.get("type") or first.name or "").strip() or first.name
    identifier = str(first.get("name") or first.get("id") or "").strip()
    details: list[str] = []

    radio_values = []
    for radio in form_item.find_all("input", attrs={"type": "radio"}):
        if not isinstance(radio, Tag):
            continue
        value = str(radio.get("value") or "").strip()
        if value:
            radio_values.append(value)
    if radio_values:
        return "radio", str(first.get("name") or first.get("id") or "").strip(), "; ".join(radio_values)

    if first.name == "select":
        options = [
            collapse_whitespace(option.get_text(" ", strip=True))
            for option in first.find_all("option")
            if collapse_whitespace(option.get_text(" ", strip=True))
        ]
        return "select", identifier, "; ".join(options)

    placeholder = str(first.get("placeholder") or "").strip()
    if placeholder:
        details.append(placeholder)
    accept = str(first.get("accept") or "").strip()
    if accept:
        details.append(f"accepts: {accept}")
    if first.has_attr("multiple"):
        details.append("multiple")
    maxlength = str(first.get("maxlength") or "").strip()
    if maxlength:
        details.append(f"max length: {maxlength}")
    return control_type, identifier, "; ".join(details)


def html_form_structure_summary(soup: BeautifulSoup) -> list[str]:
    form_items = soup.find_all(class_="form-item")
    buttons = [collapse_whitespace(button.get_text(" ", strip=True)) for button in soup.find_all("button")]
    buttons = [button for button in buttons if button]
    tabs = [
        collapse_whitespace(button.get_text(" ", strip=True))
        for button in soup.find_all("button", class_=lambda value: value and "tab" in str(value))
    ]
    tabs = [tab for tab in tabs if tab]
    if not form_items and not buttons and not tabs:
        return []

    lines = ["", "#### Prototype structure", ""]
    if tabs:
        lines.append(f"- Modes/tabs: {', '.join(tabs)}")
    if buttons:
        lines.append(f"- Buttons: {', '.join(buttons)}")

    section_ids = ["newVisitFields", "returnVisitFields"]
    sections: list[tuple[str, list[Tag]]] = []
    for section_id in section_ids:
        section = soup.find(id=section_id)
        if isinstance(section, Tag):
            sections.append((section_id, [item for item in section.find_all(class_="form-item") if isinstance(item, Tag)]))
    if not sections and form_items:
        sections.append(("page", [item for item in form_items if isinstance(item, Tag)]))

    for section_id, items in sections:
        lines.extend(["", f"##### Section `{section_id}`", "", "| Field | Control | Required | ID/name | Details |", "| --- | --- | --- | --- | --- |"])
        for item in items:
            label, required = field_label(item)
            if not label:
                continue
            control_type, identifier, details = field_control_summary(item)
            required_text = "required" if required else "optional"
            lines.append(f"| {label} | {control_type} | {required_text} | {identifier} | {details} |")
    return lines


def summarize_html_file(path: Path, root: Path) -> list[str]:
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    title = collapse_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else ""
    visible = collapse_whitespace(soup.get_text(" ", strip=True))[:1000]
    lines = [f"### `{rel}`", ""]
    if title:
        lines.append(f"- Title: {title}")
    if visible:
        lines.extend(["- Visible text:", "", "```text", visible, "```"])
    lines.extend(html_form_structure_summary(soup))
    lines.extend(sketch_meaxure_summary(text))
    return lines


def prototype_note_markdown(page: PageNode, zip_path: Path, extract_dir: Path, extracted: list[Path]) -> str:
    html_files = sorted(path for path in extracted if path.suffix.lower() in {".html", ".htm"})
    data_files = sorted(
        path
        for path in extracted
        if path.suffix.lower() in {".json", ".js", ".css", ".md", ".txt", ".csv", ".yaml", ".yml"}
    )
    lines = [
        f"# Prototype Evidence: {zip_path.name}",
        "",
        f"- Source attachment: `{zip_path.name}`",
        f"- Page ID: `{page.page_id}`",
        f"- Page title: {page.title}",
        "",
        "## HTML entry points",
        "",
    ]
    if html_files:
        for html_file in html_files:
            lines.extend(summarize_html_file(html_file, extract_dir))
            lines.append("")
    else:
        lines.append("- No HTML entry points detected.")

    lines.extend(["", "## Supporting files", ""])
    if data_files:
        for data_file in data_files[:50]:
            rel = data_file.resolve().relative_to(extract_dir.resolve()).as_posix()
            lines.append(f"### `{rel}`")
            if data_file.suffix.lower() in {".md", ".txt", ".csv", ".yaml", ".yml", ".json"}:
                excerpt = data_file.read_text(encoding="utf-8", errors="replace").strip()[:1000]
                if excerpt:
                    fence = "json" if data_file.suffix.lower() == ".json" else "text"
                    lines.extend(["", *fenced_code_block(excerpt, fence), ""])
                    continue
            lines.append("")
    else:
        lines.append("- No supporting text-like files detected.")
    return "\n".join(lines).rstrip() + "\n"


def prototype_evidence_markdown(page: PageNode, page_dir: Path, session: Optional[requests.Session]) -> str:
    names = extract_attachment_names_by_extension(page.storage_html or page.html, (".zip",))
    if not names or session is None:
        return ""

    site_base = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
    assets_dir = page_dir / "assets"
    sections: list[str] = []
    for filename in names:
        downloaded = download_attachment(session, site_base, page, filename, assets_dir)
        if downloaded is None:
            continue
        zip_path, _download_url = downloaded
        prototype_name = Path(zip_path.stem).stem or "prototype"
        extract_dir = assets_dir / "prototypes" / sanitize_filename(prototype_name)
        try:
            extracted = safe_extract_zip(zip_path, extract_dir)
        except zipfile.BadZipFile:
            continue
        has_text_evidence = any(
            path.suffix.lower() in {".html", ".htm", ".json", ".js", ".css", ".md", ".txt", ".csv", ".yaml", ".yml"}
            for path in extracted
        )
        if not has_text_evidence:
            continue
        evidence_path = zip_path.with_suffix(zip_path.suffix + ".prototype.md")
        evidence_path.write_text(prototype_note_markdown(page, zip_path, extract_dir, extracted), encoding="utf-8")
        rel_zip = f"assets/{zip_path.name}"
        rel_evidence = f"assets/{evidence_path.name}"
        sections.extend(
            [
                f"### {zip_path.name}",
                "",
                f"- 附件: [`{rel_zip}`]({rel_zip})",
                f"- 原型证据: [`{rel_evidence}`]({rel_evidence})",
                "",
            ]
        )
    if not sections:
        return ""
    return "## Prototype Attachments\n\n" + "\n".join(sections).rstrip()


def drawio_evidence_markdown(page: PageNode, page_dir: Path, session: Optional[requests.Session]) -> str:
    names = extract_drawio_attachment_names(page.storage_html or page.html)
    if not names or session is None:
        return ""

    site_base = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
    sections: list[str] = []
    assets_dir = page_dir / "assets"
    for filename in names:
        downloaded = download_drawio_attachment(session, site_base, page, filename, assets_dir)
        if downloaded is None:
            continue
        local_path, _download_url = downloaded
        try:
            text = local_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        diagrams = drawio_to_mermaid(text, fallback_name=Path(filename).stem)
        if not diagrams:
            continue
        evidence_path = local_path.with_suffix(local_path.suffix + ".md")
        rel_drawio = f"assets/{local_path.name}"
        rel_evidence = f"assets/{evidence_path.name}"
        evidence_lines = [
            f"# Draw.io Evidence: {filename}",
            "",
            f"- Source attachment: `{rel_drawio}`",
            f"- Page ID: `{page.page_id}`",
            "",
        ]
        page_lines = [
            f"### {filename}",
            "",
            f"- 附件: [`{rel_drawio}`]({rel_drawio})",
            f"- 结构化证据: [`{rel_evidence}`]({rel_evidence})",
            "",
        ]
        for diagram in diagrams:
            evidence_lines.extend(
                [
                    f"## {diagram.name}",
                    "",
                    f"- Nodes: `{diagram.node_count}`",
                    f"- Edges: `{diagram.edge_count}`",
                    "",
                    "```mermaid",
                    diagram.mermaid,
                    "```",
                    "",
                ]
            )
            page_lines.extend(
                [
                    f"#### {diagram.name}",
                    "",
                    "```mermaid",
                    diagram.mermaid,
                    "```",
                    "",
                ]
            )
        evidence_path.write_text("\n".join(evidence_lines).rstrip() + "\n", encoding="utf-8")
        sections.append("\n".join(page_lines).rstrip())

    if not sections:
        return ""
    return "\n\n".join(["## Draw.io Diagrams", *sections])


def yaml_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def build_frontmatter(page: PageNode) -> str:
    lines = [
        "---",
        f"title: {yaml_escape(page.title)}",
        f"page_id: {yaml_escape(page.page_id)}",
        f"source_url: {page.url}",
        f"author: {yaml_escape(page.author)}",
        f"last_editor: {yaml_escape(page.last_editor)}",
        f"created_at: {yaml_escape(page.created_at)}",
        f"updated_at: {yaml_escape(page.updated_at)}",
        f"version_number: {page.version_number}",
        "tags:",
        "  - confluence",
        "---",
    ]
    return "\n".join(lines)


def write_page(path: Path, page: PageNode, markdown: str) -> None:
    content = "\n".join(
        [
            build_frontmatter(page),
            "",
            f"# {page.title}",
            "",
            markdown.strip(),
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def write_export(
    pages: dict[str, PageNode],
    output_dir: Path,
    session: Optional[requests.Session],
    *,
    pages_dir_name: str = "pages",
    manifest_name: str = "manifest.json",
    page_path_overrides: Optional[dict[str, str | Path]] = None,
    manifest_dir: Optional[Path] = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_base = manifest_dir if manifest_dir is not None else output_dir
    manifest: list[dict] = []
    page_paths = build_page_paths(
        pages,
        output_dir,
        pages_dir_name=pages_dir_name,
        page_path_overrides=page_path_overrides,
    )

    for page_id, page in sorted(pages.items(), key=lambda item: (item[1].depth, item[1].title, item[0])):
        page_dir = page_paths[page_id].parent
        page_dir.mkdir(parents=True, exist_ok=True)
        page_path = page_paths[page_id]
        if page_is_unchanged(page_path, page):
            manifest.append(
                {
                    "page_id": page.page_id,
                    "title": page.title,
                    "depth": page.depth,
                    "path": path_relative_to_base(page_path, output_dir),
                    "source_url": page.url,
                }
            )
            continue
        image_links = download_page_images(session, page.html, page.url, page_dir)
        page_links = {
            target_page_id: relpath_from(page_path, target_path)
            for target_page_id, target_path in page_paths.items()
            if target_page_id != page_id
        }
        markdown = html_to_markdown(
            page.html,
            page.url,
            page_links=page_links,
            image_links=image_links,
        )
        drawio_markdown = drawio_evidence_markdown(page, page_dir, session)
        if drawio_markdown:
            markdown = markdown.rstrip() + "\n\n" + drawio_markdown
        prototype_markdown = prototype_evidence_markdown(page, page_dir, session)
        if prototype_markdown:
            markdown = markdown.rstrip() + "\n\n" + prototype_markdown
        write_page(page_path, page, markdown)
        manifest.append(
                {
                    "page_id": page.page_id,
                    "title": page.title,
                    "depth": page.depth,
                    "path": path_relative_to_base(page_path, output_dir),
                    "source_url": page.url,
                }
        )

    manifest_path = manifest_base / manifest_name
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_root_export(
    root_page_id: str,
    pages: dict[str, PageNode],
    output_dir: Path,
    session: Optional[requests.Session],
    *,
    pages_dir_name: Optional[str] = None,
    manifest_name: Optional[str] = None,
    page_path_overrides: Optional[dict[str, str | Path]] = None,
    manifest_dir: Optional[Path] = None,
) -> None:
    if pages_dir_name is None:
        pages_dir_name = root_pages_dir_name(root_page_id)
    if manifest_name is None:
        manifest_name = root_manifest_name(root_page_id)
    write_export(
        pages,
        output_dir,
        session,
        pages_dir_name=pages_dir_name,
        manifest_name=manifest_name,
        page_path_overrides=page_path_overrides,
        manifest_dir=manifest_dir,
    )


def parse_iso_datetime(value: str) -> Optional[datetime]:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_updated_since(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    parsed = parse_iso_datetime(text)
    if parsed is not None:
        return parsed
    try:
        date_only = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(
            f"Invalid --updated-since '{value}'. Use YYYY-MM-DD or ISO-8601 datetime."
        ) from exc
    return date_only.replace(tzinfo=timezone.utc)


def page_timestamp(page: PageNode) -> Optional[datetime]:
    updated = parse_iso_datetime(page.updated_at)
    if updated is not None:
        return updated
    return parse_iso_datetime(page.created_at)


def page_matches_updated_since(page: PageNode, cutoff: Optional[datetime]) -> bool:
    if cutoff is None:
        return True
    timestamp = page_timestamp(page)
    if timestamp is None:
        return False
    return timestamp >= cutoff


def filter_pages_by_updated_since(
    pages: dict[str, PageNode],
    cutoff: Optional[datetime],
) -> dict[str, PageNode]:
    if cutoff is None:
        return pages
    return {page_id: page for page_id, page in pages.items() if page_matches_updated_since(page, cutoff)}


def feed_entry_is_newer(entry: FeedEntry, page: PageNode) -> bool:
    if entry.version_number is not None and page.version_number:
        return entry.version_number > page.version_number
    entry_updated = parse_iso_datetime(entry.updated_at)
    page_updated = parse_iso_datetime(page.updated_at)
    if entry_updated is not None and page_updated is not None:
        return entry_updated > page_updated
    if entry.updated_at and page.updated_at:
        return entry.updated_at != page.updated_at
    return True


def resolve_rss_max_results(
    root_state: dict[str, Any],
    requested_max_results: int,
    *,
    now: Optional[datetime] = None,
) -> int:
    if requested_max_results > 0:
        return requested_max_results
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    last_update = parse_iso_datetime(str(root_state.get("last_update_at") or ""))
    if last_update is None:
        return DEFAULT_RSS_MAX_RESULTS
    elapsed_seconds = max((now - last_update).total_seconds(), 0.0)
    elapsed_days = max(1, ceil(elapsed_seconds / 86400))
    dynamic_count = elapsed_days * AUTO_RSS_RESULTS_PER_DAY
    return min(AUTO_RSS_MAX_RESULTS, max(AUTO_RSS_MIN_RESULTS, dynamic_count))


def default_change_report_dir(output_dir: Path) -> Path:
    if output_dir.name == "raw":
        return output_dir.parent / "staging" / "wiki-sync"
    return output_dir / "update-reports"


def markdown_table_value(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def format_update_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Wiki Update Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Root page: {report['root_page_id']}",
        f"- RSS entries scanned: {report['scanned_count']}",
        f"- Changed pages: {report['changed_count']}",
        "",
    ]
    changed_pages = report.get("changed_pages") or []
    if not changed_pages:
        lines.append("No changed pages detected.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| page_id | type | title | version | updated_at | raw_path |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in changed_pages:
        version_text = f"{record.get('old_version')} -> {record.get('new_version')}"
        updated_text = f"{record.get('old_updated_at') or ''} -> {record.get('new_updated_at') or ''}"
        lines.append(
            " | ".join(
                [
                    f"| {markdown_table_value(record.get('page_id'))}",
                    markdown_table_value(record.get("change_type")),
                    markdown_table_value(record.get("title")),
                    markdown_table_value(version_text),
                    markdown_table_value(updated_text),
                    f"{markdown_table_value(record.get('raw_path'))} |",
                ]
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_update_change_report(
    *,
    output_dir: Path,
    report_dir: Path,
    root_page_id: str,
    rss_url: str,
    scanned_count: int,
    changed_pages: list[dict[str, Any]],
    skipped_page_ids: list[str],
    ignored_page_ids: list[str],
    dry_run: bool = False,
    root_summaries: Optional[list[dict[str, Any]]] = None,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    generated_at = generated_at.astimezone(timezone.utc)
    generated_text = generated_at.isoformat()
    run_id = generated_at.strftime("%Y%m%dT%H%M%SZ")
    report = {
        "version": 1,
        "generated_at": generated_text,
        "root_page_id": root_page_id,
        "output_dir": str(output_dir),
        "rss_url": rss_url,
        "dry_run": dry_run,
        "scanned_count": scanned_count,
        "changed_count": len(changed_pages),
        "changed_pages": changed_pages,
        "skipped_page_ids": skipped_page_ids,
        "ignored_page_ids": ignored_page_ids,
        "root_summaries": root_summaries or [],
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = report_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (runs_dir / f"{run_id}.json").write_text(payload, encoding="utf-8")
    (report_dir / "latest.json").write_text(payload, encoding="utf-8")
    (report_dir / "latest.md").write_text(
        format_update_report_markdown(report),
        encoding="utf-8",
    )
    return report


def complete_page_path_overrides(
    pages: dict[str, PageNode],
    output_dir: Path,
    *,
    pages_dir_name: str,
    page_path_overrides: dict[str, str | Path],
) -> dict[str, str]:
    page_paths = build_page_paths(
        pages,
        output_dir,
        pages_dir_name=pages_dir_name,
        page_path_overrides=page_path_overrides,
    )
    return {
        page_id: path_relative_to_base(page_path, output_dir)
        for page_id, page_path in page_paths.items()
    }


def update_root_from_rss(
    session: requests.Session,
    *,
    root_page_id: str,
    site_base: str,
    output_dir: Path,
    metadata_dir: Path,
    depth_limit: int,
    rss_url: str,
    include_new: bool = False,
    dry_run: bool = False,
    pages_dir_name: Optional[str] = None,
    manifest_name: Optional[str] = None,
    page_path_overrides: Optional[dict[str, str | Path]] = None,
    change_report_dir: Optional[Path] = None,
    write_report: bool = True,
    updated_since: Optional[datetime] = None,
) -> UpdateResult:
    progress_file = resolve_existing_progress_file(metadata_dir, output_dir, root_page_id)
    state = load_progress_state(
        progress_file,
        root_page_id=root_page_id,
        depth_limit=depth_limit,
    )
    if state is None:
        raise RuntimeError(
            f"No saved export state for root page {root_page_id}. Run a normal export first."
        )

    pages: dict[str, PageNode] = state["pages"]
    effective_pages_dir_name = root_pages_dir_name(root_page_id) if pages_dir_name is None else pages_dir_name
    effective_manifest_name = root_manifest_name(root_page_id) if manifest_name is None else manifest_name
    effective_page_paths: dict[str, str | Path] = dict(state.get("page_paths") or {})
    if page_path_overrides:
        effective_page_paths.update(page_path_overrides)
    feed_entries = fetch_rss_entries(session, rss_url)
    updated_page_ids: list[str] = []
    skipped_page_ids: list[str] = []
    ignored_page_ids: list[str] = []
    change_records: list[dict[str, Any]] = []

    for entry in feed_entries:
        entry_time = parse_iso_datetime(entry.updated_at) or parse_iso_datetime(entry.published_at)
        if updated_since is not None and (entry_time is None or entry_time < updated_since):
            ignored_page_ids.append(entry.page_id)
            continue
        existing_page = pages.get(entry.page_id)
        if existing_page is None:
            if not include_new:
                ignored_page_ids.append(entry.page_id)
                continue
            depth = 0
        else:
            if not feed_entry_is_newer(entry, existing_page):
                skipped_page_ids.append(entry.page_id)
                continue
            depth = existing_page.depth

        if existing_page is not None and entry.page_id not in effective_page_paths:
            old_path = build_page_paths(
                {entry.page_id: existing_page},
                output_dir,
                pages_dir_name=effective_pages_dir_name,
            )[entry.page_id]
            effective_page_paths[entry.page_id] = path_relative_to_base(old_path, output_dir)

        if dry_run:
            new_page = PageNode(
                page_id=entry.page_id,
                title=entry.title or (existing_page.title if existing_page is not None else entry.page_id),
                url=entry.url or page_url_from_api(site_base, entry.page_id),
                depth=depth,
                html="",
                author=existing_page.author if existing_page is not None else "",
                last_editor=existing_page.last_editor if existing_page is not None else "",
                created_at=existing_page.created_at if existing_page is not None else "",
                updated_at=entry.updated_at or (existing_page.updated_at if existing_page is not None else ""),
                version_number=entry.version_number or 0,
            )
        else:
            new_page = fetch_page(session, site_base, entry.page_id, depth=depth)
            if not page_matches_updated_since(new_page, updated_since):
                ignored_page_ids.append(entry.page_id)
                continue
            pages[entry.page_id] = new_page
        new_path = build_page_paths(
            {entry.page_id: new_page},
            output_dir,
            pages_dir_name=effective_pages_dir_name,
            page_path_overrides=effective_page_paths,
        )[entry.page_id]
        if not dry_run:
            effective_page_paths[entry.page_id] = path_relative_to_base(new_path, output_dir)
        change_records.append(
            {
                "root_page_id": root_page_id,
                "page_id": entry.page_id,
                "title": new_page.title,
                "change_type": "new" if existing_page is None else "updated",
                "old_title": existing_page.title if existing_page is not None else None,
                "new_title": new_page.title,
                "old_version": existing_page.version_number if existing_page is not None else None,
                "new_version": new_page.version_number if new_page.version_number else entry.version_number,
                "old_updated_at": existing_page.updated_at if existing_page is not None else None,
                "new_updated_at": new_page.updated_at,
                "raw_path": str(new_path),
                "raw_relative_path": path_relative_to_base(new_path, output_dir),
                "source_url": new_page.url,
                "needs_postprocess": True,
                "detected_from": "rss",
                "rss_entry_title": entry.title,
                "rss_entry_url": entry.url,
                "rss_entry_updated_at": entry.updated_at,
                "rss_entry_version": entry.version_number,
            }
        )
        updated_page_ids.append(entry.page_id)

    if updated_page_ids and not dry_run:
        saved_page_paths = complete_page_path_overrides(
            pages,
            output_dir,
            pages_dir_name=effective_pages_dir_name,
            page_path_overrides=effective_page_paths,
        )
        save_progress_state(
            progress_file,
            root_page_id=root_page_id,
            depth_limit=depth_limit,
            pages=pages,
            queue=deque(),
            enqueued=set(pages.keys()),
            page_paths=saved_page_paths,
        )
        write_root_export(
            root_page_id,
            pages,
            output_dir,
            session,
            pages_dir_name=effective_pages_dir_name,
            manifest_name=effective_manifest_name,
            page_path_overrides=saved_page_paths,
            manifest_dir=metadata_dir,
        )

    report_path = str((change_report_dir or default_change_report_dir(output_dir)) / "latest.json")
    if write_report:
        write_update_change_report(
            output_dir=output_dir,
            report_dir=change_report_dir or default_change_report_dir(output_dir),
            root_page_id=root_page_id,
            rss_url=rss_url,
            scanned_count=len(feed_entries),
            changed_pages=change_records,
            skipped_page_ids=skipped_page_ids,
            ignored_page_ids=ignored_page_ids,
            dry_run=dry_run,
        )

    return UpdateResult(
        root_page_id=root_page_id,
        scanned_count=len(feed_entries),
        updated_page_ids=updated_page_ids,
        skipped_page_ids=skipped_page_ids,
        ignored_page_ids=ignored_page_ids,
        change_records=change_records,
        change_report_path=report_path,
        dry_run=dry_run,
    )


def export_state_path(metadata_dir: Path) -> Path:
    return metadata_dir / "export-state.json"


def load_export_state(metadata_dir: Path, *, raw_output_dir: Optional[Path] = None) -> dict[str, Any]:
    path = export_state_path(metadata_dir)
    if not path.is_file() and raw_output_dir is not None:
        legacy = raw_output_dir / "export-state.json"
        if legacy.is_file():
            path = legacy
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_export_state(metadata_dir: Path, root_states: list[dict[str, Any]]) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": EXPORT_STATE_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "roots": root_states,
    }
    export_state_path(metadata_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def project_root_for_output(output_dir: Path) -> Optional[Path]:
    if output_dir.name == "raw":
        return output_dir.parent
    return None


def relative_to_project(path: Path, project: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_upstream_wiki_sources(
    *,
    output_dir: Path,
    metadata_dir: Path,
    root_states: list[dict[str, Any]],
    updated_since: Optional[str] = None,
) -> None:
    project = project_root_for_output(output_dir)
    if project is None:
        return

    upstream_dir = project / "upstream"
    upstream_dir.mkdir(parents=True, exist_ok=True)
    config_path = upstream_dir / "wiki-sources.json"
    existing = load_json(config_path, {})
    existing_sources = existing.get("sources") if isinstance(existing, dict) else None
    by_page_id: dict[str, dict[str, Any]] = {}
    if isinstance(existing_sources, list):
        for item in existing_sources:
            if isinstance(item, dict) and str(item.get("page_id") or "").strip():
                by_page_id[str(item["page_id"])] = dict(item)
    existing_page_ids = set(by_page_id)

    for root_state in root_states:
        page_id = str(root_state.get("page_id") or "").strip()
        if not page_id:
            continue
        source = by_page_id.get(page_id, {})
        relationship = source.get("relationship")
        if not isinstance(relationship, dict):
            relationship = {"role": "primary" if not existing_page_ids and not by_page_id else "additional"}
        filters = source.get("filters")
        filters = dict(filters) if isinstance(filters, dict) else {}
        legacy_updated_since = str(source.pop("updated_since", "") or "").strip()
        if legacy_updated_since and not str(filters.get("updated_since") or "").strip():
            filters["updated_since"] = legacy_updated_since
        source.update(
            {
                "type": "confluence",
                "enabled": source.get("enabled", True),
                "source_id": source.get("source_id") or f"cwiki-{page_id}",
                "relationship": relationship,
                "page_id": page_id,
                "url": str(root_state.get("url") or ""),
                "site_base": str(root_state.get("site_base") or ""),
                "depth": int(root_state.get("depth_limit", 0) or 0),
                "weekly_from_title": str(root_state.get("weekly_from_title") or ""),
                "space_key": str(root_state.get("space_key") or ""),
                "rss_url": str(root_state.get("rss_url") or ""),
                "rss_url_is_custom": bool(root_state.get("rss_url_is_custom", False)),
                "rss_max_results": int(root_state.get("rss_max_results", DEFAULT_RSS_MAX_RESULTS) or DEFAULT_RSS_MAX_RESULTS),
                "output_dir": relative_to_project(output_dir, project),
                "metadata_dir": relative_to_project(metadata_dir, project),
            }
        )
        if updated_since:
            filters["updated_since"] = updated_since
        if filters:
            source["filters"] = filters
        by_page_id[page_id] = source

    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [by_page_id[key] for key in sorted(by_page_id)],
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scan_existing_flat_export_pages(output_dir: Path, site_base: str = "") -> tuple[dict[str, PageNode], dict[str, str]]:
    pages: dict[str, PageNode] = {}
    page_paths: dict[str, str] = {}
    for index_path in sorted(output_dir.glob("*/index.md")):
        if not index_path.is_file():
            continue
        content = index_path.read_text(encoding="utf-8")
        page_id = parse_frontmatter_value(content, "page_id").strip()
        if not page_id:
            continue
        title = parse_frontmatter_value(content, "title").strip() or index_path.parent.name
        source_url = parse_frontmatter_value(content, "source_url").strip()
        if not source_url and site_base:
            source_url = page_url_from_api(site_base, page_id)
        version_text = parse_frontmatter_value(content, "version_number").strip()
        try:
            version_number = int(version_text) if version_text else 0
        except ValueError:
            version_number = 0
        pages[page_id] = PageNode(
            page_id=page_id,
            title=title,
            url=source_url,
            depth=0,
            html="",
            author=parse_frontmatter_value(content, "author"),
            last_editor=parse_frontmatter_value(content, "last_editor"),
            created_at=parse_frontmatter_value(content, "created_at"),
            updated_at=parse_frontmatter_value(content, "updated_at"),
            version_number=version_number,
        )
        page_paths[page_id] = path_relative_to_base(index_path, output_dir)
    return pages, page_paths


def clone_pages_for_root(
    pages: dict[str, PageNode],
    *,
    root_page_id: str,
    depth_limit: int,
) -> dict[str, PageNode]:
    root_pages: dict[str, PageNode] = {}
    for page_id, page in pages.items():
        cloned = page_node_from_dict(page_node_to_dict(page))
        cloned.depth = 0 if page_id == root_page_id else depth_limit
        root_pages[page_id] = cloned
    return root_pages


def initialize_existing_export_state(
    output_dir: Path,
    root_specs: list[RootSpec],
    *,
    rss_max_results: int,
    rss_url_entries: list[str],
    metadata_dir: Path,
) -> list[dict[str, Any]]:
    if not root_specs:
        raise RuntimeError("At least one --url root is required for --init-from-existing.")
    output_dir.mkdir(parents=True, exist_ok=True)
    pages, page_paths = scan_existing_flat_export_pages(output_dir, root_specs[0].site_base)
    if not pages:
        raise RuntimeError(f"No existing wiki pages found under {output_dir}/*/index.md.")

    overrides = rss_url_overrides(rss_url_entries)
    root_states: list[dict[str, Any]] = []
    for index, root_spec in enumerate(root_specs):
        if root_spec.page_id not in pages:
            raise RuntimeError(
                f"Root page {root_spec.page_id} was not found in existing raw export {output_dir}."
            )
        root_pages = clone_pages_for_root(
            pages,
            root_page_id=root_spec.page_id,
            depth_limit=root_spec.depth_limit,
        )
        save_progress_state(
            root_progress_file_path(metadata_dir, root_spec.page_id),
            root_page_id=root_spec.page_id,
            depth_limit=root_spec.depth_limit,
            pages=root_pages,
            queue=deque(),
            enqueued=set(root_pages.keys()),
            page_paths=page_paths,
        )
        rss_url = overrides.get(root_spec.page_id) or overrides.get(str(index)) or ""
        root_states.append(
            {
                "page_id": root_spec.page_id,
                "url": root_spec.url,
                "site_base": root_spec.site_base,
                "depth_limit": root_spec.depth_limit,
                "weekly_from_title": root_spec.weekly_from_title,
                "space_key": "",
                "rss_url": rss_url,
                "rss_url_is_custom": bool(rss_url),
                "rss_max_results": rss_max_results,
                "pages_dir_name": "",
                "manifest_name": root_manifest_name(root_spec.page_id),
                "page_path_overrides": page_paths,
                "page_count": len(root_pages),
                "imported_from_existing": True,
                "imported_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    save_export_state(metadata_dir, root_states)
    return root_states


def rss_url_overrides(entries: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for index, entry in enumerate(entries):
        page_id, separator, value = entry.partition("=")
        if separator and page_id.strip().isdigit() and value.strip():
            overrides[page_id.strip()] = normalize_user_url(value)
        else:
            overrides[str(index)] = normalize_user_url(entry)
    return overrides


def root_states_from_specs(
    session: requests.Session,
    root_specs: list[RootSpec],
    *,
    rss_max_results: int,
    rss_url_entries: list[str],
) -> list[dict[str, Any]]:
    overrides = rss_url_overrides(rss_url_entries)
    root_states: list[dict[str, Any]] = []
    for index, root_spec in enumerate(root_specs):
        space_key = fetch_page_space_key(session, root_spec.site_base, root_spec.page_id)
        rss_url = overrides.get(root_spec.page_id) or overrides.get(str(index))
        rss_url_is_custom = bool(rss_url)
        if not rss_url:
            rss_url = build_rss_feed_url(
                root_spec.site_base,
                space_key,
                max_results=rss_max_results,
            )
        root_states.append(
            {
                "page_id": root_spec.page_id,
                "url": root_spec.url,
                "site_base": root_spec.site_base,
                "depth_limit": root_spec.depth_limit,
                "weekly_from_title": root_spec.weekly_from_title,
                "space_key": space_key,
                "rss_url": rss_url,
                "rss_url_is_custom": rss_url_is_custom,
                "rss_max_results": rss_max_results,
                "pages_dir_name": root_pages_dir_name(root_spec.page_id),
                "manifest_name": root_manifest_name(root_spec.page_id),
            }
        )
    return root_states


def root_states_from_saved_state(metadata_dir: Path, *, raw_output_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    payload = load_export_state(metadata_dir, raw_output_dir=raw_output_dir)
    roots = payload.get("roots") or []
    if not isinstance(roots, list):
        return []
    return [root for root in roots if isinstance(root, dict)]


def main() -> int:
    args = parse_args()
    auth_env = load_auth_env_file()
    if not str(getattr(args, "cookie", "") or "").strip() and auth_env.get("COOKIE_HEADER"):
        args.cookie = auth_env["COOKIE_HEADER"]
    updated_since = parse_updated_since(args.updated_since)
    if not args.url and not args.update:
        raise SystemExit("--url is required unless --update is used with a saved output directory.")
    weekly_from_map = parse_page_value_args(args.weekly_from)
    depth_map = parse_page_int_args(args.depth_for)
    output_dir = Path(args.output_dir).expanduser().resolve()
    metadata_dir = resolve_metadata_dir(output_dir, args.metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    if args.init_from_existing:
        if not args.url:
            raise SystemExit("--url is required with --init-from-existing.")
        root_specs = build_root_specs(args.url, weekly_from_map, depth_map, args.depth)
        root_states = initialize_existing_export_state(
            output_dir,
            root_specs,
            rss_max_results=args.rss_max_results or DEFAULT_RSS_MAX_RESULTS,
            rss_url_entries=args.rss_url,
            metadata_dir=metadata_dir,
        )
        write_upstream_wiki_sources(
            output_dir=output_dir,
            metadata_dir=metadata_dir,
            root_states=root_states,
            updated_since=args.updated_since.strip(),
        )
        total_pages = sum(int(root_state.get("page_count", 0) or 0) for root_state in root_states)
        print(
            f"Initialized update state for {total_pages} existing pages "
            f"across {len(root_states)} roots under {output_dir} "
            f"(metadata: {metadata_dir})"
        )
        return 0

    try:
        resolved_cookie = resolve_cookie_header(
            args.cookie,
            sso_skill_root=args.sso_skill_root,
            auto_cookie_from_sso=bool(args.auto_cookie_from_sso),
        )
    except RuntimeError as exc:
        raise SystemExit(cookie_refresh_help(str(exc))) from exc
    session = build_session(resolved_cookie, args.timeout)
    session.request_interval = args.request_interval
    session.jira_token = args.jira_token.strip()
    session.jira_cookie = args.jira_cookie.strip()
    try:
        session.jira_chdsso = resolve_jira_chdsso(
            args.jira_chdsso,
            sso_skill_root=args.sso_skill_root,
            auto_jira_chdsso_from_sso=bool(args.auto_jira_chdsso_from_sso),
            jira_chdsso_env=args.jira_chdsso_env,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Failed to resolve Jira CHDSSO: {exc}") from exc

    if args.update:
        if args.url:
            root_specs = build_root_specs(args.url, weekly_from_map, depth_map, args.depth)
            root_states = root_states_from_specs(
                session,
                root_specs,
                rss_max_results=args.rss_max_results,
                rss_url_entries=args.rss_url,
            )
        else:
            root_states = root_states_from_saved_state(metadata_dir, raw_output_dir=output_dir)
            if not root_states:
                raise SystemExit(
                    f"No export-state.json found in {metadata_dir} (or legacy {output_dir / 'export-state.json'}). "
                    "Run a normal export first, or pass --url with --update."
                )
            overrides = rss_url_overrides(args.rss_url)
            for index, root_state in enumerate(root_states):
                root_page_id = str(root_state.get("page_id") or "")
                override = overrides.get(root_page_id) or overrides.get(str(index))
                if override:
                    root_state["rss_url"] = override
                    root_state["rss_url_is_custom"] = True

        total_scanned = 0
        total_updated = 0
        all_changed_pages: list[dict[str, Any]] = []
        all_skipped_page_ids: list[str] = []
        all_ignored_page_ids: list[str] = []
        root_summaries: list[dict[str, Any]] = []
        change_report_dir = (
            Path(args.change_report_dir).expanduser().resolve()
            if args.change_report_dir.strip()
            else default_change_report_dir(output_dir)
        )
        for root_state in root_states:
            root_page_id = str(root_state["page_id"])
            site_base = str(root_state["site_base"])
            depth_limit = int(root_state.get("depth_limit", args.depth))
            rss_url = str(root_state.get("rss_url") or "")
            rss_max_results = resolve_rss_max_results(root_state, args.rss_max_results)
            if not rss_url:
                space_key = str(root_state.get("space_key") or "")
                if not space_key:
                    space_key = fetch_page_space_key(session, site_base, root_page_id)
                    root_state["space_key"] = space_key
                rss_url = build_rss_feed_url(
                    site_base,
                    space_key,
                    max_results=rss_max_results,
                )
                root_state["rss_url_is_custom"] = False
            else:
                rss_url = update_rss_url_max_results(rss_url, rss_max_results)
            root_state["rss_url"] = rss_url
            root_state["rss_max_results"] = rss_max_results
            root_state["rss_max_results_mode"] = "fixed" if args.rss_max_results > 0 else "auto"
            result = update_root_from_rss(
                session,
                root_page_id=root_page_id,
                site_base=site_base,
                output_dir=output_dir,
                metadata_dir=metadata_dir,
                depth_limit=depth_limit,
                rss_url=rss_url,
                include_new=args.rss_include_new,
                dry_run=args.dry_run,
                pages_dir_name=str(root_state["pages_dir_name"]) if "pages_dir_name" in root_state else None,
                manifest_name=str(root_state["manifest_name"]) if "manifest_name" in root_state else None,
                page_path_overrides=(
                    root_state.get("page_path_overrides")
                    if isinstance(root_state.get("page_path_overrides"), dict)
                    else None
                ),
                change_report_dir=change_report_dir,
                write_report=False,
                updated_since=updated_since,
            )
            total_scanned += result.scanned_count
            total_updated += len(result.updated_page_ids)
            all_changed_pages.extend(result.change_records)
            all_skipped_page_ids.extend(f"{root_page_id}:{page_id}" for page_id in result.skipped_page_ids)
            all_ignored_page_ids.extend(f"{root_page_id}:{page_id}" for page_id in result.ignored_page_ids)
            root_summaries.append(
                {
                    "root_page_id": root_page_id,
                    "rss_url": rss_url,
                    "rss_max_results": rss_max_results,
                    "rss_max_results_mode": root_state["rss_max_results_mode"],
                    "scanned_count": result.scanned_count,
                    "changed_count": len(result.updated_page_ids),
                    "skipped_count": len(result.skipped_page_ids),
                    "ignored_count": len(result.ignored_page_ids),
                    "updated_page_ids": result.updated_page_ids,
                }
            )
            root_state["last_update_at"] = datetime.now(timezone.utc).isoformat()
            root_state["last_update_scanned_count"] = result.scanned_count
            root_state["last_update_page_ids"] = result.updated_page_ids
            root_state["last_update_changed_pages"] = result.change_records
            root_state["last_update_report_path"] = str(change_report_dir / "latest.json")
            root_state["last_update_dry_run"] = result.dry_run
            root_state["last_update_rss_max_results"] = rss_max_results
            refreshed_state = load_progress_state(
                resolve_existing_progress_file(metadata_dir, output_dir, root_page_id),
                root_page_id=root_page_id,
                depth_limit=depth_limit,
            )
            if refreshed_state is not None:
                root_state["page_count"] = len(refreshed_state["pages"])
                root_state["page_path_overrides"] = refreshed_state.get("page_paths", {})
        write_update_change_report(
            output_dir=output_dir,
            report_dir=change_report_dir,
            root_page_id=str(root_states[0]["page_id"]) if len(root_states) == 1 else "multiple",
            rss_url=str(root_states[0].get("rss_url") or "") if len(root_states) == 1 else "",
            scanned_count=total_scanned,
            changed_pages=all_changed_pages,
            skipped_page_ids=all_skipped_page_ids,
            ignored_page_ids=all_ignored_page_ids,
            dry_run=args.dry_run,
            root_summaries=root_summaries,
        )
        if not args.dry_run:
            save_export_state(metadata_dir, root_states)
            write_upstream_wiki_sources(
                output_dir=output_dir,
                metadata_dir=metadata_dir,
                root_states=root_states,
                updated_since=args.updated_since.strip(),
            )
        print(
            f"{'Detected' if args.dry_run else 'Updated'} {total_updated} pages from {total_scanned} RSS entries "
            f"across {len(root_states)} roots in {output_dir} (metadata: {metadata_dir})"
        )
        return 0

    root_specs = build_root_specs(args.url, weekly_from_map, depth_map, args.depth)
    for root_spec in root_specs:
        progress_file = root_progress_file_path(metadata_dir, root_spec.page_id)
        root_pages = crawl_pages(
            session,
            root_spec.site_base,
            root_spec.page_id,
            depth_limit=root_spec.depth_limit,
            progress_file=progress_file,
            max_pages=args.max_pages,
            depth_one_child_filter=build_depth_one_child_filter(root_spec.weekly_from_title),
        )
        root_pages = filter_pages_by_updated_since(root_pages, updated_since)
        write_root_export(
            root_spec.page_id,
            root_pages,
            output_dir,
            session,
            manifest_dir=metadata_dir,
        )

    root_states = root_states_from_specs(
        session,
        root_specs,
        rss_max_results=args.rss_max_results or DEFAULT_RSS_MAX_RESULTS,
        rss_url_entries=args.rss_url,
    )
    save_export_state(metadata_dir, root_states)
    write_upstream_wiki_sources(
        output_dir=output_dir,
        metadata_dir=metadata_dir,
        root_states=root_states,
        updated_since=args.updated_since.strip(),
    )

    total_pages = 0
    for root_spec in root_specs:
        progress_file = resolve_existing_progress_file(metadata_dir, output_dir, root_spec.page_id)
        state = load_progress_state(
            progress_file,
            root_page_id=root_spec.page_id,
            depth_limit=root_spec.depth_limit,
        )
        if state is not None:
            total_pages += len(state["pages"])
    print(
        f"Exported {total_pages} pages across {len(root_specs)} roots to {output_dir} "
        f"(metadata: {metadata_dir})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WikiAuthenticationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
