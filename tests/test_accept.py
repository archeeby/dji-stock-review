"""Acceptance profile and fail-closed prerequisite contract tests."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "accept.py"
spec = importlib.util.spec_from_file_location("local_acceptance", MODULE)
accept = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accept)


class AcceptanceProfileTests(unittest.TestCase):
    def test_real_ollama_test_is_opt_in(self):
        self.assertEqual(accept.classify(["tests/test_ollama_e2e.py"]), "ai")

    def test_docs_only_is_not_a_local_test_requirement(self):
        self.assertEqual(accept.classify(["docs/testing.md", "README.md"]), "docs")

    def test_ui_only_requires_unit_tests(self):
        self.assertEqual(accept.classify(["review_app.py", "tests/test_candidate_reviews.py"]), "unit")

    def test_real_media_change_requires_media_tests(self):
        self.assertEqual(accept.classify(["export_approved.py"]), "media")

    def test_ai_change_requires_heavy_e2e(self):
        self.assertEqual(accept.classify(["generate_stock_metadata_batch.py"]), "ai")

    def test_mixed_changes_choose_strictest_profile(self):
        self.assertEqual(accept.classify(["review_app.py", "run_pipeline.py"]), "ai")

    def test_unknown_code_defaults_to_media(self):
        self.assertEqual(accept.classify(["unknown_new_module.py"]), "media")

    def test_no_diff_fails_closed(self):
        with self.assertRaises(ValueError):
            accept.classify([])

    def test_unit_profile_also_requires_real_media_tools(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "tests").mkdir()
            (folder / "tests/test_real_dji_tools.py").touch()
            (folder / "tests/test_real_dji_motion.py").touch()
            with patch.object(accept.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Missing required tools"):
                    accept.prerequisites("unit", folder)

    def test_missing_media_tests_fail_closed(self):
        with patch.object(accept.shutil, "which", return_value="/usr/bin/tool"):
            with self.assertRaisesRegex(RuntimeError, "integration test is not present"):
                accept.prerequisites("media", Path("/does-not-exist"))

    def test_missing_ai_e2e_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "tests").mkdir()
            (folder / "tests/test_real_dji_tools.py").touch()
            (folder / "tests/test_real_dji_motion.py").touch()
            with patch.object(accept.shutil, "which", return_value="/usr/bin/tool"):
                with self.assertRaisesRegex(RuntimeError, "Ollama E2E test is not implemented"):
                    accept.prerequisites("ai", folder)


if __name__ == "__main__":
    unittest.main()
