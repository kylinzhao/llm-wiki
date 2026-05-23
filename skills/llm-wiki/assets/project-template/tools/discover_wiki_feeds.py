#!/usr/bin/env python3
"""Discover and verify RSS/Atom feeds for upstream wiki URLs."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


FEED_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/rdf+xml",
    "text/xml",
    "application/xml",
}

VERIFIED_STATUSES = {"discovered_verified", "provided_verified"}
NONBLOCKING_STATUSES = {"not_applicable"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def tag_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


class FeedLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.feed_links: list[str] = []
        self.space_key: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "link":
            rel = attr.get("rel", "").lower()
            media_type = attr.get("type", "").lower()
            href = attr.get("href", "")
            if href and "alternate" in rel and (
                media_type in FEED_TYPES or "rss" in href.lower() or "feed" in href.lower()
            ):
                self.feed_links.append(href)
        if tag.lower() == "meta":
            name = attr.get("name", "").lower()
            if name in {"ajs-space-key", "space-key", "spacekey"} and attr.get("content"):
                self.space_key = attr["content"].strip()
        if not self.space_key:
            for key in ("data-space-key", "data-spacekey"):
                if attr.get(key):
                    self.space_key = attr[key].strip()
                    break


def load_bytes(url: str, timeout: float, limit: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "llm-wiki-feed-discovery/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(limit + 1)
            return {
                "ok": True,
                "status_code": getattr(response, "status", 200),
                "final_url": response.geturl(),
                "content_type": response.headers.get("content-type", ""),
                "body": body[:limit],
                "truncated": len(body) > limit,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(limit + 1)
        return {
            "ok": False,
            "status_code": exc.code,
            "final_url": exc.geturl(),
            "content_type": exc.headers.get("content-type", "") if exc.headers else "",
            "body": body[:limit],
            "truncated": len(body) > limit,
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "status_code": None, "final_url": url, "content_type": "", "body": b"", "error": str(exc)}


def looks_auth_required(body: bytes, status_code: int | None) -> bool:
    if status_code in {401, 403}:
        return True
    text = body[:16_384].decode("utf-8", errors="ignore").lower()
    if "<html" not in text:
        return False
    auth_markers = [
        "login",
        "log in",
        "sign in",
        "sso",
        "saml",
        "oauth",
        "cas",
        "用户名",
        "密码",
        "登录",
    ]
    return any(marker in text for marker in auth_markers)


def extract_links_from_feed(root: ET.Element) -> list[str]:
    links: list[str] = []
    for element in root.iter():
        name = tag_name(element.tag)
        if name == "link":
            href = element.attrib.get("href")
            if href:
                links.append(href.strip())
            elif element.text and element.text.strip().startswith(("http://", "https://")):
                links.append(element.text.strip())
    return links


def verify_feed(feed_url: str, wiki_url: str | None, source: str, timeout: float, limit: int) -> dict[str, Any]:
    fetched = load_bytes(feed_url, timeout, limit)
    base = {
        "feed_url": feed_url,
        "source": source,
        "status_code": fetched.get("status_code"),
        "final_url": fetched.get("final_url", feed_url),
        "content_type": fetched.get("content_type", ""),
        "warnings": [],
    }

    if looks_auth_required(fetched.get("body", b""), fetched.get("status_code")):
        return {**base, "status": "auth_required", "ok": False, "reason": "Feed request returned an auth/login response."}

    if not fetched.get("ok"):
        return {**base, "status": "unreachable", "ok": False, "reason": fetched.get("error", "Feed request failed.")}

    body = fetched.get("body", b"").lstrip()
    if body[:128].lower().startswith(b"<!doctype html") or body[:128].lower().startswith(b"<html"):
        return {**base, "status": "invalid_feed", "ok": False, "reason": "Feed URL returned HTML instead of RSS/Atom XML."}

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return {**base, "status": "invalid_feed", "ok": False, "reason": f"XML parse failed: {exc}."}

    root_name = tag_name(root.tag)
    if root_name == "rss":
        entries = root.findall("./channel/item")
    elif root_name == "feed":
        entries = [child for child in root if tag_name(child.tag) == "entry"]
    elif root_name == "rdf":
        entries = [child for child in root if tag_name(child.tag) == "item"]
    else:
        return {**base, "status": "invalid_feed", "ok": False, "reason": f"Unexpected feed root: {root_name}."}

    links = extract_links_from_feed(root)
    warnings: list[str] = []
    if wiki_url and links:
        wiki_host = urllib.parse.urlparse(wiki_url).netloc
        matching = [link for link in links if urllib.parse.urlparse(link).netloc == wiki_host]
        if wiki_host and not matching:
            warnings.append("Feed entries do not link back to the wiki host.")

    if not entries:
        return {
            **base,
            "status": "reachable_empty",
            "ok": False,
            "reason": "Feed is reachable and parseable, but contains no items/entries.",
            "entry_count": 0,
            "warnings": warnings,
        }

    status = "provided_verified" if source == "provided" else "discovered_verified"
    return {
        **base,
        "status": status,
        "ok": True,
        "reason": "Feed is reachable, parseable, and contains entries.",
        "entry_count": len(entries),
        "warnings": warnings,
    }


def parse_space_key_from_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("spaceKey", "key"):
        if query.get(key):
            return query[key][0]
    match = re.search(r"/display/([^/?#]+)", parsed.path)
    if match:
        return urllib.parse.unquote(match.group(1))
    return None


def confluence_root(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    prefix = ""
    if path.startswith("/wiki/"):
        prefix = "/wiki"
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, prefix, "", "", ""))


def discover_candidates(wiki_url: str, timeout: float, limit: int) -> dict[str, Any]:
    fetched = load_bytes(wiki_url, timeout, limit)
    candidates: list[dict[str, str]] = []
    notes: list[str] = []
    if not fetched.get("ok") and fetched.get("status_code") not in {401, 403}:
        notes.append(f"wiki_url_fetch_failed: {fetched.get('error', 'request failed')}")

    body = fetched.get("body", b"")
    content_type = fetched.get("content_type", "").split(";", 1)[0].strip().lower()
    if content_type in FEED_TYPES or urllib.parse.urlparse(wiki_url).path.lower().endswith((".rss", ".atom", ".xml")):
        candidates.append({"feed_url": fetched.get("final_url", wiki_url), "source": "discovered", "method": "input_url_is_feed"})

    parser = FeedLinkParser()
    try:
        parser.feed(body[:limit].decode("utf-8", errors="ignore"))
    except Exception as exc:  # HTMLParser should be forgiving, keep discovery best-effort.
        notes.append(f"html_parse_failed: {exc}")

    seen: set[str] = {candidate["feed_url"] for candidate in candidates}
    for href in parser.feed_links:
        feed_url = urllib.parse.urljoin(fetched.get("final_url", wiki_url), href)
        if feed_url not in seen:
            seen.add(feed_url)
            candidates.append({"feed_url": feed_url, "source": "discovered", "method": "html_alternate"})

    space_key = parser.space_key or parse_space_key_from_url(wiki_url)
    if space_key:
        root = confluence_root(fetched.get("final_url", wiki_url))
        query = urllib.parse.urlencode(
            {
                "types": "page",
                "spaces": space_key,
                "sort": "modified",
                "maxResults": "50",
            }
        )
        feed_url = urllib.parse.urljoin(root + "/", "createrssfeed.action") + "?" + query
        if feed_url not in seen:
            candidates.append({"feed_url": feed_url, "source": "discovered", "method": "confluence_space"})

    return {
        "wiki_url": wiki_url,
        "status_code": fetched.get("status_code"),
        "final_url": fetched.get("final_url", wiki_url),
        "content_type": fetched.get("content_type", ""),
        "candidates": candidates,
        "notes": notes,
    }


def normalize_sources(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        raw_sources = raw.get("sources", [])
    else:
        raw_sources = raw
    if not isinstance(raw_sources, list):
        raise ValueError("Input JSON must be a list or an object with a 'sources' list.")

    sources: list[dict[str, str]] = []
    for item in raw_sources:
        if isinstance(item, str):
            sources.append({"source_url": item})
            continue
        if not isinstance(item, dict):
            raise ValueError("Each source must be a URL string or an object.")
        source_url = item.get("source_url") or item.get("wiki_url") or item.get("url")
        rss_url = item.get("rss_url") or item.get("feed_url") or ""
        if not source_url and not rss_url:
            raise ValueError("Each source object needs source_url/wiki_url/url or rss_url/feed_url.")
        normalized = {key: str(value) for key, value in item.items() if isinstance(value, (str, int, float, bool))}
        normalized["source_url"] = str(source_url or "")
        normalized["rss_url"] = str(rss_url or "")
        sources.append(normalized)
    return sources


def load_input(path: Path) -> list[dict[str, str]]:
    return normalize_sources(json.loads(path.read_text(encoding="utf-8")))


def sources_from_args(args: argparse.Namespace) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    if args.input:
        sources.extend(load_input(Path(args.input)))
    urls = args.url or []
    rss_urls = args.rss_url or []
    if urls:
        for index, url in enumerate(urls):
            rss_url = rss_urls[index] if index < len(rss_urls) else ""
            sources.append({"source_url": url, "rss_url": rss_url})
    elif rss_urls:
        for rss_url in rss_urls:
            sources.append({"source_url": "", "rss_url": rss_url})
    return sources


def evaluate_source(source: dict[str, str], timeout: float, limit: int) -> dict[str, Any]:
    wiki_url = source.get("source_url", "")
    provided_feed = source.get("rss_url", "")
    result: dict[str, Any] = {
        "source_url": wiki_url,
        "provided_rss_url": provided_feed,
        "status": "missing",
        "ok": False,
        "verification": None,
        "candidate_verifications": [],
        "discovery": None,
        "manual_action": None,
    }

    if provided_feed:
        verification = verify_feed(provided_feed, wiki_url or None, "provided", timeout, limit)
        result.update({"status": verification["status"], "ok": verification["ok"], "verification": verification})
        if not verification["ok"]:
            result["manual_action"] = "Provide a reachable RSS/Atom URL for this wiki source."
        return result

    if not wiki_url:
        result["manual_action"] = "Provide a wiki URL or RSS/Atom URL."
        return result

    discovery = discover_candidates(wiki_url, timeout, limit)
    result["discovery"] = discovery
    for candidate in discovery["candidates"]:
        verification = verify_feed(candidate["feed_url"], wiki_url, candidate["source"], timeout, limit)
        result["candidate_verifications"].append(verification)
        if verification["ok"]:
            result.update({"status": verification["status"], "ok": True, "verification": verification})
            return result

    if discovery["candidates"]:
        result["status"] = "discovered_unverified"
        result["manual_action"] = "Discovered candidate feed URLs, but none verified. Provide a working RSS/Atom URL manually."
    else:
        result["status"] = "missing"
        result["manual_action"] = "RSS/Atom URL could not be inferred. Provide the RSS/Atom URL manually, or leave it empty without automatic updates."
    return result


def write_reports(project: Path, report: dict[str, Any]) -> None:
    out = project / "staging" / "wiki-feeds" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Wiki Feed Discovery",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Overall status: `{'pass' if report['ok'] else 'fail'}`",
        "",
        "## Sources",
        "",
    ]
    for source in report["sources"]:
        lines.extend(
            [
                f"### {source.get('source_url') or source.get('provided_rss_url') or 'source'}",
                "",
                f"- Status: `{source['status']}`",
                f"- RSS/feed URL: `{(source.get('verification') or {}).get('feed_url', '')}`",
            ]
        )
        if source.get("manual_action"):
            lines.append(f"- Manual action: {source['manual_action']}")
        lines.append("")
    (out.with_suffix(".md")).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def source_key(source: dict[str, Any]) -> str:
    if str(source.get("source_id") or "").strip():
        return str(source["source_id"])
    if str(source.get("page_id") or "").strip():
        return f"cwiki-{source['page_id']}"
    if str(source.get("id") or "").strip():
        return f"rss-{source['id']}"
    return str(source.get("url") or source.get("source_url") or source.get("rss_url") or "")


def write_upstream_feed_results(project: Path, input_sources: list[dict[str, str]], results: list[dict[str, Any]]) -> None:
    path = project / "upstream" / "wiki-sources.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"version": 1, "sources": []}
    sources_raw = payload.get("sources")
    sources = [dict(item) for item in sources_raw if isinstance(item, dict)] if isinstance(sources_raw, list) else []
    by_key = {source_key(source): source for source in sources}

    for input_source, result in zip(input_sources, results):
        key = source_key(input_source)
        source = by_key.get(key)
        if source is None:
            source = {
                "type": "confluence" if str(input_source.get("source_url") or "").strip() else "rss",
                "enabled": True,
                "source_id": key,
                "relationship": {"role": "additional"},
                "url": input_source.get("source_url", ""),
            }
        verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
        feed_url = str(verification.get("feed_url") or result.get("provided_rss_url") or "").strip()
        source["rss_discovery_status"] = result.get("status")
        if feed_url:
            source["rss_url"] = feed_url
            source["rss_url_is_custom"] = result.get("status") == "provided_verified"
        by_key[source_key(source)] = source

    payload["version"] = int(payload.get("version", 1) or 1)
    payload["updated_at"] = utc_now()
    payload["sources"] = [by_key[key] for key in sorted(by_key)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--input", help="JSON file with sources. Defaults to upstream/wiki-sources.json when present.")
    parser.add_argument("--url", action="append", help="Wiki URL to discover/verify. Can be repeated.")
    parser.add_argument("--rss-url", action="append", help="Provided RSS/Atom URL to verify. Can be repeated.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds.")
    parser.add_argument("--limit", type=int, default=2_000_000, help="Maximum response bytes to inspect per request.")
    parser.add_argument("--write-upstream", action="store_true", help="Merge verified RSS/feed results into upstream/wiki-sources.json.")
    parser.add_argument("--json", action="store_true", help="Print JSON report only.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not args.input:
        default_input = project / "upstream" / "wiki-sources.json"
        if default_input.is_file():
            args.input = str(default_input)

    try:
        sources = sources_from_args(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"failed to read wiki feed sources: {exc}", file=sys.stderr)
        return 2

    if not sources:
        print("no wiki URLs or RSS/feed URLs provided", file=sys.stderr)
        return 2

    results = [evaluate_source(source, args.timeout, args.limit) for source in sources]
    ok = all(source["status"] in VERIFIED_STATUSES | NONBLOCKING_STATUSES for source in results)
    report = {
        "generated_at": utc_now(),
        "project": str(project),
        "ok": ok,
        "verified_statuses": sorted(VERIFIED_STATUSES),
        "sources": results,
    }
    write_reports(project, report)
    if args.write_upstream:
        write_upstream_feed_results(project, sources, results)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"wiki_feeds={'pass' if ok else 'fail'}")
        for source in results:
            label = source.get("source_url") or source.get("provided_rss_url")
            print(f"- {source['status']}: {label}")
            if source.get("manual_action"):
                print(f"  manual_action={source['manual_action']}")
        print(f"report={project / 'staging' / 'wiki-feeds' / 'latest.json'}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
