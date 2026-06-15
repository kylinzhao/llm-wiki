"""Tests for RSS adaptive expansion: overlap detection and tier escalation."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
EXPORTER = TOOLS_DIR / "confluence_sync" / "export_confluence_tree.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_confluence_tree", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_confluence_tree"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_entry(page_id, version, updated_at="2026-06-01T00:00:00+00:00"):
    """Create a FeedEntry-like mock."""
    entry = MagicMock()
    entry.page_id = page_id
    entry.version_number = version
    entry.updated_at = updated_at
    entry.published_at = updated_at
    entry.title = f"Page {page_id}"
    return entry


def make_page(version, updated_at="2026-06-01T00:00:00+00:00"):
    """Create a PageNode-like mock."""
    page = MagicMock()
    page.version_number = version
    page.updated_at = updated_at
    return page


class CountRssOverlapTests(unittest.TestCase):
    def setUp(self):
        self.exporter = load_exporter()

    def test_empty_entries_returns_zero(self):
        pages = {"100": make_page(5)}
        self.assertEqual(self.exporter.count_rss_overlap([], pages), 0)

    def test_empty_pages_returns_zero(self):
        entries = [make_entry("100", 5)]
        self.assertEqual(self.exporter.count_rss_overlap(entries, {}), 0)

    def test_full_overlap(self):
        """All entries are already known with matching versions."""
        entries = [make_entry("1", 5), make_entry("2", 3), make_entry("3", 7)]
        pages = {"3": make_page(7), "2": make_page(3), "1": make_page(5)}
        # Tail is entry "3" (version 7 == 7), then "2" (3 == 3), then "1" (5 == 5)
        overlap = self.exporter.count_rss_overlap(entries, pages)
        self.assertEqual(overlap, 3)

    def test_partial_overlap_from_tail(self):
        """Only the last N entries match — oldest ones are known."""
        entries = [
            make_entry("1", 10),   # newest, version newer than progress
            make_entry("2", 10),   # newer
            make_entry("3", 5),    # matches progress
            make_entry("4", 3),    # matches progress
            make_entry("5", 7),    # matches progress (oldest)
        ]
        pages = {
            "1": make_page(5),     # progress has version 5, RSS has 10 → newer
            "2": make_page(5),     # same
            "3": make_page(5),     # matches
            "4": make_page(3),     # matches
            "5": make_page(7),     # matches
        }
        overlap = self.exporter.count_rss_overlap(entries, pages)
        self.assertEqual(overlap, 3)

    def test_no_overlap_when_all_newer(self):
        """All RSS entries are newer than progress."""
        entries = [make_entry("1", 10), make_entry("2", 10)]
        pages = {"1": make_page(5), "2": make_page(5)}
        overlap = self.exporter.count_rss_overlap(entries, pages)
        self.assertEqual(overlap, 0)

    def test_overlap_stops_at_unknown_page(self):
        """Overlap counting stops when hitting an unknown page_id."""
        entries = [
            make_entry("1", 5),    # index 0 (newest)
            make_entry("2", 5),    # index 1
            make_entry("999", 5),  # index 2 (not in pages)
            make_entry("3", 5),    # index 3 (oldest)
        ]
        pages = {"1": make_page(5), "2": make_page(5), "3": make_page(5)}
        overlap = self.exporter.count_rss_overlap(entries, pages)
        # reversed: ["3", "999", "2", "1"]
        # "3" is in pages (5==5) → overlap++  (=1)
        # "999" not in pages → break
        self.assertEqual(overlap, 1)

    def test_overlap_stops_at_newer_entry(self):
        """Overlap counting stops when finding an entry newer than progress."""
        entries = [
            make_entry("1", 5),
            make_entry("2", 10),   # newer than progress
            make_entry("3", 5),    # matches (oldest)
        ]
        pages = {"1": make_page(5), "2": make_page(5), "3": make_page(5)}
        overlap = self.exporter.count_rss_overlap(entries, pages)
        # reversed: "3"(match) → "2"(newer, stop) → overlap=1
        self.assertEqual(overlap, 1)


class ResolveAdaptiveRssMaxResultsTests(unittest.TestCase):
    def setUp(self):
        self.exporter = load_exporter()

    def _mock_session(self, feed_factory):
        """Create a mock session whose get returns different feeds per maxResults."""
        session = MagicMock()

        def fake_fetch(rss_url):
            # Parse maxResults from URL
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(rss_url)
            params = parse_qs(parsed.query)
            max_results = int(params.get("maxResults", ["50"])[0])
            return feed_factory(max_results)

        return session, fake_fetch

    def test_overlap_at_first_tier(self):
        """When the initial batch already has overlap, return it without expansion."""
        exporter = self.exporter

        # 50 entries, all matching progress
        entries = [make_entry(str(i), 5) for i in range(50)]
        pages = {str(i): make_page(5) for i in range(50)}

        session = MagicMock()
        with patch.object(exporter, "fetch_rss_entries", return_value=entries):
            max_results, overlap = exporter.resolve_adaptive_rss_max_results(
                session,
                "https://example.com/rss?maxResults=50",
                pages,
                initial_max=50,
                overlap_threshold=5,
            )
        self.assertEqual(max_results, 50)
        self.assertTrue(overlap)

    def test_expansion_needed(self):
        """First tier has no overlap, second tier does."""
        exporter = self.exporter

        pages = {str(i): make_page(5) for i in range(200)}

        # Fetch returns all-newer entries for small batches, but at 100+
        # the tail contains known pages.
        def fake_fetch(session, rss_url):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(rss_url)
            params = parse_qs(parsed.query)
            mr = int(params.get("maxResults", ["50"])[0])
            entries = []
            for i in range(mr):
                if mr <= 50:
                    # At 50: all entries are new pages not in progress
                    entries.append(make_entry(str(i + 10000), 10))
                else:
                    # At 100+: last 10 entries match known pages
                    if i < mr - 10:
                        entries.append(make_entry(str(i + 10000), 10))
                    else:
                        entries.append(make_entry(str(i), 5))
            return entries

        with patch.object(exporter, "fetch_rss_entries", side_effect=fake_fetch):
            max_results, overlap = exporter.resolve_adaptive_rss_max_results(
                MagicMock(),
                "https://example.com/rss?maxResults=50",
                pages,
                initial_max=50,
                overlap_threshold=5,
            )
        self.assertTrue(overlap)
        self.assertGreaterEqual(max_results, 100)

    def test_no_overlap_at_any_tier(self):
        """When no tier finds overlap, return the largest tier and overlap=False."""
        exporter = self.exporter

        pages = {}  # empty progress

        def fake_fetch(session, rss_url):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(rss_url)
            params = parse_qs(parsed.query)
            mr = int(params.get("maxResults", ["50"])[0])
            return [make_entry(str(i), 1) for i in range(mr)]

        with patch.object(exporter, "fetch_rss_entries", side_effect=fake_fetch):
            max_results, overlap = exporter.resolve_adaptive_rss_max_results(
                MagicMock(),
                "https://example.com/rss?maxResults=50",
                pages,
                initial_max=50,
                tiers=[50, 100, 200],
            )
        self.assertFalse(overlap)
        self.assertEqual(max_results, 200)

    def test_feed_exhausted_before_overlap(self):
        """Confluence returns fewer entries than requested — feed window ended."""
        exporter = self.exporter

        pages = {}

        def fake_fetch(session, rss_url):
            # Always return only 30 entries regardless of max_results
            return [make_entry(str(i), 1) for i in range(30)]

        with patch.object(exporter, "fetch_rss_entries", side_effect=fake_fetch):
            max_results, overlap = exporter.resolve_adaptive_rss_max_results(
                MagicMock(),
                "https://example.com/rss?maxResults=50",
                pages,
                initial_max=50,
            )
        self.assertFalse(overlap)
        # Should stop at first tier since feed is exhausted
        self.assertEqual(max_results, 50)

    def test_fixed_mode_bypasses_adaptive(self):
        """When initial_max > 0 and equals a tier, still works correctly."""
        exporter = self.exporter
        entries = [make_entry(str(i), 5) for i in range(50)]
        pages = {str(i): make_page(5) for i in range(50)}
        session = MagicMock()
        with patch.object(exporter, "fetch_rss_entries", return_value=entries):
            max_results, overlap = exporter.resolve_adaptive_rss_max_results(
                session,
                "https://example.com/rss?maxResults=50",
                pages,
                initial_max=50,
                overlap_threshold=5,
            )
        self.assertTrue(overlap)
        self.assertEqual(max_results, 50)


if __name__ == "__main__":
    unittest.main()
