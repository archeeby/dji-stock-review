"""Opt-in real DJI motion/candidate integration test.

Run with:
    DJI_TEST_VIDEO=/absolute/path/to/original.MP4 \
      python -m unittest tests.test_real_dji_motion -v

Uses production clip limits (5/22/30 seconds) and actual OpenCV.
The original video is read-only and never copied to the repository.
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


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RealDjiMotionIntegrationTests(unittest.TestCase):
    def test_real_video_contains_usable_five_second_candidate(self):
        source_name = os.environ.get("DJI_TEST_VIDEO")
        if not source_name:
            self.skipTest("Set DJI_TEST_VIDEO to an original DJI MP4 to run real-video integration")

        source = Path(source_name).expanduser().resolve()
        self.assertTrue(source.is_file(), f"Missing DJI fixture: {source}")
        before = sha256(source)

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
                with self.subTest(script=script):
                    subprocess.run(
                        [sys.executable, str(ROOT / script), *map(str, arguments)],
                        check=True,
                        cwd=ROOT,
                        timeout=180,
                        capture_output=True,
                        text=True,
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
