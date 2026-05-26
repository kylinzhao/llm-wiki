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
            self.assertEqual(plan["user_next_command"], "llm-wiki update")
            self.assertNotIn("uv run python", plan["user_next_action"])
            self.assertIn("AI-native", plan["user_next_action"])

            status_text = (project / "staging" / "refinement-status.md").read_text(encoding="utf-8")
            self.assertIn('"next_command": "llm-wiki update"', status_text)
            self.assertNotIn("Run AI-native source refinement next, then health and graph.", status_text)

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
                .replace("待完成 AI 原生摘要。", "The product rule is grounded in raw/product/index.md.")
                .replace("待从来源证据中提取。", "Product fact: A source fact.")
                .replace("确定性种子页。", "AI refined page."),
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
