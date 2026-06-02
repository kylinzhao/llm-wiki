import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py"
UPDATE_WIKI_SCRIPT = TOOLS_DIR / "update_wiki.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_confluence_tree", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_confluence_tree"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_update_wiki():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("update_wiki", UPDATE_WIKI_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportConfluenceExcludeAuthorTest(unittest.TestCase):
    def test_normalize_and_filter_pages_by_author(self):
        exporter = load_exporter()
        excluded = exporter.normalize_exclude_authors(["Alice", " alice "])

        pages = {
            "1": exporter.PageNode(
                page_id="1",
                title="Keep",
                url="https://wiki.example.com/pages/viewpage.action?pageId=1",
                depth=0,
                html="",
                author="Bob",
            ),
            "2": exporter.PageNode(
                page_id="2",
                title="Drop",
                url="https://wiki.example.com/pages/viewpage.action?pageId=2",
                depth=1,
                html="",
                author="Alice",
            ),
        }

        filtered = exporter.filter_pages_by_exclude_authors(pages, excluded)

        self.assertEqual(set(filtered), {"1"})
        self.assertTrue(exporter.page_matches_exclude_authors(pages["2"], excluded))
        self.assertFalse(exporter.page_matches_exclude_authors(pages["1"], excluded))

    def test_exclude_author_uses_substring_match_for_disambiguation(self):
        exporter = load_exporter()
        excluded = exporter.normalize_exclude_authors(["张丹-出海业务"])

        target = exporter.PageNode(
            page_id="10",
            title="Spec",
            url="https://wiki.example.com/pages/viewpage.action?pageId=10",
            depth=0,
            html="",
            author="张丹-出海业务-出海产品与增长部",
        )
        other = exporter.PageNode(
            page_id="11",
            title="Other",
            url="https://wiki.example.com/pages/viewpage.action?pageId=11",
            depth=0,
            html="",
            author="张丹-供应链业务-供应链产品部",
        )
        short_only = exporter.PageNode(
            page_id="12",
            title="Ambiguous",
            url="https://wiki.example.com/pages/viewpage.action?pageId=12",
            depth=0,
            html="",
            author="张丹",
        )

        self.assertTrue(exporter.page_matches_exclude_authors(target, excluded))
        self.assertFalse(exporter.page_matches_exclude_authors(other, excluded))

        broad = exporter.normalize_exclude_authors(["张丹"])
        self.assertTrue(exporter.page_matches_exclude_authors(short_only, broad))
        self.assertTrue(exporter.page_matches_exclude_authors(other, broad))

        filtered = exporter.filter_pages_by_exclude_authors(
            {"10": target, "11": other},
            excluded,
        )
        self.assertEqual(set(filtered), {"11"})

    def test_write_upstream_wiki_sources_persists_exclude_authors(self):
        exporter = load_exporter()

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            output_dir = project / "raw"
            metadata_dir = project / "staging" / "wiki-export-state"
            output_dir.mkdir(parents=True)
            metadata_dir.mkdir(parents=True)

            exporter.write_upstream_wiki_sources(
                output_dir=output_dir,
                metadata_dir=metadata_dir,
                root_states=[
                    {
                        "page_id": "1",
                        "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                        "site_base": "https://cwiki.guazi.com",
                        "depth_limit": 2,
                    }
                ],
                exclude_authors=["Alice", "Bob"],
            )

            payload = json.loads((project / "upstream" / "wiki-sources.json").read_text(encoding="utf-8"))
            filters = payload["sources"][0]["filters"]
            self.assertEqual(filters["exclude_authors"], ["Alice", "Bob"])

    def test_confluence_sync_command_forwards_exclude_authors(self):
        update_wiki = load_update_wiki()

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            exporter = project / "tools" / "confluence_sync" / "export_obsidian_wiki.py"
            exporter.parent.mkdir(parents=True)
            exporter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (project / "upstream").mkdir(parents=True)
            (project / "upstream" / "wiki-sources.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {
                                "type": "confluence",
                                "enabled": True,
                                "source_id": "cwiki-1",
                                "relationship": {"role": "primary"},
                                "page_id": "1",
                                "url": "https://cwiki.guazi.com/pages/viewpage.action?pageId=1",
                                "depth": 2,
                                "filters": {"exclude_authors": ["Alice", "Bob"]},
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            commands = update_wiki.confluence_sync_commands(project)

            self.assertEqual(commands[0].count("--exclude-author"), 2)
            self.assertIn("Alice", commands[0])
            self.assertIn("Bob", commands[0])


if __name__ == "__main__":
    unittest.main()
