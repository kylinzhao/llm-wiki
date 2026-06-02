import importlib.util
import json
import sys
import tempfile
import unittest
from collections import deque
from unittest import mock
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_confluence_tree", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_confluence_tree"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportConfluenceSourcePathTest(unittest.TestCase):
    def test_cookie_header_is_loaded_from_auth_env_file(self):
        exporter = load_exporter()

        with tempfile.TemporaryDirectory() as tmp:
            auth_env = Path(tmp) / "guazi-sso.env"
            auth_env.write_text("COOKIE_HEADER='GUAZISSO=token; JSESSIONID=session'\n", encoding="utf-8")
            with mock.patch.object(exporter, "AUTH_ENV_FILE", auth_env), mock.patch.object(sys, "argv", ["export"]):
                args = exporter.parse_args()

        self.assertEqual(args.cookie, "GUAZISSO=token; JSESSIONID=session")

    def test_fetch_page_expands_and_persists_source_path(self):
        exporter = load_exporter()

        payload = {
            "id": "300",
            "title": "Refund Rules",
            "body": {"view": {"value": "<p>body</p>"}, "storage": {"value": "<p>body</p>"}},
            "history": {"createdBy": {"displayName": "Alice"}, "createdDate": "2026-01-01T00:00:00Z"},
            "version": {"by": {"displayName": "Bob"}, "when": "2026-01-02T00:00:00Z", "number": 7},
            "ancestors": [
                {"id": "100", "title": "Knowledge Base"},
                {"id": "200", "title": "Trading"},
            ],
        }

        self.assertIn("ancestors", exporter.content_endpoint("https://wiki.example.com", "300"))
        page = exporter.page_from_payload("https://wiki.example.com", payload, depth=2)

        self.assertTrue(page.ancestry_loaded)
        self.assertEqual(exporter.source_path_text(page), "Knowledge Base / Trading / Refund Rules")
        self.assertEqual(exporter.parent_ref(page).page_id, "200")

        encoded = exporter.page_node_to_dict(page)
        decoded = exporter.page_node_from_dict(encoded)
        self.assertEqual(exporter.source_path_text(decoded), "Knowledge Base / Trading / Refund Rules")

    def test_raw_frontmatter_and_manifest_include_source_path(self):
        exporter = load_exporter()
        page = exporter.PageNode(
            page_id="300",
            title="Refund Rules",
            url="https://wiki.example.com/pages/viewpage.action?pageId=300",
            depth=2,
            html="<p>body</p>",
            updated_at="2026-01-02T00:00:00Z",
            version_number=7,
            ancestors=[
                exporter.PageRef("100", "Knowledge Base", "https://wiki.example.com/pages/viewpage.action?pageId=100"),
                exporter.PageRef("200", "Trading", "https://wiki.example.com/pages/viewpage.action?pageId=200"),
            ],
            ancestry_loaded=True,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "raw"
            metadata_dir = Path(tmp) / "state"
            exporter.write_root_export("100", {"300": page}, output_dir, None, manifest_dir=metadata_dir)
            raw_page = next(output_dir.glob("*/index.md"))
            text = raw_page.read_text(encoding="utf-8")
            self.assertIn("parent_page_id: '200'", text)
            self.assertIn("source_path_text: 'Knowledge Base / Trading / Refund Rules'", text)
            self.assertIn("title: 'Trading'", text)

            manifest = json.loads((metadata_dir / "manifest-100.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["parent_page_id"], "200")
            self.assertEqual(manifest[0]["source_path_text"], "Knowledge Base / Trading / Refund Rules")

            progress = metadata_dir / "progress.json"
            exporter.save_progress_state(
                progress,
                root_page_id="100",
                depth_limit=3,
                pages={"300": page},
                queue=deque(),
                enqueued={"300"},
            )
            state = exporter.load_progress_state(progress, root_page_id="100", depth_limit=3)
            self.assertEqual(exporter.source_path_text(state["pages"]["300"]), "Knowledge Base / Trading / Refund Rules")

    def test_existing_raw_without_source_path_is_rewritten(self):
        exporter = load_exporter()
        page = exporter.PageNode(
            page_id="300",
            title="Refund Rules",
            url="https://wiki.example.com/pages/viewpage.action?pageId=300",
            depth=0,
            html="<p>body</p>",
            updated_at="2026-01-02T00:00:00Z",
            version_number=7,
            ancestry_loaded=True,
        )

        with tempfile.TemporaryDirectory() as tmp:
            raw_page = Path(tmp) / "raw" / "pages" / "300-refund-rules" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text(
                "\n".join(
                    [
                        "---",
                        "title: 'Refund Rules'",
                        "page_id: '300'",
                        "source_url: https://wiki.example.com/pages/viewpage.action?pageId=300",
                        "updated_at: '2026-01-02T00:00:00Z'",
                        "version_number: 7",
                        "---",
                        "",
                        "# Refund Rules",
                        "",
                        "body",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertFalse(exporter.page_is_unchanged(raw_page, page))

    def test_legacy_child_state_without_ancestors_does_not_force_rewrite(self):
        exporter = load_exporter()
        page = exporter.PageNode(
            page_id="300",
            title="Refund Rules",
            url="https://wiki.example.com/pages/viewpage.action?pageId=300",
            depth=2,
            html="<p>body</p>",
            updated_at="2026-01-02T00:00:00Z",
            version_number=7,
        )

        with tempfile.TemporaryDirectory() as tmp:
            raw_page = Path(tmp) / "raw" / "300-refund-rules" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text(
                "\n".join(
                    [
                        "---",
                        "title: 'Refund Rules'",
                        "page_id: '300'",
                        "source_url: https://wiki.example.com/pages/viewpage.action?pageId=300",
                        "updated_at: '2026-01-02T00:00:00Z'",
                        "version_number: 7",
                        "---",
                        "",
                        "# Refund Rules",
                        "",
                        "body",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertTrue(exporter.page_is_unchanged(raw_page, page))
            self.assertEqual(exporter.source_path(page), [])

    def test_rss_include_new_exports_only_pages_inside_root_depth(self):
        exporter = load_exporter()
        root = exporter.PageNode(
            page_id="100",
            title="Knowledge Base",
            url="https://wiki.example.com/pages/viewpage.action?pageId=100",
            depth=0,
            html="<p>root</p>",
            updated_at="2026-01-01T00:00:00Z",
            version_number=1,
            ancestry_loaded=True,
        )
        in_scope = exporter.PageNode(
            page_id="300",
            title="Refund Rules",
            url="https://wiki.example.com/pages/viewpage.action?pageId=300",
            depth=0,
            html="<p>new</p>",
            updated_at="2026-01-03T00:00:00Z",
            version_number=3,
            ancestors=[
                exporter.PageRef("100", "Knowledge Base", "https://wiki.example.com/pages/viewpage.action?pageId=100"),
                exporter.PageRef("200", "Trading", "https://wiki.example.com/pages/viewpage.action?pageId=200"),
            ],
            ancestry_loaded=True,
        )
        out_of_scope = exporter.PageNode(
            page_id="400",
            title="Other Space Page",
            url="https://wiki.example.com/pages/viewpage.action?pageId=400",
            depth=0,
            html="<p>other</p>",
            updated_at="2026-01-03T00:00:00Z",
            version_number=3,
            ancestors=[
                exporter.PageRef("900", "Other Root", "https://wiki.example.com/pages/viewpage.action?pageId=900"),
            ],
            ancestry_loaded=True,
        )
        too_deep = exporter.PageNode(
            page_id="500",
            title="Too Deep",
            url="https://wiki.example.com/pages/viewpage.action?pageId=500",
            depth=0,
            html="<p>deep</p>",
            updated_at="2026-01-03T00:00:00Z",
            version_number=3,
            ancestors=[
                exporter.PageRef("100", "Knowledge Base", "https://wiki.example.com/pages/viewpage.action?pageId=100"),
                exporter.PageRef("200", "Trading", "https://wiki.example.com/pages/viewpage.action?pageId=200"),
                exporter.PageRef("250", "Nested", "https://wiki.example.com/pages/viewpage.action?pageId=250"),
            ],
            ancestry_loaded=True,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "raw"
            metadata_dir = Path(tmp) / "state"
            progress = metadata_dir / "progress" / "100.json"
            exporter.save_progress_state(
                progress,
                root_page_id="100",
                depth_limit=2,
                pages={"100": root},
                queue=deque(),
                enqueued={"100"},
            )
            entries = [
                exporter.FeedEntry("300", "Refund Rules", in_scope.url, "2026-01-03T00:00:00Z", version_number=3),
                exporter.FeedEntry("400", "Other Space Page", out_of_scope.url, "2026-01-03T00:00:00Z", version_number=3),
                exporter.FeedEntry("500", "Too Deep", too_deep.url, "2026-01-03T00:00:00Z", version_number=3),
            ]
            pages_by_id = {"300": in_scope, "400": out_of_scope, "500": too_deep}

            with mock.patch.object(exporter, "fetch_rss_entries", return_value=entries), mock.patch.object(
                exporter, "fetch_page", side_effect=lambda _session, _site_base, page_id, depth: pages_by_id[page_id]
            ):
                result = exporter.update_root_from_rss(
                    object(),
                    root_page_id="100",
                    site_base="https://wiki.example.com",
                    output_dir=output_dir,
                    metadata_dir=metadata_dir,
                    depth_limit=2,
                    rss_url="https://wiki.example.com/rss",
                    include_new=True,
                )

            self.assertEqual(result.updated_page_ids, ["300"])
            self.assertEqual(result.change_records[0]["parent_page_id"], "200")
            self.assertEqual(result.change_records[0]["source_path_text"], "Knowledge Base / Trading / Refund Rules")
            self.assertEqual(result.ignored_page_ids, ["400", "500"])
            self.assertEqual([record["reason"] for record in result.ignored_page_records], ["out_of_scope", "depth_exceeded"])

            state = exporter.load_progress_state(progress, root_page_id="100", depth_limit=2)
            self.assertIn("300", state["pages"])
            self.assertNotIn("400", state["pages"])
            self.assertNotIn("500", state["pages"])
            self.assertEqual(state["pages"]["300"].depth, 2)

            raw_page = output_dir / "300-refund-rules" / "index.md"
            self.assertTrue(raw_page.is_file())
            self.assertIn("source_path_text: 'Knowledge Base / Trading / Refund Rules'", raw_page.read_text(encoding="utf-8"))

            report = json.loads((Path(tmp) / "staging" / "wiki-sync" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual([record["reason"] for record in report["ignored_pages"]], ["out_of_scope", "depth_exceeded"])

    def test_rss_include_new_ignores_pages_without_loaded_ancestors(self):
        exporter = load_exporter()
        root = exporter.PageNode(
            page_id="100",
            title="Knowledge Base",
            url="https://wiki.example.com/pages/viewpage.action?pageId=100",
            depth=0,
            html="<p>root</p>",
            updated_at="2026-01-01T00:00:00Z",
            version_number=1,
            ancestry_loaded=True,
        )
        unknown = exporter.PageNode(
            page_id="300",
            title="Unknown Path",
            url="https://wiki.example.com/pages/viewpage.action?pageId=300",
            depth=0,
            html="<p>new</p>",
            updated_at="2026-01-03T00:00:00Z",
            version_number=3,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "raw"
            metadata_dir = Path(tmp) / "state"
            progress = metadata_dir / "progress" / "100.json"
            exporter.save_progress_state(
                progress,
                root_page_id="100",
                depth_limit=2,
                pages={"100": root},
                queue=deque(),
                enqueued={"100"},
            )
            entry = exporter.FeedEntry("300", "Unknown Path", unknown.url, "2026-01-03T00:00:00Z", version_number=3)

            with mock.patch.object(exporter, "fetch_rss_entries", return_value=[entry]), mock.patch.object(
                exporter, "fetch_page", return_value=unknown
            ):
                result = exporter.update_root_from_rss(
                    object(),
                    root_page_id="100",
                    site_base="https://wiki.example.com",
                    output_dir=output_dir,
                    metadata_dir=metadata_dir,
                    depth_limit=2,
                    rss_url="https://wiki.example.com/rss",
                    include_new=True,
                )

            self.assertEqual(result.updated_page_ids, [])
            self.assertEqual(result.ignored_page_records[0]["reason"], "missing_ancestors")


if __name__ == "__main__":
    unittest.main()
