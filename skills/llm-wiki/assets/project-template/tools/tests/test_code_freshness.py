from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graphify_code
import scan_code
from code_freshness import compute_freshness


class CodeFreshnessTests(unittest.TestCase):
    def test_first_scan_records_all_files_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.ts").write_text("export const route = '/app';\n", encoding="utf-8")
            files = scan_code.iter_code_files(codebase)
            facts = [scan_code.extract_facts(path, codebase) for path in files]

            freshness = compute_freshness(project, "demo", codebase, files, facts)

            self.assertEqual(freshness["structural_change_level"], "high")
            self.assertEqual(freshness["changed_files"], ["src/app.ts"])
            self.assertEqual(freshness["new_files"], ["src/app.ts"])
            self.assertEqual(freshness["deleted_files"], [])
            self.assertEqual(freshness["unchanged_files"], [])
            self.assertEqual(freshness["file_count"], 1)

    def test_second_scan_without_changes_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            (codebase / "src" / "app.ts").write_text("export const route = '/app';\n", encoding="utf-8")

            first = scan_code.scan_codebase(project, codebase)
            self.assertEqual(first["codebase_id"], "demo")
            second = scan_code.scan_codebase(project, codebase)

            freshness_path = project / "staging" / "code-graph" / "demo" / "freshness.json"
            self.assertTrue(freshness_path.is_file())
            freshness = json.loads(freshness_path.read_text(encoding="utf-8"))
            self.assertEqual(second["structural_change_level"], "none")
            self.assertEqual(freshness["changed_files"], [])
            self.assertEqual(freshness["structural_change_level"], "none")

    def test_controller_or_service_change_is_medium_structural_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            controller = codebase / "src" / "CarController.java"
            controller.write_text('@GetMapping("/api/cars")\nclass CarController {}\n', encoding="utf-8")
            scan_code.scan_codebase(project, codebase)

            controller.write_text('@GetMapping("/api/cars/new")\nclass CarController {}\n', encoding="utf-8")
            result = scan_code.scan_codebase(project, codebase)

            self.assertEqual(result["structural_change_level"], "medium")
            freshness = json.loads((project / "staging" / "code-graph" / "demo" / "freshness.json").read_text(encoding="utf-8"))
            self.assertEqual(freshness["changed_files"], ["src/CarController.java"])

    def test_many_changed_files_are_high_structural_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            codebase = project / "raw-code" / "demo"
            (codebase / "src").mkdir(parents=True)
            for index in range(6):
                (codebase / "src" / f"module{index}.ts").write_text(f"export const v{index} = 1;\n", encoding="utf-8")
            scan_code.scan_codebase(project, codebase)

            for index in range(6):
                (codebase / "src" / f"module{index}.ts").write_text(f"export const v{index} = 2;\n", encoding="utf-8")
            result = scan_code.scan_codebase(project, codebase)

            self.assertEqual(result["structural_change_level"], "high")


class GraphifyDecisionTests(unittest.TestCase):
    def test_policy_skips_when_upstream_and_scan_evidence_are_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            out_dir = project / "staging" / "code-graph" / "demo"
            out_dir.mkdir(parents=True)
            out_dir.joinpath("upstream-summary.json").write_text(
                json.dumps({"upstream_type": "guazi-flow-wiki", "source_map_entries": 2}, ensure_ascii=False),
                encoding="utf-8",
            )
            out_dir.joinpath("endpoint-map.json").write_text(
                json.dumps([{"path": "raw-code/demo/src/app.ts", "endpoint": {"uri": "/api/cars"}}], ensure_ascii=False),
                encoding="utf-8",
            )
            out_dir.joinpath("freshness.json").write_text(
                json.dumps({"structural_change_level": "none"}, ensure_ascii=False),
                encoding="utf-8",
            )

            decision = graphify_code.decide_graphify_action(project, "demo", requested=False)

            self.assertEqual(decision["decision"], "skipped_upstream_sufficient")
            self.assertFalse(decision["should_run"])

    def test_policy_runs_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "staging" / "code-graph" / "demo").mkdir(parents=True)

            decision = graphify_code.decide_graphify_action(project, "demo", requested=True)

            self.assertEqual(decision["decision"], "run_requested")
            self.assertTrue(decision["should_run"])

    def test_policy_recommends_graphify_for_high_structural_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            out_dir = project / "staging" / "code-graph" / "demo"
            out_dir.mkdir(parents=True)
            out_dir.joinpath("freshness.json").write_text(
                json.dumps({"structural_change_level": "high"}, ensure_ascii=False),
                encoding="utf-8",
            )

            decision = graphify_code.decide_graphify_action(project, "demo", requested=False)

            self.assertEqual(decision["decision"], "recommended_structural_change")
            self.assertFalse(decision["should_run"])


if __name__ == "__main__":
    unittest.main()
