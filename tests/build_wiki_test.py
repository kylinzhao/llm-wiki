#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "skills" / "llm-wiki" / "assets" / "project-template" / "tools"
sys.path.insert(0, str(TOOLS))


def load_build_wiki():
    spec = importlib.util.spec_from_file_location("build_wiki", TOOLS / "build_wiki.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_existing_source_page(path: Path, old_hash: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Source",
                "",
                "## 来源",
                "",
                "- 原始路径: `raw/old.md`",
                f"- SHA-256: `{old_hash}`",
                "- 大小: `1` bytes",
                "",
                "## 摘要",
                "",
                "Existing refined summary.",
                "",
                "## Source Metadata",
                "```json",
                json.dumps(
                    {
                        "page_kind": "source",
                        "schema_version": "source-v2",
                        "raw_rel": "raw/old.md",
                        "raw_hash": old_hash,
                        "ai_refinement_state": "done",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected {needle!r} in:\n{text}")


def main() -> None:
    build_wiki = load_build_wiki()
    old_hash = "a" * 64
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw_page = project / "raw" / "source.md"
        raw_page.parent.mkdir(parents=True)
        raw_page.write_text("page_id: 456\nUpdated source\n", encoding="utf-8")
        new_hash = hashlib.sha256(raw_page.read_bytes()).hexdigest()
        source_page = project / "wiki" / "sources" / "source.md"
        write_existing_source_page(source_page, old_hash)

        build_wiki.main_for_project(project)

        text = source_page.read_text(encoding="utf-8")
        assert_contains(text, "- Raw path: `raw/source.md`")
        assert_contains(text, f"- SHA-256: `{new_hash}`")
        assert_contains(text, "Existing refined summary.")
        assert_contains(text, '"raw_rel": "raw/source.md"')
        assert_contains(text, f'"raw_hash": "{new_hash}"')
        assert_contains(text, '"ai_refinement_state": "done"')

        retrieval_playbook = (project / "docs" / "retrieval-playbook.md").read_text(encoding="utf-8")
        assert_contains(retrieval_playbook, "## 语言要求")
        assert_contains(retrieval_playbook, "默认使用中文")

        drift = json.loads((project / "staging" / "source-drift.json").read_text(encoding="utf-8"))
        if drift["stale_sources"]:
            raise AssertionError(f"expected no stale sources after source backfill: {drift['stale_sources']}")


if __name__ == "__main__":
    main()
