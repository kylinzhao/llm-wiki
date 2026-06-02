#!/usr/bin/env python3
"""Track source-page Cjira bindings and document state."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests


ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")
CJIRA_URL_RE = re.compile(r"https?://cjira\.guazi-corp\.com/browse/(?P<key>[A-Z][A-Z0-9_]+-\d+)")
LEGACY_PROJECT_JIRA_URL_RE = re.compile(
    r"https?://project\.guazi-corp\.com/browse/(?P<key>[A-Z][A-Z0-9_]+-\d+)"
)
STRONG_IDEA_RE = re.compile(r"【\s*IDEA\s*】", re.IGNORECASE)
FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*['\"]?(.*?)['\"]?\s*$", re.M)
SOFT_IDEA_PHRASES = (
    "概念探索",
    "方案预研",
    "候选方向",
    "未来可能立项",
    "不代表已经承诺上线",
    "探索",
    "预研",
    "idea",
)
SUPPORTING_CONTEXT_MARKERS = ("【jira", "jira 编号", "jira编号", "jira编号】", "jira编号】", "jira 编号】")
PRIMARY_CONTEXT_MARKERS = ("文档记录", "修改内容", "| cjira |", "| jira |", "revision")
DEFAULT_TERMINAL_STATUSES = {
    "done",
    "closed",
    "resolved",
    "已完成",
    "已上线",
    "已关闭",
    "已解决",
}
AUTH_ENV_FILE = Path(os.environ.get("LLM_WIKI_AUTH_ENV_FILE", "~/.llm-wiki/guazi-sso.env")).expanduser()
SSO_SKILL_CANDIDATES = (
    Path(__file__).with_name("guazi-sso-login"),
    Path("~/.codex/skills/guazi-sso-login").expanduser(),
)
ASSET_LINE_MARKERS = ("assets/", "<img", "![", "src=")
ASSET_FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _looks_like_asset_reference(line: str, issue_key: str) -> bool:
    lowered = line.lower()
    if not any(marker in lowered for marker in ASSET_LINE_MARKERS):
        return False
    if issue_key.lower() in lowered and any(suffix in lowered for suffix in ASSET_FILE_SUFFIXES):
        return True
    return False


def _is_valid_plain_issue_match(text: str, match: re.Match[str], issue_key: str) -> bool:
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    if _looks_like_asset_reference(line, issue_key):
        return False
    prev_char = text[match.start() - 1] if match.start() > 0 else ""
    next_char = text[match.end()] if match.end() < len(text) else ""
    if prev_char == "/" or next_char in {".", "/"}:
        return False
    if next_char == "-" and any(suffix in line.lower() for suffix in ASSET_FILE_SUFFIXES):
        return False
    return True


def extract_issue_candidates(text: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    candidates: list[dict[str, object]] = []
    lines = text.splitlines()
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1

    def line_index_for(position: int) -> int:
        index = 0
        for current, start in enumerate(line_offsets):
            if start > position:
                break
            index = current
        return index

    url_matches = [(match, True, False) for match in CJIRA_URL_RE.finditer(text)]
    legacy_url_matches = [(match, True, True) for match in LEGACY_PROJECT_JIRA_URL_RE.finditer(text)]
    plain_matches = [(match, False, False) for match in ISSUE_KEY_RE.finditer(text)]
    for match, from_url, legacy_project_jira_reference in url_matches + legacy_url_matches + plain_matches:
        issue_key = match.group("key") if from_url else match.group(0)
        if not from_url and not _is_valid_plain_issue_match(text, match, issue_key):
            continue
        if issue_key in seen:
            continue
        seen.add(issue_key)
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        anchor = text[start:end].replace("\n", " ").strip()
        line_index = line_index_for(match.start())
        nearby_lines = " ".join(lines[max(0, line_index - 2) : line_index + 1]).lower()
        local_context = text[start:end].lower()
        role = "primary"
        score = 1
        if any(marker in nearby_lines for marker in SUPPORTING_CONTEXT_MARKERS):
            role = "supporting"
            score = 0
        elif any(marker in local_context for marker in PRIMARY_CONTEXT_MARKERS):
            score = 3
        elif not candidates:
            score = 2
        candidates.append(
            {
                "issue_key": issue_key,
                "source_anchor": anchor,
                "role": role,
                "score": score,
                "offset": match.start(),
                "legacy_project_jira_reference": legacy_project_jira_reference,
            }
        )
    return candidates


def detect_idea(title: str, text: str) -> dict[str, object]:
    if STRONG_IDEA_RE.search(title):
        return {"idea_flag": True, "confidence": "high", "doc_status": "idea"}
    lowered = f"{title}\n{text}".lower()
    hits = sum(1 for phrase in SOFT_IDEA_PHRASES if phrase.lower() in lowered)
    if hits >= 2:
        return {"idea_flag": True, "confidence": "medium", "doc_status": "idea"}
    return {"idea_flag": False, "confidence": "high", "doc_status": "in_progress"}


def classify_page(title: str, raw_path: str, text: str) -> dict[str, object]:
    candidates = extract_issue_candidates(text)
    primary_candidates = [item for item in candidates if item["role"] == "primary"]
    supporting = [str(item["issue_key"]) for item in candidates if item["role"] == "supporting"]

    primary_cjira = ""
    source_anchor = ""
    confidence = "high"
    if primary_candidates:
        primary_candidates = sorted(primary_candidates, key=lambda item: (-int(item["score"]), int(item["offset"])))
        primary = primary_candidates[0]
        primary_cjira = str(primary["issue_key"])
        source_anchor = str(primary["source_anchor"])
        primary_legacy_project_jira_reference = bool(primary.get("legacy_project_jira_reference"))
        if len(primary_candidates) > 1:
            confidence = "low"
            supporting.extend(str(item["issue_key"]) for item in primary_candidates[1:] if str(item["issue_key"]) not in supporting)
    else:
        primary_legacy_project_jira_reference = False

    idea = detect_idea(title, text)
    if idea["idea_flag"]:
        confidence = str(idea["confidence"])

    return {
        "page_id": "",
        "page_path": raw_path,
        "title": title,
        "doc_status": idea["doc_status"],
        "primary_cjira": primary_cjira,
        "supporting_cjira": supporting,
        "idea_flag": idea["idea_flag"],
        "status_source": "cjira" if primary_cjira else ("idea" if idea["idea_flag"] else "none"),
        "primary_cjira_status": "",
        "primary_cjira_terminal": False,
        "primary_cjira_legacy_project_jira_reference": primary_legacy_project_jira_reference,
        "last_checked_at": "",
        "source_anchor": source_anchor,
        "confidence": confidence,
    }


def normalize_status(value: str) -> str:
    return value.strip().lower()


def is_terminal_status(status: str, terminal_statuses: set[str] | None = None) -> bool:
    allowed = terminal_statuses or DEFAULT_TERMINAL_STATUSES
    return normalize_status(status) in {normalize_status(item) for item in allowed}


def fetch_jira_status(
    issue_key: str,
    *,
    jira_base: str,
    headers: dict[str, str],
    session: requests.Session,
) -> dict[str, object]:
    url = jira_base.rstrip("/") + f"/rest/api/2/issue/{issue_key}"
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    status = str((((payload.get("fields") or {}).get("status") or {}).get("name")) or "")
    return {
        "issue_key": issue_key,
        "status": status,
        "terminal": is_terminal_status(status),
        "last_checked_at": utc_now(),
    }


def legacy_project_jira_reference_status(issue_key: str) -> dict[str, object]:
    return {
        "issue_key": issue_key,
        "status": "已上线（legacy project Jira reference）",
        "terminal": True,
        "last_checked_at": utc_now(),
        "status_source": "legacy_project_jira_reference",
        "legacy_project_jira_reference": True,
    }


def registry_dir(project: Path) -> Path:
    return project / "staging" / "cjira-registry"


def _read_registry_payload(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records = payload.get("records") if isinstance(payload, dict) else []
    return [item for item in records if isinstance(item, dict)]


def read_registry(project: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    root = registry_dir(project)
    cache_path = root / "cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    except json.JSONDecodeError:
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    return (
        _read_registry_payload(root / "active.json"),
        _read_registry_payload(root / "archive.json"),
        cache,
    )


def write_registry(
    project: Path,
    active: list[dict[str, object]],
    archive: list[dict[str, object]],
    cache: dict[str, object],
) -> None:
    root = registry_dir(project)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        root / "active.json": {"generated_at": utc_now(), "records": active},
        root / "archive.json": {"generated_at": utc_now(), "records": archive},
        root / "cache.json": cache,
    }
    for path, payload in payloads.items():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_page_path_for(project: Path, raw_path: str) -> Path | None:
    source_dir = project / "wiki" / "sources"
    if not source_dir.is_dir():
        return None
    for path in source_dir.glob("*.md"):
        if path.name == "index.md" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"## Source Metadata\s*```json\s*(\{.*?\})\s*```", text, re.S)
        if match:
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                payload = {}
            raw_rel = payload.get("raw_rel") if isinstance(payload, dict) else None
            if isinstance(raw_rel, str) and raw_rel.strip() == raw_path:
                return path
        raw_match = re.search(r"(?:Raw path|原始路径):\s*`([^`]+)`", text)
        if raw_match and raw_match.group(1).strip() == raw_path:
            return path
    return None


def _replace_or_insert_section(text: str, heading: str, block: str, *, before_headings: tuple[str, ...] = ()) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\n.*?(?=^## |\Z)")
    replacement = block.rstrip() + "\n\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    for marker in before_headings:
        needle = f"## {marker}"
        idx = text.find(needle)
        if idx != -1:
            return text[:idx].rstrip() + "\n\n" + replacement + text[idx:]
    return text.rstrip() + "\n\n" + replacement


def sync_record_to_source_page(project: Path, record: dict[str, object]) -> None:
    raw_path = str(record.get("page_path") or "")
    if not raw_path:
        return
    page = source_page_path_for(project, raw_path)
    if page is None or not page.is_file():
        return
    text = page.read_text(encoding="utf-8", errors="replace")
    supporting = ", ".join(f"`{key}`" for key in (record.get("supporting_cjira") or [])) or "`none`"
    delivery_block = (
        "## Delivery Tracking\n\n"
        f"- Primary Jira: `{str(record.get('primary_cjira') or 'none')}`\n"
        f"- Supporting Jira: {supporting}\n"
        f"- Jira Status: `{str(record.get('primary_cjira_status') or '')}`\n"
        f"- Jira Status Source: `{str(record.get('status_source') or '')}`\n"
        f"- Last Checked: `{str(record.get('last_checked_at') or '')}`\n"
        f"- Confidence: `{str(record.get('confidence') or 'high')}`\n"
    )
    text = _replace_or_insert_section(text, "Delivery Tracking", delivery_block, before_headings=("Summary", "摘要"))

    metadata_match = re.search(r"## Source Metadata\s*```json\s*(\{.*?\})\s*```", text, re.S)
    metadata: dict[str, object] = {}
    if metadata_match:
        try:
            payload = json.loads(metadata_match.group(1))
            if isinstance(payload, dict):
                metadata = dict(payload)
        except json.JSONDecodeError:
            metadata = {}
    metadata.update(
        {
            "page_id": str(record.get("page_id") or metadata.get("page_id") or ""),
            "raw_rel": raw_path,
            "primary_cjira": str(record.get("primary_cjira") or ""),
            "supporting_cjira": list(record.get("supporting_cjira") or []),
            "primary_cjira_status": str(record.get("primary_cjira_status") or ""),
            "cjira_status_source": str(record.get("status_source") or ""),
            "primary_cjira_legacy_project_jira_reference": bool(
                record.get("primary_cjira_legacy_project_jira_reference")
            ),
            "last_checked_at": str(record.get("last_checked_at") or ""),
            "cjira_confidence": str(record.get("confidence") or "high"),
        }
    )
    metadata_block = "## Source Metadata\n```json\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n```\n"
    text = _replace_or_insert_section(text, "Source Metadata", metadata_block)
    page.write_text(text, encoding="utf-8")


def _classify_source(source: dict[str, object], project: Path) -> dict[str, object]:
    text = str(source.get("text") or "")
    if not text:
        raw_path = str(source.get("raw_path") or "")
        source_file = project / raw_path
        if source_file.is_file():
            text = source_file.read_text(encoding="utf-8", errors="replace")
    record = classify_page(
        str(source.get("title") or ""),
        str(source.get("raw_path") or ""),
        text,
    )
    record["page_id"] = str(source.get("page_id") or "")
    return record


def _apply_status(
    record: dict[str, object],
    cache: dict[str, object],
    *,
    status_by_key: dict[str, dict[str, object]] | None = None,
    jira_base: str = "https://cjira.guazi-corp.com",
    headers: dict[str, str] | None = None,
    session: requests.Session | None = None,
) -> dict[str, object]:
    issue_key = str(record.get("primary_cjira") or "")
    if not issue_key:
        return record
    status_info = (status_by_key or {}).get(issue_key)
    if status_info is None and session is not None and headers:
        try:
            status_info = fetch_jira_status(issue_key, jira_base=jira_base, headers=headers, session=session)
        except Exception:
            if record.get("primary_cjira_legacy_project_jira_reference"):
                status_info = legacy_project_jira_reference_status(issue_key)
            if status_info is None:
                cache[issue_key] = {
                    "issue_key": issue_key,
                    "status": "",
                    "terminal": False,
                    "last_checked_at": utc_now(),
                    "fetch_failed": True,
                    "legacy_project_jira_reference": False,
                }
                return record
    if status_info is None:
        status_info = {}
    status = str(status_info.get("status") or "")
    terminal = bool(status_info.get("terminal"))
    fetched_at = str(status_info.get("last_checked_at") or utc_now())
    status_source = str(status_info.get("status_source") or "cjira")
    cache[issue_key] = {
        "issue_key": issue_key,
        "status": status,
        "terminal": terminal,
        "last_checked_at": fetched_at,
        "fetch_failed": bool(status_info.get("fetch_failed")),
        "status_source": status_source,
    }
    if status_info.get("legacy_project_jira_reference"):
        cache[issue_key]["legacy_project_jira_reference"] = True
    record["primary_cjira_status"] = status
    record["primary_cjira_terminal"] = terminal
    record["last_checked_at"] = fetched_at
    record["status_source"] = status_source
    if terminal:
        record["doc_status"] = "frozen"
    elif not record["idea_flag"]:
        record["doc_status"] = "in_progress"
    return record


def update_registry_for_sources(
    project: Path,
    sources: list[dict[str, object]],
    refresh_status: bool = False,
    status_by_key: dict[str, dict[str, object]] | None = None,
    jira_base: str = "https://cjira.guazi-corp.com",
    headers: dict[str, str] | None = None,
    session: requests.Session | None = None,
) -> dict[str, object]:
    active_records, archive_records, cache = read_registry(project)
    _ = active_records
    archive_by_path = {str(item.get("page_path") or ""): item for item in archive_records}

    next_active: list[dict[str, object]] = []
    next_archive: list[dict[str, object]] = list(archive_records)
    archived_paths = set(archive_by_path)

    for source in sources:
        record = _classify_source(source, project)
        if refresh_status and record["primary_cjira"]:
            record = _apply_status(
                record,
                cache,
                status_by_key=status_by_key,
                jira_base=jira_base,
                headers=headers,
                session=session,
            )
        if record["doc_status"] == "frozen":
            if record["page_path"] in archived_paths:
                next_archive = [item for item in next_archive if str(item.get("page_path") or "") != record["page_path"]]
            next_archive.append(record)
            archived_paths.add(str(record["page_path"]))
            sync_record_to_source_page(project, record)
            continue
        next_active.append(record)
        sync_record_to_source_page(project, record)

    referenced_keys = {
        str(record.get("primary_cjira") or "")
        for record in [*next_active, *next_archive]
        if str(record.get("primary_cjira") or "")
    }
    cache = {
        key: value
        for key, value in cache.items()
        if key in referenced_keys
    }

    write_registry(project, next_active, next_archive, cache)
    return {
        "generated_at": utc_now(),
        "active_pages": len(next_active),
        "archived_pages": len(next_archive),
        "refreshed": refresh_status,
    }


def load_auth_env_file(path: Path | None = None) -> dict[str, str]:
    path = AUTH_ENV_FILE if path is None else path
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        try:
            parsed = shlex.split(value, posix=True)
            values[key] = parsed[0] if parsed else ""
        except ValueError:
            values[key] = value.strip().strip("'\"")
    return values


def apply_auth_env_defaults(args: argparse.Namespace) -> None:
    auth_env = load_auth_env_file()
    if not str(getattr(args, "jira_token", "") or "").strip() and auth_env.get("JIRA_TOKEN"):
        args.jira_token = auth_env["JIRA_TOKEN"]
    if not str(getattr(args, "jira_cookie", "") or "").strip():
        if auth_env.get("JIRA_COOKIE"):
            args.jira_cookie = auth_env["JIRA_COOKIE"]
        elif auth_env.get("COOKIE_HEADER"):
            args.jira_cookie = auth_env["COOKIE_HEADER"]


def discover_sso_skill_root() -> Path | None:
    for candidate in SSO_SKILL_CANDIDATES:
        if (candidate / "run.sh").is_file():
            return candidate
    return None


def resolve_jira_chdsso(
    jira_chdsso: str,
    *,
    auto_jira_chdsso_from_sso: bool,
    jira_chdsso_env: str,
) -> str:
    token = jira_chdsso.strip()
    if token:
        return token
    env = os.environ.get(jira_chdsso_env.strip(), "").strip()
    if env:
        return env
    auth_env = load_auth_env_file()
    if jira_chdsso_env.strip() in auth_env:
        return auth_env[jira_chdsso_env.strip()]
    if not auto_jira_chdsso_from_sso:
        return ""
    skill_root = discover_sso_skill_root()
    if skill_root is None:
        return ""
    result = subprocess.run(
        ["bash", str(skill_root / "run.sh"), "chdsso", "--env", jira_chdsso_env, "--validate", "--plain"],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def jira_headers(
    *,
    jira_token: str,
    jira_cookie: str,
    jira_chdsso: str,
) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if jira_token.strip():
        headers["Authorization"] = f"Bearer {jira_token.strip()}"
    if jira_cookie.strip():
        headers["Cookie"] = jira_cookie.strip()
    if jira_chdsso.strip():
        headers["chdsso"] = jira_chdsso.strip()
    return headers


def has_auth_headers(headers: dict[str, str]) -> bool:
    return any(key in headers for key in ("Authorization", "Cookie", "chdsso"))


def read_source_file(path: Path, project: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    title_match = FRONTMATTER_TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
    page_id_match = re.search(r"^page_id:\s*['\"]?(.*?)['\"]?\s*$", text, re.M)
    return {
        "title": title or path.stem,
        "page_id": page_id_match.group(1).strip() if page_id_match else "",
        "raw_path": path.relative_to(project).as_posix(),
        "text": text,
    }


def discover_project_sources(project: Path) -> list[dict[str, object]]:
    raw_dir = project / "raw"
    if not raw_dir.is_dir():
        return []
    return [
        read_source_file(path, project)
        for path in sorted(raw_dir.rglob("*.md"))
        if path.is_file()
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or refresh the Cjira registry.")
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--refresh", action="store_true", help="Refresh live Jira status when auth is available.")
    parser.add_argument("--jira-base", default="https://cjira.guazi-corp.com")
    parser.add_argument("--jira-token", default=os.environ.get("JIRA_TOKEN", ""))
    parser.add_argument("--jira-cookie", default=os.environ.get("COOKIE_HEADER", ""))
    parser.add_argument("--jira-chdsso", default="")
    parser.add_argument("--auto-jira-chdsso-from-sso", action="store_true")
    parser.add_argument("--jira-chdsso-env", default="GUAZI_CHDSSO_ONLINE")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_auth_env_defaults(args)
    project = Path(args.project).resolve()
    sources = discover_project_sources(project)
    resolved_chdsso = resolve_jira_chdsso(
        args.jira_chdsso,
        auto_jira_chdsso_from_sso=bool(args.auto_jira_chdsso_from_sso),
        jira_chdsso_env=args.jira_chdsso_env,
    )
    headers = jira_headers(
        jira_token=args.jira_token,
        jira_cookie=args.jira_cookie,
        jira_chdsso=resolved_chdsso,
    )
    session = requests.Session()
    can_refresh = has_auth_headers(headers)
    report = update_registry_for_sources(
        project,
        sources,
        refresh_status=bool(args.refresh and can_refresh),
        jira_base=args.jira_base,
        headers=headers,
        session=session,
    )
    if args.refresh and not can_refresh:
        report["warning"] = "Jira auth missing; registry written without live status refresh."
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
