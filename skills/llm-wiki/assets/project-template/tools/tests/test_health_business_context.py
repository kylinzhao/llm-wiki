import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_health():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location("health", TOOLS_DIR / "health.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_minimal_project(project: Path) -> None:
    (project / "raw" / "product").mkdir(parents=True)
    (project / "raw" / "product" / "index.md").write_text("# Product\n", encoding="utf-8")
    (project / "wiki").mkdir()
    (project / "wiki" / "index.md").write_text("# Wiki\n", encoding="utf-8")
    (project / "wiki" / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "retrieval-playbook.md").write_text("# Retrieval\n", encoding="utf-8")
    (project / "docs" / "build-and-maintenance.md").write_text("# Build\n", encoding="utf-8")
    (project / "staging").mkdir()
    (project / "staging" / "refinement-status.md").write_text("# Status\n", encoding="utf-8")


class HealthBusinessContextTest(unittest.TestCase):
    def test_missing_business_context_is_required(self):
        health = load_health()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_minimal_project(project)

            report = health.build_report(project)

            self.assertFalse(report["ok"])
            self.assertFalse(report["has_business_context"])
            self.assertIn("BUSINESS_CONTEXT.md", report["missing_required_paths"])

    def test_template_placeholder_business_context_is_not_valid(self):
        health = load_health()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_minimal_project(project)
            (project / "BUSINESS_CONTEXT.md").write_text(
                "# BUSINESS_CONTEXT\n\n"
                "> TODO: 请在首次构建前补全本文件。它是 LLM Wiki 的业务语义基线。\n\n"
                "- 项目名称：TODO\n",
                encoding="utf-8",
            )

            report = health.build_report(project)

            self.assertFalse(report["ok"])
            self.assertTrue(report["has_business_context"])
            self.assertFalse(report["has_valid_business_context"])
            self.assertIn("BUSINESS_CONTEXT.md", report["missing_required_paths"])

    def test_filled_business_context_satisfies_required_input(self):
        health = load_health()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_minimal_project(project)
            (project / "BUSINESS_CONTEXT.md").write_text(
                "# BUSINESS_CONTEXT\n\n"
                "## 1) 项目与业务边界\n\n"
                "- 项目名称：二手车知识库\n"
                "- 目标用户/角色：运营、产品、研发、客服\n"
                "- 核心业务目标：统一历史需求和当前执行口径。\n\n"
                "## 2) 关键实体与术语归一\n\n"
                "- 车源：平台内可售车辆，主键为 car_id。\n"
                "- 订单：买卖双方围绕车源达成的交易过程。\n\n"
                "## 3) 规则与约束\n\n"
                "- 冲突时以最新已发布 PRD 和当前业务 owner 确认为准。\n",
                encoding="utf-8",
            )

            report = health.build_report(project)

            self.assertTrue(report["ok"])
            self.assertTrue(report["has_valid_business_context"])
            self.assertNotIn("BUSINESS_CONTEXT.md", report["missing_required_paths"])

    def test_health_reports_cjira_registry_summary(self):
        health = load_health()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_minimal_project(project)
            (project / "BUSINESS_CONTEXT.md").write_text(
                "# BUSINESS_CONTEXT\n\n- 项目名称：二手车知识库\n- 目标用户/角色：运营\n- 核心业务目标：统一需求口径。\n",
                encoding="utf-8",
            )
            registry_dir = project / "staging" / "cjira-registry"
            registry_dir.mkdir(parents=True)
            (registry_dir / "active.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-26T00:00:00+00:00",
                        "records": [
                            {
                                "page_path": "raw/idea/index.md",
                                "doc_status": "idea",
                                "confidence": "medium",
                                "primary_cjira_status": "",
                            },
                            {
                                "page_path": "raw/product/index.md",
                                "doc_status": "in_progress",
                                "confidence": "low",
                                "primary_cjira_status": "",
                            },
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (registry_dir / "archive.json").write_text(
                json.dumps({"generated_at": "2026-05-26T00:00:00+00:00", "records": []}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (registry_dir / "cache.json").write_text(
                json.dumps(
                    {
                        "PSP-40038": {
                            "issue_key": "PSP-40038",
                            "status": "",
                            "terminal": False,
                            "last_checked_at": "2026-05-26T00:00:00+00:00",
                            "fetch_failed": True,
                        }
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            report = health.build_report(project)

            self.assertEqual(
                report["cjira_registry"],
                {
                    "active_pages": 2,
                    "archived_pages": 0,
                    "idea_pages": 1,
                    "in_progress_pages": 1,
                    "frozen_pages": 0,
                    "low_confidence_pages": 1,
                    "stale_status_pages": 1,
                },
            )
