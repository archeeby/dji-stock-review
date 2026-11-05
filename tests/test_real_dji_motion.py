"""Real DJI motion/candidate integration test using the checked-in immutable MP4.

Run with:
    python -m unittest tests.test_real_dji_motion -v

Optionally override the fixture with DJI_TEST_VIDEO=/path/to/other.MP4.
Uses production clip limits (5/22/30 seconds) and actual OpenCV.
The original fixture is read-only; scripts write analysis only to a temp directory.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIN_CLIP_SECONDS = 5.0
MAX_CLIP_SECONDS = 30.0
FIXTURE = ROOT / "tests" / "fixtures" / "dji" / "354022_DJI_0408.MP4"
FIXTURE_SHA256 = "43ff72ef1f3b7167b71b6672b3694d50e3fc339f38e3a905f5a40ada0b7773e5"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RealDjiMotionIntegrationTests(unittest.TestCase):
    def test_real_video_contains_usable_five_second_candidate(self):
        source_name = os.environ.get("DJI_TEST_VIDEO")
        source = Path(source_name).expanduser().resolve() if source_name else FIXTURE
        self.assertTrue(source.is_file(), f"Missing DJI fixture: {source}")
        before = sha256(source)
        if not source_name:
            self.assertEqual(before, FIXTURE_SHA256, "Checked-in DJI fixture SHA-256 mismatch")

        with tempfile.TemporaryDirectory(prefix="dji-motion-integration-") as temp:
            work = Path(temp)
            motion = work / "camera_motion.json"
            composition = work / "composition_analysis.json"
            candidates = work / "clip_candidates.json"

            for script, arguments in (
                ("analyze_camera_motion_batch.py", [source, motion]),
                ("analyze_composition_batch.py", [source, composition]),
                ("detect_scenes_v4_batch.py", [composition, motion, candidates]),
            ):
                completed = subprocess.run(
                    [sys.executable, str(ROOT / script), *map(str, arguments)],
                    check=False,
                    cwd=ROOT,
                    timeout=180,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{script} failed (exit {completed.returncode})\\n"
                    f"stdout:\\n{completed.stdout}\\nstderr:\\n{completed.stderr}",
                )

            result = json.loads(candidates.read_text())
            self.assertEqual(result["source"], source.name)
            self.assertGreater(float(result["duration"]), MIN_CLIP_SECONDS)

            clips = result["clips"]
            self.assertTrue(
                clips,
                "Hypothesis failed: the real DJI clip produced no >=5s usable "
                "candidate. Inspect motion warnings and excluded intervals "
                f"before changing the algorithm or this assertion. Excluded: {result['excluded']}",
            )

            for clip in clips:
                with self.subTest(clip=clip["id"]):
                    start = float(clip["start"])
                    end = float(clip["end"])
                    self.assertGreaterEqual(start, 0)
                    self.assertLessEqual(end, float(result["duration"]) + 0.01)
                    self.assertGreaterEqual(end - start, MIN_CLIP_SECONDS - 0.02)
                    self.assertLessEqual(end - start, MAX_CLIP_SECONDS + 0.02)
                    self.assertAlmostEqual(float(clip["duration"]), end - start, delta=0.02)
                    for excluded in result["excluded"]:
                        overlap = min(end, excluded["end"]) - max(start, excluded["start"])
                        self.assertLessEqual(overlap, 0.02, f"Candidate overlaps excluded motion: {excluded}")

        self.assertEqual(sha256(source), before, "Original DJI source was modified")


if __name__ == "__main__":
    unittest.main()
