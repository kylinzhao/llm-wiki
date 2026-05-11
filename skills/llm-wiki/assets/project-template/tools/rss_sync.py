#!/usr/bin/env python3
"""Deterministic RSS fetch with rate limits (engine-owned). Gateway only invokes this phase."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    print("rss_sync: PyYAML is required (pip/uv: pyyaml)", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parents[1]
STAGING_RSS = ROOT / "staging" / "rss"
STATE_PATH = STAGING_RSS / "state.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {}
    return data


def host_from_url(url: str) -> str:
    try:
        return urlparse(url).hostname or "unknown"
    except Exception:
        return "unknown"


def fetch_url(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "llm-wiki-rss-sync/1.0 (+engine rss_sync.py)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_rss_items(xml_bytes: bytes) -> tuple[list[dict[str, str]], str | None]:
    """Parse RSS 2.0 channel/items; returns items with title/link/pubDate text."""
    items: list[dict[str, str]] = []
    channel_title = None
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return [], f"xml_parse_error:{e}"

    root_tag = strip_ns(root.tag).lower()
    if root_tag == "rss":
        channel = root.find(".//channel") or root
        if channel is not None:
            t = channel.find("title")
            if t is not None and t.text:
                channel_title = t.text.strip()
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            items.append(
                {
                    "title": (title_el.text or "").strip() if title_el is not None else "",
                    "link": (link_el.text or "").strip() if link_el is not None else "",
                    "pubDate": (pub_el.text or "").strip() if pub_el is not None else "",
                }
            )
    elif root_tag == "feed":
        # Atom — minimal
        t = root.find("{http://www.w3.org/2005/Atom}title")
        if t is not None and t.text:
            channel_title = t.text.strip()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            tit = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            updated = entry.find("atom:updated", ns)
            href = link_el.get("href", "") if link_el is not None else ""
            items.append(
                {
                    "title": (tit.text or "").strip() if tit is not None else "",
                    "link": href,
                    "pubDate": (updated.text or "").strip() if updated is not None else "",
                }
            )

    return items, channel_title


def throttle(
    state: dict[str, Any],
    feed_id: str,
    host: str,
    cfg: dict[str, Any],
    default_interval: float,
) -> None:
    """Sleep if needed to respect per-feed and per-host intervals."""
    rate = cfg.get("rate_limits") or {}
    per_host = (rate.get("per_host") or {}) if isinstance(rate.get("per_host"), dict) else {}
    host_rule = per_host.get(host) if isinstance(per_host.get(host), dict) else {}
    host_interval = float(host_rule.get("min_interval_seconds", default_interval))
    now = time.time()
    last_feed = float(state.get("last_fetch_feed", {}).get(feed_id, 0))
    last_host = float(state.get("last_fetch_host", {}).get(host, 0))
    wait_feed = max(0.0, default_interval - (now - last_feed))
    wait_host = max(0.0, host_interval - (now - last_host))
    sleep_s = max(wait_feed, wait_host)
    if sleep_s > 0:
        time.sleep(sleep_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="RSS sync with rate limits")
    parser.add_argument("--config", default="config/rss-feeds.yaml", help="Path to rss-feeds.yaml")
    args = parser.parse_args()
    cfg_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)

    if not cfg_path.exists():
        STAGING_RSS.mkdir(parents=True, exist_ok=True)
        noop = {
            "ok": True,
            "skipped": True,
            "reason": "config_missing",
            "config_path": str(cfg_path),
            "at": utc_now_iso(),
        }
        write_json(STAGING_RSS / "latest.json", noop)
        write_text(
            STAGING_RSS / "latest.md",
            f"# RSS sync\n\nSkipped: config not found at `{cfg_path}`.\n",
        )
        return 0

    cfg = load_config(cfg_path)
    feeds_raw = cfg.get("feeds") or []
    if not isinstance(feeds_raw, list):
        feeds_raw = []

    enabled_feeds = []
    for f in feeds_raw:
        if not isinstance(f, dict):
            continue
        if f.get("enabled") is False:
            continue
        fid = str(f.get("id") or "").strip()
        url = str(f.get("url") or "").strip()
        if not fid or not url:
            continue
        enabled_feeds.append(f)

    rate = cfg.get("rate_limits") or {}
    default_interval = float(rate.get("default_min_interval_seconds", 60))
    retry_cfg = cfg.get("retry") or {}
    max_attempts = int(retry_cfg.get("max_attempts", 2))
    backoff = float(retry_cfg.get("backoff_seconds", 30))

    STAGING_RSS.mkdir(parents=True, exist_ok=True)

    if not enabled_feeds:
        summary = {
            "ok": True,
            "skipped": True,
            "reason": "no_enabled_feeds",
            "at": utc_now_iso(),
            "config_path": str(cfg_path),
        }
        write_json(STAGING_RSS / "latest.json", summary)
        write_text(STAGING_RSS / "latest.md", "# RSS sync\n\nNo enabled feeds — noop.\n")
        return 0

    state = read_json(STATE_PATH, {"last_fetch_feed": {}, "last_fetch_host": {}})
    if not isinstance(state.get("last_fetch_feed"), dict):
        state["last_fetch_feed"] = {}
    if not isinstance(state.get("last_fetch_host"), dict):
        state["last_fetch_host"] = {}

    results: list[dict[str, Any]] = []
    for feed in enabled_feeds:
        fid = str(feed["id"])
        url = str(feed["url"])
        target_dir = str(feed.get("target_dir") or f"raw/rss/{fid}")
        host = host_from_url(url)

        throttle(state, fid, host, cfg, default_interval)

        attempt = 0
        last_err = None
        xml_bytes: bytes | None = None
        while attempt < max_attempts:
            attempt += 1
            try:
                xml_bytes = fetch_url(url)
                last_err = None
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = str(e)
                if attempt < max_attempts:
                    time.sleep(backoff + random.uniform(0, 1))

        if xml_bytes is None:
            results.append({"id": fid, "ok": False, "error": last_err or "fetch_failed"})
            continue

        items, ch_title = parse_rss_items(xml_bytes)
        err = None if items or ch_title is not None else "no_items_parsed"

        out_dir = ROOT / target_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = STAGING_RSS / "feeds" / fid / "snapshot.xml"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(xml_bytes)

        payload_path = out_dir / f"{fid}_latest.json"
        payload = {
            "feed_id": fid,
            "fetched_at": utc_now_iso(),
            "channel_title": ch_title,
            "item_count": len(items),
            "items": items[:200],
        }
        write_json(payload_path, payload)

        now_ts = time.time()
        state["last_fetch_feed"][fid] = now_ts
        state["last_fetch_host"][host] = now_ts

        results.append(
            {
                "id": fid,
                "ok": True,
                "items": len(items),
                "target_dir": target_dir,
                "warning": err,
            }
        )

    write_json(STATE_PATH, state)

    digest_input = json.dumps(results, sort_keys=True, ensure_ascii=True)
    summary = {
        "ok": all(r.get("ok") for r in results),
        "at": utc_now_iso(),
        "feeds_processed": len(results),
        "results": results,
        "digest": hashlib.sha256(digest_input.encode()).hexdigest()[:16],
    }
    write_json(STAGING_RSS / "latest.json", summary)

    md_lines = ["# RSS sync\n", f"- At: {summary['at']}", f"- Feeds: {len(results)}\n"]
    for r in results:
        md_lines.append(f"- **{r.get('id')}**: {'ok' if r.get('ok') else 'FAIL'} — {json.dumps(r, ensure_ascii=False)}")
    write_text(STAGING_RSS / "latest.md", "\n".join(md_lines) + "\n")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
