import json
import tempfile
import unittest
from pathlib import Path

from stock.records import load_records


class RecordDiscoveryTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        self.folder_name = "synthetic_source"
        self.approved = (
            self.root / "exports" / "approved" / self.folder_name
        )
        self.approved.mkdir(parents=True)

        self.reviews_path = (
            self.root / "metadata" / "videos"
            / self.folder_name / "reviews.json"
        )
        self.reviews_path.parent.mkdir(parents=True)

    def add_clip(self, name, status="approved",
                 create_mp4=True, manifest_start=0.0):
        review = {
            "status": status,
            "title": "Synthetic aerial landscape",
            "description": "Drone footage of a mountain landscape",
            "keywords": (
                "drone, aerial, mountains, landscape, "
                "nature, travel, sky, scenic"
            ),
            "start": 0.0,
            "end": 15.0,
        }

        reviews = {}
        if self.reviews_path.exists():
            reviews = json.loads(self.reviews_path.read_text())

        reviews[name] = review
        self.reviews_path.write_text(json.dumps(reviews))

        if create_mp4:
            (self.approved / name).write_bytes(b"synthetic-video")

        manifest = {
            "source": str(self.root / "nonexistent_original.mp4"),
            "start": manifest_start,
            "end": 15.0,
        }
        (self.approved / (name + ".source.json")).write_text(
            json.dumps(manifest)
        )

    def test_approved_clip_is_discovered(self):
        self.add_clip("approved.mp4")
        records = list(load_records(self.root))
        self.assertEqual(
            [r["filename"] for r in records],
            ["approved.mp4"],
        )

    def test_rejected_clip_is_excluded(self):
        self.add_clip("rejected.mp4", status="rejected")
        self.assertEqual(list(load_records(self.root)), [])

    def test_missing_mp4_is_excluded(self):
        self.add_clip("missing.mp4", create_mp4=False)
        self.assertEqual(list(load_records(self.root)), [])

    def test_source_time_mismatch_is_excluded(self):
        self.add_clip("mismatch.mp4", manifest_start=5.0)
        self.assertEqual(list(load_records(self.root)), [])


if __name__ == "__main__":
    unittest.main()
