import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_build_wiki():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("build_wiki", TOOLS_DIR / "build_wiki.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SourceV2BuildWikiTest(unittest.TestCase):
    def test_new_project_seed_pages_are_chinese_first(self):
        import tempfile

        build_wiki = load_build_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_page = tmp_path / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# 产品说明\n\n这是原始证据。\n", encoding="utf-8")

            build_wiki.main_for_project(tmp_path)

            overview = (tmp_path / "wiki" / "overview.md").read_text(encoding="utf-8")
            playbook = (tmp_path / "docs" / "retrieval-playbook.md").read_text(encoding="utf-8")
            source = (tmp_path / "wiki" / "sources" / "product-index.md").read_text(encoding="utf-8")

        self.assertIn("# 总览", overview)
        self.assertIn("待基于", overview)
        self.assertIn("# 检索手册", playbook)
        self.assertIn("先读取 `BUSINESS_CONTEXT.md`", playbook)
        self.assertIn("## 来源", source)
        self.assertIn("待完成 AI 原生摘要", source)

    def test_source_v2_prefix_hash_matches_full_raw_sha_and_legacy_slug_is_not_orphan(self):
        import tempfile

        build_wiki = load_build_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_page = tmp_path / "raw" / "123-业务页面" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# 业务页面\n\n这是原始证据。\n", encoding="utf-8")
            raw_sha = hashlib.sha256(raw_page.read_bytes()).hexdigest()

            source_dir = tmp_path / "wiki" / "sources"
            source_dir.mkdir(parents=True)
            (source_dir / "index.md").write_text("# Sources\n", encoding="utf-8")
            legacy_page = source_dir / "123-业务页面.md"
            legacy_page.write_text(
                f"""# 业务页面

## Source Metadata
```json
{{
  "page_kind": "source",
  "schema_version": "source-v2",
  "source_slug": "123-业务页面",
  "raw_rel": "raw/123-业务页面/index.md",
  "raw_hash": "{raw_sha[:16]}",
  "ai_refinement_state": "applied"
}}
```

## AI Refinement Block
<!-- AI:BEGIN -->
人工精修内容必须保留。
<!-- AI:END -->
""",
                encoding="utf-8",
            )

            build_wiki.main_for_project(tmp_path)

            canonical_page = source_dir / "123-业务页面-index.md"
            self.assertTrue(canonical_page.exists())
            self.assertIn("人工精修内容必须保留", canonical_page.read_text(encoding="utf-8"))
            self.assertFalse(legacy_page.exists())

            drift = build_wiki.read_json(tmp_path / "staging" / "source-drift.json")
            self.assertEqual(drift["stale_sources"], [])
            self.assertEqual(drift["orphan_source_pages"], [])

    def test_operational_export_metadata_without_raw_hash_does_not_block_health(self):
        import tempfile

        build_wiki = load_build_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_page = tmp_path / "raw" / "rss" / "626659514" / "626659514_latest.json"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text('{"kind":"export-state"}\n', encoding="utf-8")

            source_dir = tmp_path / "wiki" / "sources"
            source_dir.mkdir(parents=True)
            source_page = source_dir / "rss-626659514-626659514_latest.md"
            source_page.write_text(
                """# export state

## Source Metadata
```json
{
  "page_kind": "source",
  "schema_version": "source-v2",
  "source_slug": "rss-626659514-626659514_latest",
  "raw_rel": "raw/rss/626659514/626659514_latest.json",
  "candidate_layer": "operations",
  "ai_refinement_state": "applied"
}
```

## Summary

Operational sync metadata.
""",
                encoding="utf-8",
            )

            build_wiki.main_for_project(tmp_path)

            drift = build_wiki.read_json(tmp_path / "staging" / "source-drift.json")
            self.assertEqual(drift["stale_sources"], [])

    def test_operational_rss_metadata_hash_changes_do_not_mark_stale(self):
        import tempfile

        build_wiki = load_build_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_page = tmp_path / "raw" / "rss" / "605842244" / "605842244_latest.json"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text('{"items": 1}\n', encoding="utf-8")

            source_dir = tmp_path / "wiki" / "sources"
            source_dir.mkdir(parents=True)
            source_page = source_dir / "rss-605842244-605842244_latest.md"
            source_page.write_text(
                """# 605842244 latest

## Source Metadata
```json
{
  "page_kind": "source",
  "schema_version": "source-v2",
  "source_slug": "rss-605842244-605842244_latest",
  "raw_rel": "raw/rss/605842244/605842244_latest.json",
  "raw_hash": "oldhash1234567890",
  "ai_refinement_state": "applied"
}
```

## Summary

Operational RSS metadata.
""",
                encoding="utf-8",
            )

            build_wiki.main_for_project(tmp_path)

            drift = build_wiki.read_json(tmp_path / "staging" / "source-drift.json")
            plan = build_wiki.read_json(tmp_path / "staging" / "refinement-plan.json")
            self.assertEqual(drift["stale_sources"], [])
            self.assertFalse(plan["semantic_update_required"])


if __name__ == "__main__":
    unittest.main()
