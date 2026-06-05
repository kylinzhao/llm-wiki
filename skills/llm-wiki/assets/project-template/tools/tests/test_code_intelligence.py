from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scan_code
import build_traceability
from build_traceability import build_code_seed_row
from code_intelligence import (
    adapt_upstream_artifacts,
    collect_upstream_summary,
    detect_upstream_code_intelligence,
    load_code_intelligence_registry,
    resolve_code_intelligence,
    save_code_intelligence_registry,
)


class CodeIntelligenceRegistryTests(unittest.TestCase):
    def test_load_registry_defaults_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertEqual(load_code_intelligence_registry(project), {"codebases": {}})

    def test_save_and_load_registry_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            payload = {
                "codebases": {
                    "sell-taro": {
                        "upstream_type": "guazi-flow-wiki",
                        "discovery_mode": "explicit",
                    }
                }
            }
            save_code_intelligence_registry(project, payload)
            self.assertEqual(load_code_intelligence_registry(project), payload)


class DetectUpstreamIntelligenceTests(unittest.TestCase):
    def test_no_upstream_defaults_to_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw-code" / "empty-app").mkdir(parents=True)
            result = detect_upstream_code_intelligence(project, "empty-app")
            self.assertEqual(result["codebase_id"], "empty-app")
            self.assertEqual(result["upstream_type"], "none")
            self.assertEqual(result["discovery_mode"], "none")

    def test_detects_guazi_flow_wiki_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs_wiki = project / "raw-code" / "sell-taro" / "docs" / "wiki"
            docs_wiki.mkdir(parents=True)
            for rel in ("INDEX.md", "CONTEXT.md", "schema.md", "source-map.jsonl", "index.json"):
                (docs_wiki / rel).write_text("x", encoding="utf-8")

            result = detect_upstream_code_intelligence(project, "sell-taro")
            self.assertEqual(result["upstream_type"], "guazi-flow-wiki")
            self.assertEqual(result["discovery_mode"], "auto-detected")
            self.assertEqual(result["root"], "raw-code/sell-taro/docs/wiki")

    def test_explicit_registry_entry_overrides_auto_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs_wiki = project / "raw-code" / "sell-taro" / "docs" / "wiki"
            docs_wiki.mkdir(parents=True)
            for rel in ("INDEX.md", "CONTEXT.md", "schema.md", "source-map.jsonl", "index.json"):
                (docs_wiki / rel).write_text("x", encoding="utf-8")

            save_code_intelligence_registry(
                project,
                {
                    "codebases": {
                        "sell-taro": {
                            "codebase_id": "sell-taro",
                            "upstream_type": "custom-explicit",
                            "discovery_mode": "explicit",
                            "root": "raw-code/sell-taro/custom/wiki",
                            "index_path": "raw-code/sell-taro/custom/wiki/INDEX.md",
                        }
                    }
                },
            )

            result = resolve_code_intelligence(project, "sell-taro")
            self.assertEqual(result["upstream_type"], "custom-explicit")
            self.assertEqual(result["discovery_mode"], "explicit")

    def test_collect_upstream_summary_reads_index_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs_wiki = project / "raw-code" / "sell-taro" / "docs" / "wiki"
            docs_wiki.mkdir(parents=True)
            (docs_wiki / "INDEX.md").write_text("# sell-taro 知识库\n", encoding="utf-8")
            (docs_wiki / "CONTEXT.md").write_text("# context\n", encoding="utf-8")
            (docs_wiki / "schema.md").write_text("# schema\n", encoding="utf-8")
            (docs_wiki / "source-map.jsonl").write_text('{"path":"src/app.tsx"}\n', encoding="utf-8")
            (docs_wiki / "index.json").write_text(
                json.dumps(
                    {
                        "topics": [{"slug": "project-overview", "title": "Project Overview", "keywords": ["route"]}],
                        "concepts": [{"slug": "unified-runtime-infrastructure", "title": "Unified Runtime Infrastructure"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            resolved = detect_upstream_code_intelligence(project, "sell-taro")
            summary = collect_upstream_summary(project, "sell-taro", resolved)
            self.assertEqual(summary["upstream_type"], "guazi-flow-wiki")
            self.assertEqual(summary["topic_count"], 1)
            self.assertEqual(summary["concept_count"], 1)
            self.assertEqual(summary["source_map_entries"], 1)

    def test_adapt_upstream_artifacts_writes_compact_topics_concepts_and_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs_wiki = project / "raw-code" / "sell-taro" / "docs" / "wiki"
            docs_wiki.mkdir(parents=True)
            (docs_wiki / "INDEX.md").write_text("# sell-taro 知识库\n", encoding="utf-8")
            (docs_wiki / "CONTEXT.md").write_text("# context\n", encoding="utf-8")
            (docs_wiki / "schema.md").write_text("# schema\n", encoding="utf-8")
            (docs_wiki / "source-map.jsonl").write_text(
                '{"path":"src/app.tsx","topic":"project-overview"}\nnot-json\n',
                encoding="utf-8",
            )
            (docs_wiki / "index.json").write_text(
                json.dumps(
                    {
                        "topics": [{"slug": "project-overview", "title": "Project Overview", "keywords": ["route"], "path": "topics/project-overview.md"}],
                        "concepts": [{"slug": "runtime", "title": "Runtime", "aliases": ["app runtime"]}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            resolved = detect_upstream_code_intelligence(project, "sell-taro")
            result = adapt_upstream_artifacts(project, "sell-taro", resolved)

            self.assertEqual(result["adapter_status"], "ok_with_warnings")
            out_dir = project / "staging" / "code-graph" / "sell-taro"
            topics = json.loads(out_dir.joinpath("upstream-topics.json").read_text(encoding="utf-8"))
            concepts = json.loads(out_dir.joinpath("upstream-concepts.json").read_text(encoding="utf-8"))
            source_map = json.loads(out_dir.joinpath("upstream-source-map.json").read_text(encoding="utf-8"))
            self.assertEqual(topics["topics"][0]["id"], "project-overview")
            self.assertEqual(concepts["concepts"][0]["aliases"], ["app runtime"])
            self.assertEqual(source_map["entries"][0]["path"], "src/app.tsx")
            self.assertEqual(source_map["warning_count"], 1)


class ScanAndHealthIntegrationTests(unittest.TestCase):
    def test_scan_code_writes_upstream_artifacts_and_page_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs_wiki = project / "raw-code" / "sell-taro" / "docs" / "wiki"
            docs_wiki.mkdir(parents=True)
            (docs_wiki / "INDEX.md").write_text("# sell-taro 知识库\n", encoding="utf-8")
            (docs_wiki / "CONTEXT.md").write_text("# context\n", encoding="utf-8")
            (docs_wiki / "schema.md").write_text("# schema\n", encoding="utf-8")
            (docs_wiki / "source-map.jsonl").write_text('{"path":"src/app.tsx"}\n', encoding="utf-8")
            (docs_wiki / "index.json").write_text(
                json.dumps(
                    {
                        "topics": [{"slug": "project-overview", "title": "Project Overview"}],
                        "concepts": [{"slug": "runtime", "title": "Runtime"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (project / "raw-code" / "sell-taro" / "package.json").write_text('{"name":"sell-taro"}', encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const route = '/app';\n", encoding="utf-8")

            result = scan_code.scan_codebase(project, project / "raw-code" / "sell-taro")
            self.assertEqual(result["upstream_type"], "guazi-flow-wiki")

            upstream_summary = project / "staging" / "code-graph" / "sell-taro" / "upstream-summary.json"
            self.assertTrue(upstream_summary.is_file())
            self.assertTrue((project / "staging" / "code-graph" / "sell-taro" / "upstream-topics.json").is_file())
            self.assertTrue((project / "staging" / "code-graph" / "sell-taro" / "upstream-concepts.json").is_file())
            self.assertTrue((project / "staging" / "code-graph" / "sell-taro" / "upstream-source-map.json").is_file())
            page = project / "wiki" / "code" / "codebases" / "sell-taro" / "index.md"
            content = page.read_text(encoding="utf-8")
            self.assertIn("## Upstream Code Intelligence", content)
            self.assertIn("`guazi-flow-wiki`", content)
            self.assertIn("Adapter status: `ok`", content)
            self.assertIn("Preferred entry: `raw-code/sell-taro/docs/wiki/INDEX.md`", content)

    def test_health_reports_detected_upstream_code_intelligence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw").mkdir()
            (project / "BUSINESS_CONTEXT.md").write_text(
                "# BUSINESS_CONTEXT\n\n"
                "项目与业务边界：代码能力测试项目。\n\n"
                "关键实体：测试 codebase。\n\n"
                "规则与约束：健康检查需识别上游代码智能状态。\n",
                encoding="utf-8",
            )
            (project / "wiki").mkdir(parents=True)
            (project / "wiki" / "index.md").write_text("# index\n", encoding="utf-8")
            (project / "wiki" / "overview.md").write_text("# overview\n", encoding="utf-8")
            (project / "docs").mkdir()
            (project / "docs" / "retrieval-playbook.md").write_text("# retrieval\n", encoding="utf-8")
            (project / "docs" / "build-and-maintenance.md").write_text("# build\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "refinement-status.md").write_text("{}", encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const App = 1;\n", encoding="utf-8")
            out_dir = project / "staging" / "code-graph" / "sell-taro"
            out_dir.mkdir(parents=True)
            out_dir.joinpath("upstream-summary.json").write_text(
                json.dumps(
                    {
                        "codebase_id": "sell-taro",
                        "upstream_type": "guazi-flow-wiki",
                        "discovery_mode": "auto-detected",
                        "adapter_status": "ok",
                        "source_map_entries": 3,
                        "warning_count": 1,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out_dir.joinpath("manifest.json").write_text("{}", encoding="utf-8")
            (project / "wiki" / "code" / "codebases" / "sell-taro").mkdir(parents=True)
            (project / "wiki" / "code" / "codebases" / "sell-taro" / "index.md").write_text("# sell-taro\n", encoding="utf-8")

            tool = Path(__file__).resolve().parents[1] / "health.py"
            process = subprocess.run(
                [sys.executable, str(tool), "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0)
            report = json.loads(process.stdout)
            self.assertEqual(report["code_intelligence"]["detected_codebases"], ["sell-taro"])
            self.assertEqual(report["code_intelligence"]["fallback_only_codebases"], [])
            self.assertEqual(report["code_intelligence"]["details"]["sell-taro"]["upstream_adapter_status"], "ok")
            self.assertEqual(report["code_intelligence"]["details"]["sell-taro"]["upstream_source_map_entries"], 3)
            self.assertEqual(report["code_intelligence"]["details"]["sell-taro"]["upstream_warning_count"], 1)


class TraceabilitySeedTests(unittest.TestCase):
    def test_build_code_seed_row_marks_upstream_as_derived_hint(self) -> None:
        row = build_code_seed_row(
            {
                "codebase_id": "sell-taro",
                "stack": ["node"],
                "upstream_type": "guazi-flow-wiki",
            }
        )
        self.assertIn("partial", row)
        self.assertIn("Derived upstream topic matched; direct code anchor still required.", row)

    def test_build_traceability_preserves_verified_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const App = 1;\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (project / "staging" / "code-graph").mkdir(parents=True)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "sell-taro", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            traceability = project / "wiki" / "code" / "traceability" / "index.md"
            traceability.parent.mkdir(parents=True)
            traceability.write_text(
                "# Traceability Matrix\n\n"
                "## Verified Traceability\n\n"
                "| Requirement Source | Requirement Point | Code Anchors | Evidence Strength | Notes |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| [[sources/source-index|Source]] | verified point | `raw-code/sell-taro/src/app.tsx` | strong | keep me |\n",
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            content = traceability.read_text(encoding="utf-8")
            self.assertIn("verified point", content)
            self.assertIn("keep me", content)

    def test_build_traceability_preserves_legacy_manual_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const App = 1;\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (project / "staging" / "code-graph").mkdir(parents=True)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "sell-taro", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            traceability = project / "wiki" / "code" / "traceability" / "index.md"
            traceability.parent.mkdir(parents=True)
            traceability.write_text(
                "# Traceability Matrix\n\n"
                "## Requirement Seeds\n\n"
                "| [[sources/source-index|Source]] | legacy manual point | service anchor | strong | keep legacy |\n",
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            content = traceability.read_text(encoding="utf-8")
            self.assertIn("## Previous Traceability Content", content)
            self.assertIn("legacy manual point", content)
            self.assertIn("keep legacy", content)

    def test_build_traceability_lists_code_anchor_candidates_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            codebase = project / "raw-code" / "sell-taro"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.tsx").write_text("export const url = '/api/cars';\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            scan_code.scan_codebase(project, codebase)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "sell-taro", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            content = (project / "wiki" / "code" / "traceability" / "index.md").read_text(encoding="utf-8")
            self.assertIn("## Code Anchor Candidates", content)
            self.assertIn("`raw-code/sell-taro/src/app.tsx`", content)
            self.assertIn("`/api/cars`", content)
            self.assertIn("candidate", content)
            self.assertNotIn("Codex must", content)

    def test_build_traceability_merges_worker_proposals_into_single_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            codebase = project / "raw-code" / "sell-taro"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.tsx").write_text("export const url = '/api/cars';\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            scan_code.scan_codebase(project, codebase)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "sell-taro", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            run_dir = project / "staging" / "traceability" / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            run_dir.joinpath("proposals.json").write_text(
                json.dumps(
                    {
                        "links": [
                            {
                                "id": "tr_api_cars",
                                "requirement": "车辆列表查询",
                                "source": "wiki/sources/source-index.md",
                                "code": ["raw-code/sell-taro/src/app.tsx#/api/cars"],
                                "strength": "partial",
                                "status": "proposed",
                                "note": "需求与接口路径相关，但缺少服务端实现锚点。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            state = json.loads((project / "staging" / "traceability" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["links"][0]["id"], "tr_api_cars")
            self.assertEqual(state["links"][0]["status"], "proposed")
            content = (project / "wiki" / "code" / "traceability" / "index.md").read_text(encoding="utf-8")
            self.assertIn("## Proposed Traceability", content)
            self.assertIn("车辆列表查询", content)
            self.assertIn("部分证据", content)

    def test_build_traceability_preserves_confirmed_and_rejected_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const App = 1;\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (project / "staging" / "code-graph").mkdir(parents=True)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "sell-taro", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            state_dir = project / "staging" / "traceability"
            state_dir.mkdir(parents=True)
            state_dir.joinpath("state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "links": [
                            {"id": "tr_keep", "requirement": "保留确认", "source": "wiki/sources/source-index.md", "code": [], "strength": "strong", "status": "confirmed"},
                            {"id": "tr_reject", "requirement": "保留拒绝", "source": "wiki/sources/source-index.md", "code": [], "strength": "inferred", "status": "rejected"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_dir = state_dir / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            run_dir.joinpath("proposals.json").write_text(
                json.dumps(
                    {
                        "links": [
                            {"id": "tr_keep", "requirement": "新文案", "source": "wiki/sources/source-index.md", "code": ["raw-code/sell-taro/src/app.tsx#App"], "strength": "partial", "status": "proposed"},
                            {"id": "tr_reject", "requirement": "新拒绝文案", "source": "wiki/sources/source-index.md", "code": ["raw-code/sell-taro/src/app.tsx#App"], "strength": "partial", "status": "proposed"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            state = json.loads(state_dir.joinpath("state.json").read_text(encoding="utf-8"))
            by_id = {link["id"]: link for link in state["links"]}
            self.assertEqual(by_id["tr_keep"]["status"], "confirmed")
            self.assertEqual(by_id["tr_keep"]["requirement"], "新文案")
            self.assertEqual(by_id["tr_reject"]["status"], "rejected")
            content = (project / "wiki" / "code" / "traceability" / "index.md").read_text(encoding="utf-8")
            self.assertIn("## Verified Traceability", content)
            self.assertIn("新拒绝文案", content)
            proposed_section = content.split("## Proposed Traceability", 1)[1].split("## Traceability Gaps", 1)[0]
            self.assertNotIn("新拒绝文案", proposed_section)

    def test_build_traceability_extracts_endpoint_units_from_refined_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "carsource" / "src").mkdir(parents=True)
            (project / "raw-code" / "carsource" / "src" / "ReportController.java").write_text(
                "class ReportController { void reportResultAnalysisByKey() {} }\n",
                encoding="utf-8",
            )
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "report-analysis", "title": "报告分析接口"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            source_page = project / "wiki" / "sources" / "report-analysis.md"
            source_page.parent.mkdir(parents=True)
            source_page.write_text(
                "# 报告分析接口\n\n"
                "## 关键事实\n\n"
                "- 内部接口：`GET /cars-report/internal/reportResultAnalysisByKey`，调用前需要验签。\n"
                "- 必传参数：`clue_id`（车源号）、`key`（字段 key）；可选：`task_id`、`snapshot_id`。\n"
                "- `report_version` 取值：`check` / `recheck` / `latest` / `snapshot`。\n"
                "- 关键 key：`major_accident`、`base_info`、`report_conclusion`。\n",
                encoding="utf-8",
            )
            (project / "staging" / "code-graph").mkdir(parents=True)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "carsource", "stack": ["java"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            units_path = project / "staging" / "traceability" / "units.json"
            units = json.loads(units_path.read_text(encoding="utf-8"))["units"]
            endpoint_units = [unit for unit in units if unit["kind"] == "endpoint"]
            self.assertTrue(endpoint_units)
            unit = endpoint_units[0]
            self.assertEqual(unit["source"], "wiki/sources/report-analysis.md")
            self.assertEqual(unit["capability"], "报告分析查询")
            self.assertEqual(unit["endpoint"], "GET /cars-report/internal/reportResultAnalysisByKey")
            self.assertIn("clue_id", unit["params"])
            self.assertIn("major_accident", unit["fields"])
            content = (project / "wiki" / "code" / "traceability" / "index.md").read_text(encoding="utf-8")
            self.assertIn("## Traceability Units", content)
            self.assertIn("GET /cars-report/internal/reportResultAnalysisByKey", content)
            self.assertIn("报告分析查询", content)

    def test_build_traceability_diagnoses_legacy_low_granularity_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "demo" / "src").mkdir(parents=True)
            (project / "raw-code" / "demo" / "src" / "service.ts").write_text("export const service = 1;\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "Source"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (project / "staging" / "code-graph").mkdir(parents=True)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "demo", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            state_dir = project / "staging" / "traceability"
            state_dir.mkdir(parents=True)
            state_dir.joinpath("state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "links": [
                            {
                                "id": "tr_page_to_file",
                                "requirement": "Source",
                                "source": "wiki/sources/source-index.md",
                                "code": ["raw-code/demo/src/service.ts"],
                                "strength": "partial",
                                "status": "proposed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            state = json.loads(state_dir.joinpath("state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["links"][0]["id"], "tr_page_to_file")
            content = (project / "wiki" / "code" / "traceability" / "index.md").read_text(encoding="utf-8")
            self.assertIn("## Traceability Diagnostics", content)
            self.assertIn("low_granularity_links", content)
            self.assertIn("tr_page_to_file", content)


if __name__ == "__main__":
    unittest.main()
