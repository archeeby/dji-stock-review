"""Recovery contracts for interrupted FFmpeg exports.

All test files live in TemporaryDirectory; the real DroneStock tree is never used.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import export_approved
from candidate_reviews import key_for


class InterruptedExportRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dji-interrupted-export-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.originals = self.root / "originals"
        self.work = self.root / "metadata" / "videos"
        self.dest = self.root / "exports" / "approved"
        self.originals.mkdir()
        self.source = self.originals / "source.MP4"
        self.source.write_bytes(b"original video remains immutable")
        self.folder = "video_001"
        folder = self.work / self.folder
        (folder / "stock_metadata").mkdir(parents=True)
        (folder / "clip_candidates.json").write_text(json.dumps({
            "source": self.source.name, "duration": 10,
            "clips": [{"id": "clip_01", "start": 0, "end": 5}],
        }))
        self.key = key_for(self.source.name, "clip_01")
        (folder / "reviews.json").write_text(json.dumps({
            self.key: {"status": "approved"}
        }))
        (folder / "stock_metadata" / "clip_01.json").write_text(json.dumps({
            "metadata": {"title": "Coast", "description": "Aerial coast",
                         "keywords": ["drone", "coast", "sky"]}
        }))
        self.output = self.dest / self.folder
        self.target = self.output / self.key
        self.manifest = self.output / (self.key + ".source.json")
        self.partial = self.output / (self.key + ".partial.mp4")
        self.calls = []

    def fake_run(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"valid regenerated video")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"")

    def run_export(self, runner=None):
        with (patch.object(export_approved, "WORK", self.work),
              patch.object(export_approved, "ORIGINALS", self.originals),
              patch.object(export_approved, "DEST", self.dest),
              patch.object(export_approved.subprocess, "run",
                           side_effect=runner or self.fake_run)):
            export_approved.export(self.folder)

    def test_stale_partial_from_killed_process_is_replaced_on_resume(self):
        self.output.mkdir(parents=True)
        self.partial.write_bytes(b"truncated video from killed process")
        self.run_export()
        self.assertFalse(self.partial.exists())
        self.assertEqual(self.target.read_bytes(), b"valid regenerated video")
        self.assertTrue(self.manifest.exists())
        self.assertEqual(self.source.read_bytes(), b"original video remains immutable")
        first_calls = len([c for c in self.calls if c[0] == "ffmpeg"])
        self.run_export()
        self.assertEqual(len([c for c in self.calls if c[0] == "ffmpeg"]), first_calls)

    def test_ffprobe_failure_removes_partial_and_resume_succeeds(self):
        def probe_failure(cmd, **kwargs):
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).write_bytes(b"invalid video")
                return subprocess.CompletedProcess(cmd, 0)
            raise subprocess.CalledProcessError(1, cmd)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_export(probe_failure)
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.target.exists())
        self.assertFalse(self.manifest.exists())
        self.run_export()
        self.assertEqual(self.target.read_bytes(), b"valid regenerated video")
        self.assertTrue(self.manifest.exists())

    def test_rejected_clip_removes_existing_export_and_manifest_without_touching_original(self):
        self.run_export()
        reviews_path = self.work / self.folder / "reviews.json"
        reviews_path.write_text(json.dumps({self.key: {"status": "rejected"}}))
        self.run_export()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(self.source.read_bytes(), b"original video remains immutable")


if __name__ == "__main__":
    unittest.main()
