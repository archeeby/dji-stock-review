import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stock.managed import load_registry_v2, save_registry_v2, file_identity
from stock.staging import apply_sync


class StagingFailureTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upload = self.root / "upload"
        self.upload.mkdir()

        self.source = self.root / "approved.mp4"
        self.source.write_bytes(b"approved video")

    def test_hardlink_failure_preserves_source(self):
        with patch("os.link", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                apply_sync(self.upload, {"clip.mp4": self.source})

        self.assertEqual(self.source.read_bytes(), b"approved video")
        self.assertFalse((self.upload / "clip.mp4").exists())
        self.assertEqual(load_registry_v2(self.upload), {})

    def test_registry_failure_does_not_delete_new_hardlink(self):
        with patch(
            "stock.managed.save_registry_v2",
            side_effect=OSError("simulated registry failure"),
        ):
            with self.assertRaises(OSError):
                apply_sync(self.upload, {"clip.mp4": self.source})

        # Failed registry persistence must roll back the new hardlink.
        destination = self.upload / "clip.mp4"
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), b"approved video")
        self.assertEqual(load_registry_v2(self.upload), {})

    def test_conflict_prevents_unrelated_removal(self):
        old_source = self.root / "old.mp4"
        old_source.write_bytes(b"old approved video")

        os.link(old_source, self.upload / "old.mp4")
        save_registry_v2(self.upload, {"old.mp4": file_identity(self.upload / "old.mp4")})

        conflict = self.upload / "clip.mp4"
        conflict.write_bytes(b"foreign video")

        with self.assertRaises(FileExistsError):
            apply_sync(self.upload, {"clip.mp4": self.source})

        self.assertTrue((self.upload / "old.mp4").exists())
        self.assertEqual(set(load_registry_v2(self.upload)), {"old.mp4"})
        self.assertEqual(conflict.read_bytes(), b"foreign video")


if __name__ == "__main__":
    unittest.main()


class PartialRemovalTests(unittest.TestCase):

    def test_partial_removal_can_be_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload = root / "upload"
            upload.mkdir()

            source_a = root / "source_a.mp4"
            source_b = root / "source_b.mp4"
            source_a.write_bytes(b"video A")
            source_b.write_bytes(b"video B")

            os.link(source_a, upload / "a.mp4")
            os.link(source_b, upload / "b.mp4")

            save_registry_v2(upload, {
                "a.mp4": file_identity(upload / "a.mp4"),
                "b.mp4": file_identity(upload / "b.mp4"),
            })

            original_unlink = Path.unlink
            calls = []

            def failing_unlink(path, *args, **kwargs):
                if path.name in ("a.mp4", "b.mp4"):
                    calls.append(path.name)
                    if len(calls) == 2:
                        raise OSError("simulated deletion failure")

                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", failing_unlink):
                with self.assertRaises(OSError):
                    apply_sync(upload, {})

            # One staged link was removed, the other remains.
            self.assertEqual(
                sum((upload / name).exists()
                    for name in ("a.mp4", "b.mp4")),
                1,
            )

            # Both names remain registered for safe recovery.
            self.assertEqual(
                set(load_registry_v2(upload)),
                {"a.mp4", "b.mp4"},
            )

            # Retry completes cleanup.
            apply_sync(upload, {})

            self.assertFalse((upload / "a.mp4").exists())
            self.assertFalse((upload / "b.mp4").exists())
            self.assertEqual(load_registry_v2(upload), {})

            # Source files were never removed.
            self.assertEqual(source_a.read_bytes(), b"video A")
            self.assertEqual(source_b.read_bytes(), b"video B")


class ManagedFileReplacementTests(unittest.TestCase):

    def test_replaced_managed_file_must_not_be_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload = root / "upload"
            upload.mkdir()

            approved = root / "approved.mp4"
            approved.write_bytes(b"original approved video")

            staged = upload / "clip.mp4"
            os.link(approved, staged)
            save_registry_v2(upload, {"clip.mp4": file_identity(staged)})

            # Simulate manual replacement after registration.
            staged.unlink()
            staged.write_bytes(b"someone else's video")

            # The clip is no longer approved.
            # A safe exporter must not delete the replacement.
            try:
                apply_sync(upload, {})
            except (ValueError, RuntimeError):
                pass

            self.assertTrue(
                staged.exists(),
                "A replaced managed file was deleted!"
            )
            self.assertEqual(
                staged.read_bytes(),
                b"someone else's video",
                "A replaced managed file was modified!"
            )
            self.assertEqual(
                approved.read_bytes(),
                b"original approved video"
            )
