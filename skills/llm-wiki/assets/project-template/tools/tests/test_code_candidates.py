from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graphify_code
import scan_code
import build_traceability
from code_candidates import build_code_candidates


class CodeCandidateTests(unittest.TestCase):
    def test_builds_anchor_candidates_from_scan_and_upstream_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.ts").write_text("export const url = '/api/cars';\n", encoding="utf-8")
            scan_code.scan_codebase(project, codebase)
            out_dir = project / "staging" / "code-graph" / "demo"
            out_dir.joinpath("upstream-source-map.json").write_text(
                json.dumps({"entries": [{"path": "src/app.ts", "topic": "car-list"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = build_code_candidates(project, "demo")

            self.assertEqual(result["anchor_candidate_count"], 1)
            anchors = json.loads(out_dir.joinpath("anchor-candidates.json").read_text(encoding="utf-8"))
            candidate = anchors["candidates"][0]
            self.assertEqual(candidate["code_anchor"], "raw-code/demo/src/app.ts")
            self.assertEqual(candidate["evidence_strength"], "partial")
            self.assertIn("scan_endpoint", candidate["signals"])
            self.assertIn("upstream_source_map", candidate["signals"])
            self.assertTrue(candidate["requires_verification"])

    def test_builds_capability_candidates_from_upstream_topics_and_scan_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "car-service.ts").write_text("function listCars() { return '/api/cars'; }\n", encoding="utf-8")
            scan_code.scan_codebase(project, codebase)
            out_dir = project / "staging" / "code-graph" / "demo"
            out_dir.joinpath("upstream-topics.json").write_text(
                json.dumps({"topics": [{"id": "car-list", "title": "车辆列表", "keywords": ["cars"], "related_files": ["src/car-service.ts"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            build_code_candidates(project, "demo")

            capabilities = json.loads(out_dir.joinpath("capability-candidates.json").read_text(encoding="utf-8"))
            candidate = capabilities["candidates"][0]
            self.assertEqual(candidate["slug"], "car-list")
            self.assertEqual(candidate["title"], "车辆列表")
            self.assertIn("upstream_topic", candidate["signals"])
            self.assertIn("scan_symbol", candidate["signals"])
            self.assertEqual(candidate["evidence_strength"], "partial")

    def test_graphify_graph_json_is_summarized_as_structure_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            out_dir = project / "staging" / "code-graph" / "demo" / "graphify-out"
            out_dir.mkdir(parents=True)
            out_dir.joinpath("graph.json").write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"id": "src/app.ts", "label": "App"},
                            {"id": "src/service.ts", "label": "Service"},
                        ],
                        "edges": [
                            {"source": "src/app.ts", "target": "src/service.ts", "type": "calls"},
                            {"source": "node_modules/react", "target": "src/app.ts", "type": "import"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = graphify_code.summarize_graphify_output(project, "demo")

            self.assertEqual(summary["node_count"], 2)
            self.assertEqual(summary["edge_count"], 1)
            structure = json.loads((project / "staging" / "code-graph" / "demo" / "structure-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(structure["edges"][0]["source"], "src/app.ts")
            self.assertEqual(structure["edges"][0]["signal"], "graph_neighbor")

    def test_anchor_candidates_feed_deterministic_traceability_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# 车辆列表\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "source-manifest.json").write_text(
                json.dumps({"sources": [{"slug": "source-index", "title": "车辆列表需求"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.ts").write_text("export const url = '/api/cars';\n", encoding="utf-8")
            scan_code.scan_codebase(project, codebase)
            (project / "staging" / "code-graph" / "summary.json").write_text(
                json.dumps({"codebases": [{"codebase_id": "demo", "stack": ["node"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            state = json.loads((project / "staging" / "traceability" / "state.json").read_text(encoding="utf-8"))
            proposed = [link for link in state["links"] if link["status"] == "proposed"]
            self.assertTrue(proposed)
            self.assertEqual(proposed[0]["strength"], "partial")
            self.assertIn("raw-code/demo/src/app.ts", proposed[0]["code"])
            self.assertNotEqual(proposed[0]["strength"], "strong")

    def test_anchor_candidates_include_role_and_low_value_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / ".agents" / "skills").mkdir(parents=True)
            (codebase / ".agents" / "skills" / "helper.py").write_text("def helper(): pass\n", encoding="utf-8")
            (codebase / "src" / "api").mkdir(parents=True)
            (codebase / "src" / "api" / "ReportController.java").write_text(
                "class ReportController { void reportResultAnalysisByKey() {} }\n",
                encoding="utf-8",
            )
            scan_code.scan_codebase(project, codebase)

            build_code_candidates(project, "demo")

            anchors = json.loads((project / "staging" / "code-graph" / "demo" / "anchor-candidates.json").read_text(encoding="utf-8"))
            by_anchor = {item["code_anchor"]: item for item in anchors["candidates"]}
            controller = by_anchor["raw-code/demo/src/api/ReportController.java"]
            self.assertEqual(controller["code_role"], "controller")
            self.assertIn("scan_symbol", controller["match_reason"])
            helper = by_anchor["raw-code/demo/.agents/skills/helper.py"]
            self.assertEqual(helper["code_role"], "tooling")
            self.assertIn("low_value_path", helper["diagnostics"])

    def test_missing_code_anchor_marks_confirmed_traceability_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw" / "source").mkdir(parents=True)
            (project / "raw" / "source" / "index.md").write_text("# source\n", encoding="utf-8")
            (project / "raw-code" / "demo" / "src").mkdir(parents=True)
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
                                "id": "tr_missing_anchor",
                                "requirement": "missing anchor",
                                "source": "wiki/sources/source-index.md",
                                "code": ["raw-code/demo/src/missing.ts#handler"],
                                "strength": "strong",
                                "status": "confirmed",
                                "note": "was valid before",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            build_traceability.build_traceability(project)

            state = json.loads(state_dir.joinpath("state.json").read_text(encoding="utf-8"))
            link = state["links"][0]
            self.assertEqual(link["status"], "stale")
            self.assertEqual(link["strength"], "partial")
            self.assertIn("missing code anchor", link["note"])


if __name__ == "__main__":
    unittest.main()
