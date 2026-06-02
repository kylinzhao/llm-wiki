import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str):
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_page(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class GPlusQualityTest(unittest.TestCase):
    def test_large_kb_with_two_concepts_is_reported_as_p1_underfit(self):
        gplus_quality = load_module("gplus_quality")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "concepts" / "index.md", "# Concepts\n")
            write_page(project / "wiki" / "concepts" / "c1-seller-journey.md", "# C1 seller journey\n")
            write_page(project / "wiki" / "concepts" / "c1-data-analytics.md", "# C1 analytics\n")
            write_page(project / "wiki" / "entities" / "index.md", "# Entities\n")
            write_page(project / "wiki" / "entities" / "c1.md", "# C1\n")
            for layer in ["truth", "conflicts", "evidence", "proposals", "operations", "reference"]:
                write_page(project / "wiki" / layer / "index.md", f"# {layer}\n")
            for index in range(682):
                link = "[[concepts/c1-seller-journey|C1]]" if index < 329 else ""
                placeholder = "\n- （请人工补链到 concepts / entities）" if index < 23 else ""
                write_page(project / "wiki" / "sources" / f"source-{index}.md", f"# Source {index}\n{link}{placeholder}\n")
            health = {"source_pages": 682}

            report = gplus_quality.inspect_gplus_quality(project, health)

            titles = {item["title"]: item for item in report["findings"]}
            self.assertEqual(titles["gplus_concepts_underfit"]["severity"], "P1")
            self.assertEqual(titles["gplus_manual_link_placeholders"]["severity"], "P1")
            self.assertEqual(report["metrics"]["non_index_concept_pages"], 2)

    def test_dense_concepts_do_not_create_underfit_finding(self):
        gplus_quality = load_module("gplus_quality")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "concepts" / "index.md", "# Concepts\n")
            for index in range(24):
                write_page(project / "wiki" / "concepts" / f"concept-{index}.md", f"# Concept {index}\n")
            for index in range(105):
                write_page(project / "wiki" / "sources" / f"source-{index}.md", "# Source\n[[concepts/concept-1|Concept]]\n")
            health = {"source_pages": 105}

            report = gplus_quality.inspect_gplus_quality(project, health)

            self.assertNotIn("gplus_concepts_underfit", {item["title"] for item in report["findings"]})

    def test_doctor_includes_gplus_findings(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "concepts" / "index.md", "# Concepts\n")
            write_page(project / "wiki" / "concepts" / "only.md", "# Only\n")
            for index in range(120):
                write_page(project / "wiki" / "sources" / f"source-{index}.md", "# Source\n")
            doctor.run_health = lambda _: {"ok": True, "status": "pass", "source_pages": 120, "wiki_pages": 122}

            report = doctor.build_report(project)

            self.assertIn("gplus_concepts_underfit", {item["title"] for item in report["findings"]})
            self.assertEqual(report["gplus_quality"]["metrics"]["non_index_concept_pages"], 1)
            self.assertEqual(report["project"], ".")

    def test_doctor_latest_is_stable_when_only_path_and_time_would_change(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            out = project / "staging" / "doctor" / "latest.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            existing = {
                "schemaVersion": "doctor.v1",
                "generated_at": "2026-05-01T00:00:00+00:00",
                "project": "/tmp/old-checkout",
                "summary": "No blocking LLM Wiki issues found.",
                "findings": [],
                "maxSeverity": None,
                "p0Count": 0,
                "health": {"ok": True, "status": "pass", "wiki_pages": 2, "source_pages": 1, "raw_drawio_assets": 0, "drawio_repair": {}},
                "gplus_quality": {"status": "ok", "metrics": {}, "findings": []},
                "agent_rules": {"path": "/tmp/old-checkout/AGENTS.md", "exists": True, "has_query_routing": True, "ok": True},
            }
            out.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report = {
                **existing,
                "generated_at": "2026-06-01T00:00:00+00:00",
                "project": str(project),
                "agent_rules": {"path": str(project / "AGENTS.md"), "exists": True, "has_query_routing": True, "ok": True},
            }
            before = out.read_text(encoding="utf-8")

            doctor.write_stable_report(out, report)

            self.assertEqual(out.read_text(encoding="utf-8"), before)

    def test_doctor_reports_pending_source_refinement_as_p1(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "sources" / "source-1.md", "# Source\n\nDeterministic seed page.\n\nraw/source/index.md\n")
            write_page(
                project / "staging" / "refinement-plan.json",
                json.dumps(
                    {
                        "semantic_update_required": True,
                        "required_source_pages": [
                            {
                                "raw_path": "raw/source/index.md",
                                "wiki_path": "wiki/sources/source-1.md",
                                "required": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
            doctor.run_health = lambda _: {"ok": True, "status": "pass", "source_pages": 1, "wiki_pages": 1}

            report = doctor.build_report(project)

            findings = {item["title"]: item for item in report["findings"]}
            self.assertEqual(findings["source_refinement_pending"]["severity"], "P1")
            self.assertEqual(report["refinement_contract"]["pending_count"], 1)

    def test_doctor_promotes_important_p2_when_no_p1_exists(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "concepts" / "index.md", "# Concepts\n")
            write_page(project / "wiki" / "concepts" / "concept-1.md", "# Concept 1\n")
            write_page(project / "wiki" / "entities" / "index.md", "# Entities\n")
            write_page(project / "wiki" / "entities" / "entity-1.md", "# Entity 1\n")
            write_page(project / "AGENTS.md", "# Rules\n\n## Query Routing\n")
            for index in range(10):
                write_page(
                    project / "wiki" / "sources" / f"source-{index}.md",
                    "# Source\n[[concepts/concept-1|Concept]]\n[[entities/entity-1|Entity]]\n",
                )
            doctor.run_health = lambda _: {
                "ok": True,
                "status": "pass",
                "source_pages": 10,
                "wiki_pages": 12,
                "raw_image_assets": 5,
                "image_notes": 1,
                "image_evidence_status": "unknown",
                "cjira_registry": {"stale_status_pages": 2, "low_confidence_pages": 1},
                "orphan_source_pages": ["wiki/sources/orphan.md"],
            }

            report = doctor.build_report(project)

            findings = {item["title"]: item for item in report["findings"]}
            self.assertEqual(findings["image_evidence_status_unknown"]["severity"], "P1")
            self.assertEqual(findings["image_evidence_status_unknown"]["promoted_from"], "P2")
            self.assertEqual(findings["cjira_status_quality_gaps"]["severity"], "P1")
            self.assertEqual(findings["orphan_source_pages"]["severity"], "P1")

    def test_doctor_keeps_important_p2_when_p1_exists(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "sources" / "source-1.md", "# Source\n\nDeterministic seed page.\n\nraw/source/index.md\n")
            write_page(
                project / "staging" / "refinement-plan.json",
                json.dumps(
                    {
                        "semantic_update_required": True,
                        "required_source_pages": [
                            {
                                "raw_path": "raw/source/index.md",
                                "wiki_path": "wiki/sources/source-1.md",
                                "required": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
            doctor.run_health = lambda _: {
                "ok": True,
                "status": "pass",
                "source_pages": 1,
                "wiki_pages": 1,
                "raw_image_assets": 5,
                "image_notes": 1,
                "image_evidence_status": "unknown",
            }

            report = doctor.build_report(project)

            findings = {item["title"]: item for item in report["findings"]}
            self.assertEqual(findings["source_refinement_pending"]["severity"], "P1")
            self.assertEqual(findings["image_evidence_status_unknown"]["severity"], "P2")
            self.assertNotIn("promoted_from", findings["image_evidence_status_unknown"])

    def test_doctor_promotes_gplus_p2_when_no_p1_exists(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "AGENTS.md", "# Rules\n\n## Query Routing\n")
            for index in range(5):
                write_page(project / "wiki" / "concepts" / f"concept-{index}.md", f"# Concept {index}\n")
            write_page(project / "wiki" / "entities" / "entity-1.md", "# Entity\n")
            for index in range(100):
                body = "# Source\n"
                if index < 40:
                    body += "[[concepts/concept-1|Concept]]\n"
                write_page(project / "wiki" / "sources" / f"source-{index}.md", body)
            doctor.run_health = lambda _: {
                "ok": True,
                "status": "pass",
                "source_pages": 100,
                "wiki_pages": 106,
            }

            report = doctor.build_report(project)

            findings = {item["title"]: item for item in report["findings"]}
            self.assertEqual(findings["gplus_concept_coverage_low"]["severity"], "P1")
            self.assertEqual(findings["gplus_concept_coverage_low"]["promoted_from"], "P2")

    def test_doctor_cjira_gap_message_skips_auth_prompt_when_local_auth_exists(self):
        doctor = load_module("doctor")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "AGENTS.md", "# Rules\n\n## Query Routing\n")
            doctor.run_health = lambda _: {
                "ok": True,
                "status": "pass",
                "source_pages": 10,
                "wiki_pages": 12,
                "cjira_registry": {"stale_status_pages": 2, "low_confidence_pages": 1},
            }
            doctor.local_jira_auth_configured = lambda: True

            report = doctor.build_report(project)

            findings = {item["title"]: item for item in report["findings"]}
            self.assertNotIn("Refresh Jira auth/status", findings["cjira_status_quality_gaps"]["detail"])
            self.assertIn("Run `llm-wiki-new update`", findings["cjira_status_quality_gaps"]["detail"])

    def test_update_success_report_records_gplus_quality(self):
        update_wiki = load_module("update_wiki")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "concepts" / "index.md", "# Concepts\n")
            write_page(project / "wiki" / "concepts" / "only.md", "# Only\n")
            for index in range(120):
                write_page(project / "wiki" / "sources" / f"source-{index}.md", "# Source\n")
            write_page(
                project / "staging" / "health" / "latest.json",
                json.dumps({"ok": True, "status": "pass", "source_pages": 120}, ensure_ascii=False),
            )

            update_wiki.write_success_report(project)

            latest = json.loads((project / "staging" / "update" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["gplus_quality"]["status"], "needs_attention")
            self.assertIn("gplus_concepts_underfit", (project / "staging" / "update" / "latest.md").read_text(encoding="utf-8"))

    def test_update_success_report_records_refinement_contract(self):
        update_wiki = load_module("update_wiki")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_page(project / "wiki" / "sources" / "source-1.md", "# Source\n\nDeterministic seed page.\n\nraw/source/index.md\n")
            write_page(
                project / "staging" / "health" / "latest.json",
                json.dumps({"ok": True, "status": "pass", "source_pages": 1}, ensure_ascii=False),
            )
            write_page(
                project / "staging" / "refinement-plan.json",
                json.dumps(
                    {
                        "semantic_update_required": True,
                        "required_source_pages": [
                            {
                                "raw_path": "raw/source/index.md",
                                "wiki_path": "wiki/sources/source-1.md",
                                "required": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )

            update_wiki.write_success_report(project)

            latest = json.loads((project / "staging" / "update" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["refinement_contract"]["status"], "needs_refinement")
            self.assertEqual(latest["refinement_contract"]["pending_count"], 1)
            self.assertIn("P1 automatic update task", (project / "staging" / "update" / "latest.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
