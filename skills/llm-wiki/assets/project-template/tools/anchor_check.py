#!/usr/bin/env python3
"""Check that referenced raw-code anchors in traceability pages exist."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


RAW_CODE_RE = re.compile(r"`(raw-code/[^`]+)`")
LINE_REF_RE = re.compile(r"^(raw-code/.+):(\d+)(?::\d+)?$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_anchor(ref: str) -> tuple[str, str | None]:
    value = ref.strip()
    if "..." in value or "*" in value:
        return value, "symbolic"
    line_match = LINE_REF_RE.match(value)
    if line_match:
        return line_match.group(1), None
    return value, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project root. Defaults to current directory.")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    trace_dir = project / "wiki" / "code" / "traceability"
    missing = []
    skipped = []
    checked = 0
    if trace_dir.is_dir():
        for page in sorted(trace_dir.rglob("*.md")):
            text = page.read_text(encoding="utf-8", errors="replace")
            for ref in RAW_CODE_RE.findall(text):
                normalized, skip_reason = normalize_anchor(ref)
                if skip_reason:
                    skipped.append(
                        {
                            "page": str(page.relative_to(project)),
                            "anchor": ref,
                            "reason": skip_reason,
                        }
                    )
                    continue
                checked += 1
                if not (project / normalized).exists():
                    missing.append({"page": str(page.relative_to(project)), "anchor": ref})
    report = {
        "generated_at": utc_now(),
        "checked": checked,
        "skipped": skipped,
        "missing": missing,
        "ok": not missing,
    }
    out = project / "staging" / "anchor-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
