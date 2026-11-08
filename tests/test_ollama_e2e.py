"""Opt-in real Ollama E2E. No mocks, no writes outside disposable HOME."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.request

from tests.test_real_dji_motion import FIXTURE, FIXTURE_SHA256, sha256

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("qwen3-vl:4b", "qwen3:4b")


class RealOllamaE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("DJI_RUN_OLLAMA_E2E") != "1":
            raise unittest.SkipTest("Ollama E2E opt-in only; set DJI_RUN_OLLAMA_E2E=1")
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=15) as response:
            tags = json.load(response)
        available = {model["name"] for model in tags.get("models", [])}
        missing = set(MODELS) - available
        if missing:
            raise RuntimeError(f"Required Ollama models missing: {sorted(missing)}")

    def test_real_frame_vision_and_stock_metadata(self):
        self.assertEqual(sha256(FIXTURE), FIXTURE_SHA256)
        with tempfile.TemporaryDirectory(prefix="dji-ollama-e2e-") as tmp:
            root = Path(tmp) / "relocated workspace" / "DroneStock"
            root.mkdir(parents=True)
            originals = root / "originals"
            originals.mkdir()
            copied_source = originals / FIXTURE.name
            copied_source.write_bytes(FIXTURE.read_bytes())
            candidates = root / "clip_candidates.json"
            clip = {"id": "clip_001", "start": 0.0, "end": 5.0, "duration": 5.0}
            candidates.write_text(json.dumps({"source": FIXTURE.name, "duration": 5.0, "clips": [clip]}))
            analysis_dir = root / "vision"
            metadata_dir = root / "metadata"
            env = os.environ.copy()
            env["HOME"] = str(root)
            env["DJI_STOCK_ROOT"] = str(root)
            env["TMPDIR"] = str(root)
            def run(script, *args):
                proc = subprocess.run(
                    [sys.executable, str(ROOT / script), *map(str, args)],
                    cwd=root, env=env, capture_output=True, text=True, timeout=900,
                )
                self.assertEqual(proc.returncode, 0, f"{script}: {proc.stdout}\n{proc.stderr}")
                return proc

            run("analyze_auto_single_frame_batch.py", candidates, analysis_dir,
                clip["id"], "--video", copied_source)
            vision = json.loads((analysis_dir / "clip_001.json").read_text())
            self.assertEqual(vision["model"], MODELS[0])
            self.assertEqual(vision["source"], FIXTURE.name)
            for field in ("subjects", "scene", "composition_change",
                          "commercial_uses", "quality_concerns"):
                self.assertIn(field, vision["analysis"])
            self.assertIsInstance(vision["analysis"]["subjects"], list)
            self.assertIsInstance(vision["analysis"]["scene"], str)
            self.assertTrue(vision["analysis"]["scene"].strip())

            # This producer catches per-clip exceptions and can exit 0 on failure.
            # The output-file and contract checks below are therefore mandatory.
            run("generate_stock_metadata_batch.py", candidates, analysis_dir,
                metadata_dir, "--location", "Unknown")
            target = metadata_dir / "clip_001.json"
            self.assertTrue(target.is_file(), "Metadata producer exited without an output")
            metadata = json.loads(target.read_text())
            self.assertEqual(metadata["model"], MODELS[1])
            self.assertEqual(metadata["location"], "Unknown")
            fields = metadata["metadata"]
            self.assertTrue(0 < len(fields["title"].strip()) <= 100)
            self.assertTrue(0 < len(fields["description"].strip()) <= 350)
            self.assertGreaterEqual(len(fields["keywords"]), 8)
            # Continue the same real-model acceptance test through real FFmpeg.
            # Approval is simulated; no human clicks or writes to personal data.
            from candidate_reviews import key_for
            work = root / "metadata" / "videos"
            folder = "ollama-e2e"
            workspace = work / folder
            (workspace / "stock_metadata").mkdir(parents=True)
            (workspace / "clip_candidates.json").write_text(candidates.read_text())
            (workspace / "stock_metadata" / "clip_001.json").write_text(target.read_text())
            key = key_for(FIXTURE.name, "clip_001")
            review_path = workspace / "reviews.json"
            output_dir = root / "exports" / "approved"
            output = output_dir / folder / key
            sidecar = output.with_name(key + ".source.json")

            def set_status(status):
                review_path.write_text(json.dumps({key: {"status": status}}))

            def export():
                # Use the real CLI/env boundary, including data-root resolution.
                return run("export_approved.py", folder)

            set_status("approved")
            export()
            self.assertTrue(output.is_file())
            self.assertTrue(sidecar.is_file())
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration:stream=codec_name", "-of", "json", str(output)],
                capture_output=True, text=True, check=True, timeout=60,
            )
            video = json.loads(probe.stdout)
            self.assertGreater(float(video["format"]["duration"]), 4.0)
            self.assertTrue(any(stream.get("codec_name") == "h264"
                                for stream in video.get("streams", [])))
            original_output = output.read_bytes()
            export_mtime = output.stat().st_mtime_ns
            sidecar_before = sidecar.read_bytes()
            repeat = export()  # Unchanged approved export is idempotent.
            self.assertIn("SKIP unchanged", repeat.stdout)
            self.assertEqual(output.stat().st_mtime_ns, export_mtime)
            self.assertEqual(sidecar.read_bytes(), sidecar_before)
            self.assertEqual(output.read_bytes(), original_output)
            set_status("rejected")
            export()
            self.assertFalse(output.exists())
            self.assertFalse(sidecar.exists())
            set_status("approved")
            export()
            self.assertTrue(output.is_file())
            self.assertTrue(sidecar.is_file())
            self.assertEqual(sha256(copied_source), FIXTURE_SHA256)
            self.assertEqual(sha256(FIXTURE), FIXTURE_SHA256)


if __name__ == "__main__":
    unittest.main()
