import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_cjira_registry():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("cjira_registry", TOOLS_DIR / "cjira_registry.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_build_wiki():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("build_wiki", TOOLS_DIR / "build_wiki.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CjiraRegistryExtractionTest(unittest.TestCase):
    def test_revision_table_issue_becomes_primary_cjira(self):
        registry = load_cjira_registry()
        text = """
| 更新时间 | 修改内容 | cjira |
| --- | --- | --- |
| 2026-05-01 | 调整调价规则 | PSP-40038 |
"""

        record = registry.classify_page("8.动销平台_自营政策调价", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "PSP-40038")
        self.assertEqual(record["supporting_cjira"], [])
        self.assertEqual(record["confidence"], "high")

    def test_issue_under_jira_heading_becomes_supporting_cjira(self):
        registry = load_cjira_registry()
        text = """
| 更新时间 | 修改内容 | cjira |
| --- | --- | --- |
| 2026-05-01 | 调整调价规则 | PSP-40038 |

## 【JIRA 编号】

OP-42513
"""

        record = registry.classify_page("8.动销平台_自营政策调价", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "PSP-40038")
        self.assertEqual(record["supporting_cjira"], ["OP-42513"])

    def test_multiple_primary_candidates_reduce_confidence(self):
        registry = load_cjira_registry()
        text = """
| 更新时间 | 修改内容 | cjira |
| --- | --- | --- |
| 2026-05-01 | A 调整 | PSP-40038 |
| 2026-05-02 | B 调整 | PSP-40039 |
"""

        record = registry.classify_page("8.动销平台_自营政策调价", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "PSP-40038")
        self.assertEqual(record["confidence"], "low")

    def test_title_idea_marker_forces_idea_status(self):
        registry = load_cjira_registry()
        text = "这是一个正式立项前的方案草稿。"

        record = registry.classify_page("【IDEA】调价策略探索", "raw/product/index.md", text)

        self.assertTrue(record["idea_flag"])
        self.assertEqual(record["doc_status"], "idea")
        self.assertEqual(record["confidence"], "high")

    def test_semantic_idea_phrases_can_mark_idea_with_medium_confidence(self):
        registry = load_cjira_registry()
        text = """
这是一个概念探索，记录候选方向与后续可能立项的需求。
当前仅作为方案预研，不代表已经承诺上线。
"""

        record = registry.classify_page("调价策略探索", "raw/product/index.md", text)

        self.assertTrue(record["idea_flag"])
        self.assertEqual(record["doc_status"], "idea")
        self.assertEqual(record["confidence"], "medium")

    def test_image_filename_like_token_is_not_treated_as_jira(self):
        registry = load_cjira_registry()
        text = """
下单方 <img alt="" src="assets/WX20240814-152731.png"/>
"""

        record = registry.classify_page("创建复检工单", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "")
        self.assertEqual(record["supporting_cjira"], [])

    def test_asset_encoded_fragment_is_not_treated_as_jira(self):
        registry = load_cjira_registry()
        text = """
![image](assets/E8-87-AA-E8-90-A5-E9-87-87-E9-94-80-E5-B9-B3-E5-8F-B0.png)
"""

        record = registry.classify_page("2月总部买手运营调研", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "")
        self.assertEqual(record["supporting_cjira"], [])

    def test_loading_issue_detail_placeholder_does_not_hide_project_jira_links(self):
        registry = load_cjira_registry()
        text = """
<a href="http://project.guazi-corp.com/browse/CTB-7850">CTB-7850</a>
正在获取问题细节。。。
<a href="http://project.guazi-corp.com/browse/CTB-8017">CTB-8017</a>
正在获取问题细节。。。
<a href="http://project.guazi-corp.com/browse/AUCT-676">AUCT-676</a>
正在获取问题细节。。。
"""

        record = registry.classify_page("商好多V1.7_车商简报+诊断", "raw/product/index.md", text)

        self.assertEqual(record["primary_cjira"], "CTB-7850")
        self.assertEqual(record["supporting_cjira"], ["CTB-8017", "AUCT-676"])
        self.assertEqual(record["confidence"], "low")


class CjiraRegistryPersistenceTest(unittest.TestCase):
    def test_active_registry_is_written_for_idea_and_non_terminal_pages(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "【IDEA】调价策略探索",
                    "raw_path": "raw/idea/index.md",
                    "text": "方案预研，尚未立项。",
                },
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | OP-42513 |",
                },
            ]
            status_by_key = {
                "OP-42513": {"status": "In Progress", "terminal": False},
            }

            registry.update_registry_for_sources(project, sources, refresh_status=True, status_by_key=status_by_key)

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            archive_payload = json.loads((project / "staging" / "cjira-registry" / "archive.json").read_text(encoding="utf-8"))
            self.assertEqual(len(active_payload["records"]), 2)
            self.assertEqual(archive_payload["records"], [])
            self.assertEqual(active_payload["records"][0]["doc_status"], "idea")
            self.assertEqual(active_payload["records"][1]["primary_cjira_status"], "In Progress")

    def test_terminal_primary_issue_moves_page_to_archive(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]
            status_by_key = {
                "PSP-40038": {"status": "Done", "terminal": True},
            }

            registry.update_registry_for_sources(project, sources, refresh_status=True, status_by_key=status_by_key)

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            archive_payload = json.loads((project / "staging" / "cjira-registry" / "archive.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload["records"], [])
            self.assertEqual(len(archive_payload["records"]), 1)
            self.assertEqual(archive_payload["records"][0]["doc_status"], "frozen")

    def test_shipped_primary_issue_moves_page_to_archive(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]
            status_by_key = {
                "PSP-40038": {"status": "已上线", "terminal": registry.is_terminal_status("已上线")},
            }

            registry.update_registry_for_sources(project, sources, refresh_status=True, status_by_key=status_by_key)

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            archive_payload = json.loads((project / "staging" / "cjira-registry" / "archive.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload["records"], [])
            self.assertEqual(len(archive_payload["records"]), 1)
            self.assertEqual(archive_payload["records"][0]["primary_cjira_status"], "已上线")
            self.assertEqual(archive_payload["records"][0]["doc_status"], "frozen")

    def test_archive_writes_happen_before_active_pruning(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]
            status_by_key = {
                "PSP-40038": {"status": "Done", "terminal": True},
            }

            registry.update_registry_for_sources(project, sources, refresh_status=True, status_by_key=status_by_key)
            active_records, archive_records, _ = registry.read_registry(project)

            self.assertEqual(active_records, [])
            self.assertEqual(len(archive_records), 1)
            self.assertEqual(archive_records[0]["primary_cjira"], "PSP-40038")

    def test_failed_or_unknown_status_remains_active(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]
            status_by_key = {
                "PSP-40038": {"status": "Blocked", "terminal": False, "fetch_failed": True},
            }

            registry.update_registry_for_sources(project, sources, refresh_status=True, status_by_key=status_by_key)

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            self.assertEqual(len(active_payload["records"]), 1)
            self.assertEqual(active_payload["records"][0]["doc_status"], "in_progress")
            self.assertEqual(active_payload["records"][0]["primary_cjira_status"], "Blocked")

    def test_unreferenced_cache_entries_are_pruned_on_rebuild(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            root = project / "staging" / "cjira-registry"
            root.mkdir(parents=True)
            (root / "active.json").write_text(
                json.dumps({"generated_at": "2026-05-26T00:00:00+00:00", "records": []}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "archive.json").write_text(
                json.dumps({"generated_at": "2026-05-26T00:00:00+00:00", "records": []}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "cache.json").write_text(
                json.dumps(
                    {
                        "WX20240814-152731": {"issue_key": "WX20240814-152731", "fetch_failed": True},
                        "PSP-40038": {"issue_key": "PSP-40038", "status": "In Progress", "terminal": False},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]

            registry.update_registry_for_sources(project, sources, refresh_status=False)

            cache_payload = json.loads((root / "cache.json").read_text(encoding="utf-8"))
            self.assertNotIn("WX20240814-152731", cache_payload)
            self.assertIn("PSP-40038", cache_payload)

    def test_refresh_backfills_live_status_into_existing_source_page(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text(
                "---\n"
                "title: '8.动销平台_自营政策调价'\n"
                "page_id: '665758297'\n"
                "---\n\n"
                "# 8.动销平台_自营政策调价\n\n"
                '<a href="https://cjira.guazi-corp.com/browse/PSP-40038">PSP-40038</a>\n',
                encoding="utf-8",
            )
            source_page = project / "wiki" / "sources" / "product-index.md"
            source_page.parent.mkdir(parents=True)
            source_page.write_text(
                """# 8.动销平台_自营政策调价

## Delivery Tracking

- Primary Jira: `PSP-40038`
- Supporting Jira: `none`
- Jira Status: ``
- Last Checked: ``
- Confidence: `high`

## Source Metadata
```json
{
  "raw_hash": "placeholder",
  "raw_rel": "raw/product/index.md",
  "primary_cjira": "PSP-40038",
  "primary_cjira_status": "",
  "last_checked_at": "",
  "ai_refinement_state": "complete"
}
```
""",
                encoding="utf-8",
            )

            registry.update_registry_for_sources(
                project,
                [registry.read_source_file(raw_page, project)],
                refresh_status=True,
                status_by_key={
                    "PSP-40038": {
                        "issue_key": "PSP-40038",
                        "status": "开发中",
                        "terminal": False,
                        "last_checked_at": "2026-05-26T12:34:00+00:00",
                    }
                },
            )

            source_text = source_page.read_text(encoding="utf-8")
            self.assertIn("- Jira Status: `开发中`", source_text)
            self.assertIn("- Last Checked: `2026-05-26T12:34:00+00:00`", source_text)
            self.assertIn('"primary_cjira_status": "开发中"', source_text)


class CjiraRegistryStatusRefreshTest(unittest.TestCase):
    def test_fetch_jira_status_calls_issue_api_and_reads_status_name(self):
        registry = load_cjira_registry()
        session = mock.Mock()
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"fields": {"status": {"name": "In Progress"}}}
        session.get.return_value = response

        result = registry.fetch_jira_status(
            "PSP-40038",
            jira_base="https://cjira.guazi-corp.com",
            headers={"Authorization": "Bearer token"},
            session=session,
        )

        session.get.assert_called_once_with(
            "https://cjira.guazi-corp.com/rest/api/2/issue/PSP-40038",
            headers={"Authorization": "Bearer token"},
            timeout=30,
        )
        self.assertEqual(result["status"], "In Progress")
        self.assertFalse(result["terminal"])

    def test_terminal_statuses_are_classified(self):
        registry = load_cjira_registry()

        for status in ("Done", "Closed", "Resolved", "已完成", "已关闭", "已解决", "已上线"):
            self.assertTrue(registry.is_terminal_status(status), status)

    def test_lookup_failure_records_stale_cache_and_keeps_record_active(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "8.动销平台_自营政策调价",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 调价 | PSP-40038 |",
                }
            ]

            with mock.patch.object(registry, "fetch_jira_status", side_effect=RuntimeError("boom")):
                registry.update_registry_for_sources(
                    project,
                    sources,
                    refresh_status=True,
                    jira_base="https://cjira.guazi-corp.com",
                    headers={"Authorization": "Bearer token"},
                    session=mock.Mock(),
                )

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            cache_payload = json.loads((project / "staging" / "cjira-registry" / "cache.json").read_text(encoding="utf-8"))
            self.assertEqual(len(active_payload["records"]), 1)
            self.assertEqual(active_payload["records"][0]["doc_status"], "in_progress")
            self.assertEqual(active_payload["records"][0]["primary_cjira_status"], "")
            self.assertTrue(cache_payload["PSP-40038"]["fetch_failed"])

    def test_cjira_lookup_failure_uses_legacy_project_jira_reference_without_api(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "历史 Jira 需求",
                    "raw_path": "raw/product/index.md",
                    "text": (
                        "| 修改内容 | cjira |\n"
                        "| --- | --- |\n"
                        '| 上线 | <a href="http://project.guazi-corp.com/browse/CTB-7850">CTB-7850</a> |'
                    ),
                }
            ]

            def fake_fetch(issue_key, *, jira_base, headers, session):
                self.assertEqual(issue_key, "CTB-7850")
                self.assertEqual(jira_base, "https://cjira.guazi-corp.com")
                raise RuntimeError("not found in cjira")

            with mock.patch.object(registry, "fetch_jira_status", side_effect=fake_fetch):
                registry.update_registry_for_sources(
                    project,
                    sources,
                    refresh_status=True,
                    jira_base="https://cjira.guazi-corp.com",
                    headers={"Authorization": "Bearer current"},
                    session=mock.Mock(),
                )

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            archive_payload = json.loads((project / "staging" / "cjira-registry" / "archive.json").read_text(encoding="utf-8"))
            cache_payload = json.loads((project / "staging" / "cjira-registry" / "cache.json").read_text(encoding="utf-8"))

            self.assertEqual(active_payload["records"], [])
            self.assertEqual(len(archive_payload["records"]), 1)
            record = archive_payload["records"][0]
            self.assertEqual(record["doc_status"], "frozen")
            self.assertEqual(record["primary_cjira_status"], "已上线（legacy project Jira reference）")
            self.assertTrue(record["primary_cjira_terminal"])
            self.assertEqual(record["status_source"], "legacy_project_jira_reference")
            self.assertTrue(cache_payload["CTB-7850"]["legacy_project_jira_reference"])

    def test_plain_issue_without_legacy_project_url_remains_active_when_cjira_fails(self):
        registry = load_cjira_registry()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = [
                {
                    "title": "纯文本 Jira 需求",
                    "raw_path": "raw/product/index.md",
                    "text": "| 修改内容 | cjira |\n| --- | --- |\n| 待确认 | CTB-7850 |",
                }
            ]

            with mock.patch.object(registry, "fetch_jira_status", side_effect=RuntimeError("not found in cjira")):
                registry.update_registry_for_sources(
                    project,
                    sources,
                    refresh_status=True,
                    jira_base="https://cjira.guazi-corp.com",
                    headers={"Authorization": "Bearer current"},
                    session=mock.Mock(),
                )

            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            archive_payload = json.loads((project / "staging" / "cjira-registry" / "archive.json").read_text(encoding="utf-8"))
            cache_payload = json.loads((project / "staging" / "cjira-registry" / "cache.json").read_text(encoding="utf-8"))

            self.assertEqual(len(active_payload["records"]), 1)
            self.assertEqual(archive_payload["records"], [])
            self.assertEqual(active_payload["records"][0]["doc_status"], "in_progress")
            self.assertTrue(cache_payload["CTB-7850"]["fetch_failed"])
            self.assertFalse(cache_payload["CTB-7850"].get("legacy_project_jira_reference", False))


class CjiraRegistryEndToEndTest(unittest.TestCase):
    def test_registry_covers_idea_primary_and_supporting_issue_pages(self):
        registry = load_cjira_registry()
        build_wiki = load_build_wiki()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            product_page = project / "raw" / "product" / "index.md"
            product_page.parent.mkdir(parents=True)
            product_page.write_text(
                "# 正常需求页\n\n"
                "| 更新时间 | 修改内容 | cjira |\n"
                "| --- | --- | --- |\n"
                "| 2026-05-01 | 调价 | PSP-40038 |\n",
                encoding="utf-8",
            )
            idea_page = project / "raw" / "idea" / "index.md"
            idea_page.parent.mkdir(parents=True)
            idea_page.write_text(
                "# 【IDEA】探索页\n\n这是一个方案预研，暂未承诺上线。\n",
                encoding="utf-8",
            )
            support_page = project / "raw" / "support" / "index.md"
            support_page.parent.mkdir(parents=True)
            support_page.write_text(
                "# 带 supporting issue 的页面\n\n"
                "| 更新时间 | 修改内容 | cjira |\n"
                "| --- | --- | --- |\n"
                "| 2026-05-01 | 主需求 | PSP-50001 |\n\n"
                "## 【JIRA 编号】\n\n"
                "OP-42513\n",
                encoding="utf-8",
            )

            build_wiki.main_for_project(project)
            manifest_before = json.loads((project / "staging" / "source-manifest.json").read_text(encoding="utf-8"))
            registry.update_registry_for_sources(project, manifest_before["sources"], refresh_status=False)
            manifest_after = json.loads((project / "staging" / "source-manifest.json").read_text(encoding="utf-8"))
            active_payload = json.loads((project / "staging" / "cjira-registry" / "active.json").read_text(encoding="utf-8"))
            records = {item["page_path"]: item for item in active_payload["records"]}

            self.assertEqual(len(active_payload["records"]), 3)
            self.assertEqual(records["raw/idea/index.md"]["doc_status"], "idea")
            self.assertEqual(records["raw/product/index.md"]["primary_cjira"], "PSP-40038")
            self.assertEqual(records["raw/support/index.md"]["primary_cjira"], "PSP-50001")
            self.assertEqual(records["raw/support/index.md"]["supporting_cjira"], ["OP-42513"])
            self.assertEqual(manifest_before, manifest_after)


if __name__ == "__main__":
    unittest.main()
