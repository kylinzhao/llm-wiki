import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RefinementPlanTest(unittest.TestCase):
    def test_build_wiki_writes_refinement_plan_for_pending_source_page(self):
        build_wiki = load_tool("build_wiki")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# Product Rules\n\nA source fact.\n", encoding="utf-8")

            build_wiki.main_for_project(project)

            plan = json.loads((project / "staging" / "refinement-plan.json").read_text(encoding="utf-8"))
            self.assertTrue(plan["semantic_update_required"])
            self.assertEqual(plan["trigger"], "raw_changed")
            self.assertEqual(plan["required_source_pages"][0]["raw_path"], "raw/product/index.md")
            self.assertEqual(plan["required_source_pages"][0]["reason"], "new_raw_page")
            self.assertIn("wiki/sources/product-index.md", plan["allowed_write_paths"])
            self.assertIn("raw/**", plan["forbidden_write_paths"])
            self.assertIn("tools/check_refinement.py", plan["verification"])

    def test_check_refinement_fails_pending_source_and_passes_completed_record(self):
        build_wiki = load_tool("build_wiki")
        check_refinement = load_tool("check_refinement")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_page = project / "raw" / "product" / "index.md"
            raw_page.parent.mkdir(parents=True)
            raw_page.write_text("# Product Rules\n\nA source fact.\n", encoding="utf-8")

            build_wiki.main_for_project(project)

            self.assertEqual(check_refinement.check_project(project), 1)
            source_page = project / "wiki" / "sources" / "product-index.md"
            source_page.write_text(
                source_page.read_text(encoding="utf-8")
                .replace("Pending AI-native summary.", "The product rule is grounded in raw/product/index.md.")
                .replace("Pending extraction from source evidence.", "Product fact: A source fact.")
                .replace("Deterministic seed page.", "AI refined page."),
                encoding="utf-8",
            )
            (project / "staging" / "refinement-status.md").write_text(
                "# Refinement Status\n\n```json\n"
                + json.dumps(
                    {
                        "completed": [
                            {
                                "path": "wiki/sources/product-index.md",
                                "raw_path": "raw/product/index.md",
                                "status": "completed",
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n```\n",
                encoding="utf-8",
            )

            self.assertEqual(check_refinement.check_project(project), 0)


if __name__ == "__main__":
    unittest.main()
