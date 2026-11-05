"""Approved-record discovery safety: only reviewed, matching exports are publishable."""
import json
from pathlib import Path
import tempfile
import unittest

from stock.records import load_records


class ApprovedRecordDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dji-records-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "exports" / "approved" / "source"
        self.folder.mkdir(parents=True)
        self.reviews = self.root / "metadata" / "videos" / "source" / "reviews.json"
        self.reviews.parent.mkdir(parents=True)
        self.name = "source_auto_01.mp4"
        self.mp4 = self.folder / self.name
        self.mp4.write_bytes(b"exported test clip")
        (self.folder / (self.name + ".source.json")).write_text(json.dumps({
            "source": str(self.root / "missing_original.mp4"),
            "start": 1, "end": 8,
        }))
        self.review = {"status": "approved", "start": 1, "end": 8,
                       "title": "Coast", "description": "Aerial coastline",
                       "keywords": "coast, sea, aerial, travel, nature, sky, drone"}

    def records(self, review):
        self.reviews.write_text(json.dumps({self.name: review}))
        return list(load_records(self.root))

    def test_valid_approved_export_with_matching_manifest_is_discovered(self):
        records = self.records(self.review)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], self.mp4)
        self.assertEqual(records[0]["filename"], self.name)

    def test_pending_and_rejected_exports_are_not_published(self):
        for status in ("pending", "rejected"):
            with self.subTest(status=status):
                self.assertEqual(self.records(dict(self.review, status=status)), [])

    def test_stale_manifest_after_trim_edit_is_not_published(self):
        self.assertEqual(self.records(dict(self.review, end=9)), [])

    def test_incomplete_metadata_is_not_published(self):
        for field in ("title", "description", "keywords"):
            with self.subTest(field=field):
                self.assertEqual(self.records(dict(self.review, **{field: " "})), [])

    def test_missing_or_empty_export_is_not_published(self):
        self.mp4.write_bytes(b"")
        self.assertEqual(self.records(self.review), [])
        self.mp4.unlink()
        self.assertEqual(self.records(self.review), [])

    def test_corrupt_manifest_and_review_are_not_published(self):
        manifest = self.folder / (self.name + ".source.json")
        manifest.write_text("{bad json")
        self.assertEqual(self.records(self.review), [])
        manifest.unlink()
        self.assertEqual(self.records(self.review), [])
        self.reviews.write_text("{bad json")
        self.assertEqual(list(load_records(self.root)), [])


if __name__ == "__main__":
    unittest.main()
