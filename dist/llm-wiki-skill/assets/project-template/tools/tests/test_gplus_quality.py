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


if __name__ == "__main__":
    unittest.main()
