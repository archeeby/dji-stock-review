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


    def test_ollama_result_requires_real_success(self):
        output = ("test_real_frame_vision_and_stock_metadata (tests.test_ollama_e2e.RealOllamaE2E.test_real_frame_vision_and_stock_metadata) ... ok\\n"
                  "----------------------------------------------------------------------\\nRan 1 test in 8.12s\\n\\nOK\\n")
        accept.verify_ollama_result(output, 0)

    def test_skipped_ollama_is_rejected_even_with_exit_zero(self):
        output = ("setUpClass (tests.test_ollama_e2e.RealOllamaE2E) ... skipped 'opt-in'\\n"
                  "----------------------------------------------------------------------\\nRan 0 tests in 0.000s\\n\\nOK (skipped=1)\\n")
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result(output, 0)

    def test_empty_ollama_is_rejected(self):
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result("Ran 0 tests in 0.00s\\nOK", 0)

    def test_failed_ollama_is_rejected(self):
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result("test_real_frame_vision_and_stock_metadata ... ok\\nRan 1 test in 1.0s\\nOK", 1)

    def test_missing_ollama_models_are_rejected(self):
        from tests.test_ollama_e2e import RealOllamaE2E
        import io
        import json
        with patch.dict("os.environ", {"DJI_RUN_OLLAMA_E2E": "1"}):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps({"models": []}).encode())
                with self.assertRaisesRegex(RuntimeError, "Required Ollama models missing"):
                    RealOllamaE2E.setUpClass()

    def test_preview_script_enforces_expected_sha(self):
        script = (MODULE.parent / "preview.sh").read_text()
        self.assertIn('DJI_EXPECTED_PR_SHA', script)
        self.assertIn('Refusing preview', script)

    def test_accept_passes_expected_sha_to_preview(self):
        script = MODULE.read_text()
        self.assertIn('preview_env["DJI_EXPECTED_PR_SHA"] = sha', script)

    def test_profile_override_cannot_downgrade(self):
        # The runner must reject weaker profiles rather than silently skipping tests.
        script = MODULE.read_text()
        self.assertIn('order[override] < order[profile]', script)


if __name__ == "__main__":
    unittest.main()
