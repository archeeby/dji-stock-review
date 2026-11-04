import tempfile
import unittest
from pathlib import Path

from stock.staging import plan_sync


class StagingTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upload = self.root / "upload"
        self.upload.mkdir()

        self.source = self.root / "approved.mp4"
        self.source.write_bytes(b"approved video")

    def test_missing_clip_is_scheduled_for_creation(self):
        plan = plan_sync(
            self.upload,
            {"clip.mp4": self.source},
        )

        self.assertEqual(plan["create"], ["clip.mp4"])
        self.assertFalse(plan["conflicts"])

    def test_rejected_managed_clip_is_scheduled_for_removal(self):
        stale = self.upload / "rejected.mp4"
        stale.write_bytes(b"old video")

        plan = plan_sync(
            self.upload,
            {},
            managed_names={"rejected.mp4"},
        )

        self.assertEqual(plan["remove_managed"], ["rejected.mp4"])
        self.assertTrue(stale.exists())

    def test_unknown_clip_is_preserved(self):
        unknown = self.upload / "personal.mp4"
        unknown.write_bytes(b"personal video")

        plan = plan_sync(self.upload, {})

        self.assertEqual(plan["unknown_preserved"], ["personal.mp4"])
        self.assertFalse(plan["remove_managed"])
        self.assertTrue(unknown.exists())

    def test_conflicting_clip_is_not_overwritten(self):
        conflict = self.upload / "clip.mp4"
        conflict.write_bytes(b"different video")

        plan = plan_sync(
            self.upload,
            {"clip.mp4": self.source},
        )

        self.assertEqual(plan["conflicts"], ["clip.mp4"])
        self.assertFalse(plan["create"])
        self.assertEqual(conflict.read_bytes(), b"different video")

    def test_existing_hardlink_is_unchanged(self):
        destination = self.upload / "clip.mp4"
        __import__('os').link(self.source, destination)

        plan = plan_sync(
            self.upload,
            {"clip.mp4": self.source},
        )

        self.assertEqual(plan["unchanged"], ["clip.mp4"])
        self.assertFalse(plan["create"])
        self.assertFalse(plan["conflicts"])


if __name__ == "__main__":
    unittest.main()
