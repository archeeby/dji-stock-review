"""Export lifecycle regressions using disposable originals and mocked encoding.

The FFmpeg invocation is exercised as an integration boundary; the existing
real-DJI integration tests separately validate actual FFmpeg output.
"""
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import export_approved
from candidate_reviews import key_for


class ApprovedExportLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dji-lifecycle-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "metadata" / "videos"
        self.originals = self.root / "originals"
        self.dest = self.root / "exports" / "approved"
        self.originals.mkdir()
        self.source = self.originals / "sample.MP4"
        self.source.write_bytes(b"immutable test original")
        self.folder = "sample-work"
        self.workspace = self.work / self.folder
        (self.workspace / "stock_metadata").mkdir(parents=True)
        self.clips = [
            {"id": "clip_01", "start": 0, "end": 5},
            {"id": "clip_02", "start": 5, "end": 10},
        ]
        (self.workspace / "clip_candidates.json").write_text(json.dumps({
            "source": self.source.name, "duration": 10, "clips": self.clips,
        }))
        for clip in self.clips:
            (self.workspace / "stock_metadata" / (clip["id"] + ".json")).write_text(
                json.dumps({"metadata": {"title": "Coast", "description": "Aerial coast",
                                         "keywords": ["drone", "coast", "sea"]}})
            )
        self.reviews_path = self.workspace / "reviews.json"
        self.calls = []

    def set_reviews(self, **statuses):
        self.reviews_path.write_text(json.dumps({
            key_for(self.source.name, clip_id): {"status": status}
            for clip_id, status in statuses.items()
        }))

    def fake_run(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"encoded output")
        return subprocess.CompletedProcess(command, 0, stdout=b"")

    def export(self, runner=None):
        with (patch.object(export_approved, "WORK", self.work),
              patch.object(export_approved, "ORIGINALS", self.originals),
              patch.object(export_approved, "DEST", self.dest),
              patch.object(export_approved.subprocess, "run",
                           side_effect=runner or self.fake_run)):
            export_approved.export(self.folder)

    def output(self, clip_id):
        return self.dest / self.folder / key_for(self.source.name, clip_id)

    def csv_rows(self):
        with (self.dest / self.folder / "approved_metadata.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            return list(csv.DictReader(stream))

    def test_approve_reject_reapprove_deletes_only_generated_files(self):
        original = self.source.read_bytes()
        self.set_reviews(clip_01="approved", clip_02="rejected")
        self.export()
        first = self.output("clip_01")
        sidecar = first.with_name(first.name + ".source.json")
        self.assertTrue(first.exists())
        self.assertTrue(sidecar.exists())
        self.assertFalse(self.output("clip_02").exists())
        self.assertEqual(len(self.csv_rows()), 1)
        count = len([c for c in self.calls if c[0] == "ffmpeg"])
        self.export()
        self.assertEqual(len([c for c in self.calls if c[0] == "ffmpeg"]), count)
        self.set_reviews(clip_01="rejected", clip_02="rejected")
        self.export()
        self.assertFalse(first.exists())
        self.assertFalse(sidecar.exists())
        self.assertEqual(self.csv_rows(), [])
        self.assertEqual(self.source.read_bytes(), original)
        self.set_reviews(clip_01="approved", clip_02="rejected")
        self.export()
        self.assertTrue(first.exists())
        self.assertTrue(sidecar.exists())
        self.assertEqual(len([c for c in self.calls if c[0] == "ffmpeg"]), count + 1)

    def test_trim_edit_invalidates_only_changed_export(self):
        self.set_reviews(clip_01="approved", clip_02="approved")
        self.export()
        before = {clip: json.loads(self.output(clip).with_name(
            self.output(clip).name + ".source.json"
        ).read_text()) for clip in ("clip_01", "clip_02")}
        self.calls.clear()
        reviews = json.loads(self.reviews_path.read_text())
        reviews[key_for(self.source.name, "clip_01")]["end"] = 6
        self.reviews_path.write_text(json.dumps(reviews))
        self.export()
        self.assertEqual(len([c for c in self.calls if c[0] == "ffmpeg"]), 1)
        after = {clip: json.loads(self.output(clip).with_name(
            self.output(clip).name + ".source.json"
        ).read_text()) for clip in ("clip_01", "clip_02")}
        self.assertEqual(after["clip_01"]["end"], 6)
        self.assertEqual(after["clip_02"], before["clip_02"])

    def test_ffmpeg_failure_does_not_publish_partial_export(self):
        self.set_reviews(clip_01="approved", clip_02="rejected")
        def failing_run(command, **kwargs):
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"partial")
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)
        with self.assertRaises(subprocess.CalledProcessError):
            self.export(failing_run)
        target = self.output("clip_01")
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + ".source.json").exists())
        self.assertFalse(target.with_name(target.name + ".partial.mp4").exists())
        self.assertEqual(self.source.read_bytes(), b"immutable test original")
        self.export()
        self.assertTrue(target.exists())

    def test_invalid_review_bounds_do_not_publish_export(self):
        self.set_reviews(clip_01="approved")
        reviews = json.loads(self.reviews_path.read_text())
        reviews[key_for(self.source.name, "clip_01")]["end"] = 4
        self.reviews_path.write_text(json.dumps(reviews))
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.output("clip_01").exists())


if __name__ == "__main__":
    unittest.main()
