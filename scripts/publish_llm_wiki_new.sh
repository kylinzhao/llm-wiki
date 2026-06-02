#!/usr/bin/env bash
# Build skills-new/ with llm-wiki-new* names (experimental bundle; does not touch llm-wiki-* installs).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_SKILLS="$ROOT_DIR/skills"
OUT_SKILLS="$ROOT_DIR/skills-new"

export ROOT_DIR
python3 <<'PY'
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(os.environ["ROOT_DIR"])
SRC = ROOT / "skills"
OUT = ROOT / "skills-new"

RENAME = {
    "llm-wiki": "llm-wiki-new",
    "llm-wiki-add-code": "llm-wiki-new-add-code",
    "llm-wiki-add-wiki": "llm-wiki-new-add-wiki",
    "llm-wiki-backfill": "llm-wiki-new-backfill",
    "llm-wiki-doctor": "llm-wiki-new-doctor",
    "llm-wiki-fast": "llm-wiki-new-fast",
    "llm-wiki-image": "llm-wiki-new-image",
    "llm-wiki-init": "llm-wiki-new-init",
    "llm-wiki-maintain-all": "llm-wiki-new-maintain-all",
    "llm-wiki-query": "llm-wiki-new-query",
    "llm-wiki-query-plus": "llm-wiki-new-query-plus",
    "llm-wiki-review-requirement": "llm-wiki-new-review-requirement",
    "llm-wiki-update": "llm-wiki-new-update",
    "llm-wiki-update-skill": "llm-wiki-new-update-skill",
}

SKIP = {"requirement-review"}

SUFFIXES = (
    "review-requirement",
    "update-skill",
    "query-plus",
    "maintain-all",
    "add-wiki",
    "add-code",
    "backfill",
    "update",
    "doctor",
    "query",
    "init",
    "fast",
    "image",
)

TOKEN_REPLACEMENTS = sorted(
    [(f"$llm-wiki-{suffix}", f"$llm-wiki-new-{suffix}") for suffix in SUFFIXES]
    + [
        ("/llm-wiki-", "/llm-wiki-new-"),
        ("`llm-wiki ", "`llm-wiki-new "),
        ("## `llm-wiki ", "## `llm-wiki-new "),
        ("诊断类型：llm-wiki ", "诊断类型：llm-wiki-new "),
        ("**llm-wiki** skill", "**llm-wiki-new** skill"),
        ("llm-wiki skill 包", "llm-wiki-new skill 包"),
        ("llm-wiki skill bundle", "llm-wiki-new skill bundle"),
        ("llm-wiki skills", "llm-wiki-new skills"),
        ("$LLM_WIKI_SKILL_ROOT", "$LLM_WIKI_NEW_SKILL_ROOT"),
        ("LLM_WIKI_SKILL_ROOT", "LLM_WIKI_NEW_SKILL_ROOT"),
        ("llm-wiki-skill", "llm-wiki-new-skill"),
    ],
    key=lambda item: -len(item[0]),
)


def rewrite_text(text: str) -> str:
    for old, new in TOKEN_REPLACEMENTS:
        text = text.replace(old, new)
    # Bare invocations only — avoid turning llm-wiki-new-* into llm-wiki-new-new-*
    text = re.sub(r"\$llm-wiki(?!-new)", "$llm-wiki-new", text)
    text = re.sub(r"/llm-wiki(?!-new)", "/llm-wiki-new", text)
    text = re.sub(r"`llm-wiki(?!-new)", "`llm-wiki-new", text)
    return text


def rewrite_frontmatter_name(text: str, new_name: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    front = text[: end + 4]
    body = text[end + 4 :]
    front = re.sub(r"^name:\s*.+$", f"name: {new_name}", front, count=1, flags=re.M)
    if "experimental" not in front.lower():
        front = re.sub(
            r"^(description:\s*.+)$",
            r"\1（实验包 llm-wiki-new；与全局 llm-wiki 并行，验证通过后再合并）",
            front,
            count=1,
            flags=re.M,
        )
    return front + body


def copy_skill(old_name: str, new_name: str) -> None:
    src = SRC / old_name
    dst = OUT / new_name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for path in dst.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json", ".sh", ".py"}:
            raw = path.read_text(encoding="utf-8")
            updated = rewrite_text(raw)
            if path.name == "SKILL.md":
                updated = rewrite_frontmatter_name(updated, new_name)
            if updated != raw:
                path.write_text(updated, encoding="utf-8")


if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

for old, new in RENAME.items():
    copy_skill(old, new)

# Marker file for installs
(OUT / "BUNDLE_ID").write_text("llm-wiki-new\n", encoding="utf-8")
(OUT / "README.md").write_text(
    "# llm-wiki-new（实验 skill bundle）\n\n"
    "由 `scripts/publish_llm_wiki_new.sh` 从 `skills/` 生成。\n"
    "安装：`./install-llm-wiki-new.sh --link --client cursor`\n"
    "不会覆盖已安装的 `llm-wiki-*`。\n",
    encoding="utf-8",
)

print(f"Published {len(RENAME)} skills to {OUT}")
PY

echo "llm-wiki-new publish complete: $OUT_SKILLS"
