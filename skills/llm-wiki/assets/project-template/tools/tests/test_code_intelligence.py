from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scan_code
from build_traceability import build_code_seed_row
from code_intelligence import (
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
                        "topics": [{"slug": "project-overview"}],
                        "concepts": [{"slug": "unified-runtime-infrastructure"}],
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
            (docs_wiki / "index.json").write_text(json.dumps({"topics": [{"slug": "project-overview"}]}, ensure_ascii=False), encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "package.json").write_text('{"name":"sell-taro"}', encoding="utf-8")
            (project / "raw-code" / "sell-taro" / "src").mkdir(parents=True)
            (project / "raw-code" / "sell-taro" / "src" / "app.tsx").write_text("export const route = '/app';\n", encoding="utf-8")

            result = scan_code.scan_codebase(project, project / "raw-code" / "sell-taro")
            self.assertEqual(result["upstream_type"], "guazi-flow-wiki")

            upstream_summary = project / "staging" / "code-graph" / "sell-taro" / "upstream-summary.json"
            self.assertTrue(upstream_summary.is_file())
            page = project / "wiki" / "code" / "codebases" / "sell-taro" / "index.md"
            content = page.read_text(encoding="utf-8")
            self.assertIn("## Upstream Code Intelligence", content)
            self.assertIn("`guazi-flow-wiki`", content)

    def test_health_reports_detected_upstream_code_intelligence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "raw").mkdir()
            (project / "wiki").mkdir(parents=True)
            (project / "wiki" / "index.md").write_text("# index\n", encoding="utf-8")
            (project / "wiki" / "overview.md").write_text("# overview\n", encoding="utf-8")
            (project / "docs").mkdir()
            (project / "docs" / "retrieval-playbook.md").write_text("# retrieval\n", encoding="utf-8")
            (project / "docs" / "build-and-maintenance.md").write_text("# build\n", encoding="utf-8")
            (project / "staging").mkdir()
            (project / "staging" / "refinement-status.md").write_text("{}", encoding="utf-8")
            (project / "raw-code" / "sell-taro").mkdir(parents=True)
            out_dir = project / "staging" / "code-graph" / "sell-taro"
            out_dir.mkdir(parents=True)
            out_dir.joinpath("upstream-summary.json").write_text(
                json.dumps({"codebase_id": "sell-taro", "upstream_type": "guazi-flow-wiki", "discovery_mode": "auto-detected"}, ensure_ascii=False),
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


if __name__ == "__main__":
    unittest.main()
