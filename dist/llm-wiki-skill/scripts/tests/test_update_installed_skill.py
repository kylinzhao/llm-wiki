import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "update_installed_skill.py"


def load_updater():
    spec = importlib.util.spec_from_file_location("update_installed_skill", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UpdateInstalledSkillTest(unittest.TestCase):
    def test_successful_update_suggests_maintain_all(self):
        updater = load_updater()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            stdout = io.StringIO()
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--source", str(bundle), "--no-pull"]
                with mock.patch.object(updater, "resolve_bundle_root", return_value=bundle), mock.patch.object(
                    updater, "run", return_value=0
                ), mock.patch.object(
                    updater, "update_prd_review_max", return_value=0
                ) as prd_update, contextlib.redirect_stdout(stdout):
                    self.assertEqual(updater.main(), 0)
            finally:
                sys.argv = original_argv

        output = stdout.getvalue()
        self.assertIn("maintain-all", output)
        self.assertIn("Existing KB projects keep their project-local tools", output)
        self.assertIn("prd-review-max was refreshed", output)
        prd_update.assert_called_once()

    def test_skip_prd_review_max(self):
        updater = load_updater()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            original_argv = sys.argv
            try:
                sys.argv = [str(SCRIPT), "--source", str(bundle), "--no-pull", "--skip-prd-review-max"]
                with mock.patch.object(updater, "resolve_bundle_root", return_value=bundle), mock.patch.object(
                    updater, "run", return_value=0
                ), mock.patch.object(
                    updater, "update_prd_review_max", return_value=0
                ) as prd_update:
                    self.assertEqual(updater.main(), 0)
            finally:
                sys.argv = original_argv

        prd_update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
