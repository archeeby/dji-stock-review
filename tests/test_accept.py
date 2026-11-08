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

    def test_relocation_and_acceptance_changes_require_real_ai(self):
        for path in ("workspace_paths.py", "scripts/accept.py", "scripts/accept.sh",
                     "scripts/preview.sh", "scripts/start-review.sh", "scripts/structured_tests.py"):
            with self.subTest(path=path):
                self.assertEqual(accept.classify([path]), "ai")

    def test_ai_environment_overrides_live_workspace_without_changing_parent(self):
        import os
        with patch.dict(os.environ, DJI_STOCK_ROOT="/live/DroneStock",
                        DJI_RUN_OLLAMA_E2E="1"):
            for ai in (False, True):
                env = accept.test_environment("/tmp/relocated fixture", ai=ai)
                self.assertEqual(env["DJI_STOCK_ROOT"], "/tmp/relocated fixture")
                self.assertEqual(env["HOME"], "/tmp/relocated fixture")
                self.assertEqual(env["TMPDIR"], "/tmp/relocated fixture")
                self.assertEqual(env.get("DJI_RUN_OLLAMA_E2E"), "1" if ai else None)
            self.assertEqual(os.environ["DJI_STOCK_ROOT"], "/live/DroneStock")

    def test_preview_carries_workspace_across_detached_checkout(self):
        import os
        with patch.dict(os.environ):
            os.environ.pop("DJI_STOCK_ROOT", None)
            env = accept.preview_environment(Path("/relocated workspace/DroneStock/checkout"), "sha")
            self.assertEqual(env["DJI_STOCK_ROOT"], "/relocated workspace/DroneStock")
            self.assertEqual(env["DJI_STOCK_REPO"], "/relocated workspace/DroneStock/checkout")
            self.assertEqual(env["DJI_EXPECTED_PR_SHA"], "sha")
        with patch.dict(os.environ, DJI_STOCK_ROOT="/separate data"):
            self.assertEqual(accept.preview_environment(Path("/checkout"), "sha")["DJI_STOCK_ROOT"], "/separate data")

    def test_python_lookup_uses_workspace_checkout_then_separate_data(self):
        import tempfile
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "workspace" / "checkout"
            data = Path(tmp) / "separate data"
            candidates = [base / ".venv312/bin/python" for base in (repo.parent, repo, data)]
            for path in candidates:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            with patch.dict("os.environ", DJI_STOCK_ROOT=str(data)):
                for selected in range(3):
                    # Stub only interpreter validation; assert actual lookup/fallback order.
                    results = [SimpleNamespace(returncode=1)] * selected + [SimpleNamespace(returncode=0)]
                    with patch.object(accept.subprocess, "run", side_effect=results) as run:
                        self.assertEqual(accept.find_python(repo), candidates[selected])
                        self.assertEqual([Path(c.args[0][0]) for c in run.call_args_list], candidates[:selected + 1])

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
        data = {"successful": True, "total": 1, "failed": 0, "skipped": 0,
                "tests": [{"id": "tests.test_ollama_e2e.RealOllamaE2E.test_real_frame_vision_and_stock_metadata",
                           "status": "passed"}]}
        accept.verify_ollama_result(data, 0)

    def test_skipped_ollama_is_rejected_even_with_exit_zero(self):
        data = {"successful": True, "total": 0, "failed": 0, "skipped": 1, "tests": []}
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result(data, 0)

    def test_empty_ollama_is_rejected(self):
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result({"successful": True, "total": 0,
                                         "failed": 0, "skipped": 0, "tests": []}, 0)

    def test_failed_ollama_is_rejected(self):
        data = {"successful": False, "total": 1, "failed": 1, "skipped": 0,
                "tests": [{"id": "tests.test_ollama_e2e.RealOllamaE2E.test_real_frame_vision_and_stock_metadata",
                           "status": "failed"}]}
        with self.assertRaises(RuntimeError):
            accept.verify_ollama_result(data, 1)

    def test_missing_ollama_models_are_rejected(self):
        from tests.test_ollama_e2e import RealOllamaE2E
        import io
        import json
        with patch.dict("os.environ", {"DJI_RUN_OLLAMA_E2E": "1"}):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps({"models": []}).encode())
                with self.assertRaisesRegex(RuntimeError, "Required Ollama models missing"):
                    RealOllamaE2E.setUpClass()

    def test_acceptance_uses_nested_checkout_and_workspace_venv(self):
        runner = MODULE.read_text()
        accept_shell = (MODULE.parent / "accept.sh").read_text()
        preview_shell = (MODULE.parent / "preview.sh").read_text()
        self.assertIn('DJI_STOCK_REPO', runner)
        self.assertIn('dict.fromkeys((repo.parent, repo, workspace))', runner)
        for script in (accept_shell, preview_shell):
            self.assertIn('BASH_SOURCE[0]', script)
            self.assertIn('export DJI_STOCK_ROOT=', script)
            self.assertIn('"$DJI_STOCK_ROOT/.venv312/bin/python"', script)

    def test_preview_script_enforces_expected_sha(self):
        script = (MODULE.parent / "preview.sh").read_text()
        self.assertIn('DJI_EXPECTED_PR_SHA', script)
        self.assertIn('Refusing preview', script)

    def test_accept_passes_expected_sha_to_preview(self):
        script = MODULE.read_text()
        self.assertIn('env["DJI_EXPECTED_PR_SHA"] = sha', script)

    def test_profile_override_cannot_downgrade(self):
        # The runner must reject weaker profiles rather than silently skipping tests.
        script = MODULE.read_text()
        self.assertIn('order[override] < order[profile]', script)


if __name__ == "__main__":
    unittest.main()
