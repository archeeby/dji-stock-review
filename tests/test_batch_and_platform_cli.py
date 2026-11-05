"""CLI regression checks for batch discovery and stock-platform failure safety.

Run against disposable HOME/root only. Never touch the user's DroneStock library.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BatchDiscoveryIntegrationTests(unittest.TestCase):
    def test_dry_run_recurses_and_filters_video_extensions_without_writes(self):
        with tempfile.TemporaryDirectory(prefix="dji-batch-discovery-") as tmp:
            home = Path(tmp)
            originals = home / "DroneStock" / "originals"
            (originals / "nested").mkdir(parents=True)
            for name in ("B.MP4", "a.mov", "notes.txt", "nested/c.M4V"):
                path = originals / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"discovery only")
            env = {**os.environ, "HOME": str(home)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "run_batch.py"), "--dry-run"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Found 3 videos", result.stdout)
            self.assertIn("B.MP4", result.stdout)
            self.assertIn("a.mov", result.stdout)
            self.assertIn("nested/c.M4V", result.stdout)
            self.assertNotIn("notes.txt", result.stdout)
            self.assertFalse((home / "DroneStock" / "metadata").exists())

    def test_dry_run_limit_applies_to_sorted_discovery(self):
        with tempfile.TemporaryDirectory(prefix="dji-batch-limit-") as tmp:
            home = Path(tmp)
            originals = home / "DroneStock" / "originals"
            originals.mkdir(parents=True)
            for name in ("b.mp4", "a.mp4"):
                (originals / name).write_bytes(b"not decoded in dry run")
            result = subprocess.run(
                [sys.executable, str(ROOT / "run_batch.py"), "--dry-run", "--limit", "1"],
                cwd=ROOT, env={**os.environ, "HOME": str(home)},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Found 1 videos", result.stdout)
            self.assertIn("a.mp4", result.stdout)
            self.assertNotIn("b.mp4", result.stdout)
            self.assertFalse((home / "DroneStock" / "metadata").exists())


class PlatformCliFailureSafetyTests(unittest.TestCase):
    def test_invalid_category_overrides_fail_without_creating_platform_outputs(self):
        with tempfile.TemporaryDirectory(prefix="dji-platform-invalid-") as tmp:
            root = Path(tmp)
            metadata = root / "metadata"
            metadata.mkdir()
            (metadata / "platform_category_overrides.json").write_text(
                json.dumps(["wrong", "shape"]), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "export_stock_platforms.py"), "--root", str(root)],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be a JSON object", result.stderr)
            self.assertFalse((root / "platforms").exists())

    def test_empty_library_generates_no_uploads_or_csv(self):
        with tempfile.TemporaryDirectory(prefix="dji-platform-empty-") as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(ROOT / "export_stock_platforms.py"), "--root", str(root)],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Approved existing MP4 with matching manifests: 0", result.stdout)
            self.assertEqual(list(root.rglob("*.csv")), [])
            self.assertEqual(list(root.rglob("*.mp4")), [])


if __name__ == "__main__":
    unittest.main()
