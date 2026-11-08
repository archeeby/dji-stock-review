"""Real ExifTool, FFmpeg and approved-export integration using a disposable DJI copy.

This is deliberately not mocked: production export() invokes FFmpeg/FFprobe.
All source, metadata and export paths are temporary and patched in-process.
"""
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import export_approved
from candidate_reviews import key_for
from tests.test_real_dji_motion import FIXTURE, FIXTURE_SHA256, sha256


def run_tool(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180).stdout


class RealDjiToolsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ("ffmpeg", "ffprobe", "exiftool"):
            if shutil.which(name) is None:
                raise RuntimeError(f"Required real integration dependency missing: {name}")
        if not FIXTURE.is_file():
            raise RuntimeError(f"Missing immutable DJI fixture: {FIXTURE}")
        if sha256(FIXTURE) != FIXTURE_SHA256:
            raise RuntimeError("DJI fixture checksum mismatch")

    def test_exiftool_reads_real_dji_gps_without_writing_source(self):
        before = sha256(FIXTURE)
        raw = run_tool("exiftool", "-j", "-n", "-GPSLatitude", "-GPSLongitude", str(FIXTURE))
        record = json.loads(raw)[0]
        lat, lon = record.get("GPSLatitude"), record.get("GPSLongitude")
        self.assertIsInstance(lat, (int, float))
        self.assertIsInstance(lon, (int, float))
        self.assertTrue(-90 <= lat <= 90)
        self.assertTrue(-180 <= lon <= 180)
        self.assertEqual(sha256(FIXTURE), before)

    def test_real_approved_export_is_playable_idempotent_and_preserves_source(self):
        fixture_before = sha256(FIXTURE)
        with tempfile.TemporaryDirectory(prefix="dji-real-export-") as temp:
            root = Path(temp) / "relocated workspace"
            originals = root / "originals"
            work = root / "metadata" / "videos"
            dest = root / "exports" / "approved"
            originals.mkdir(parents=True)
            source = originals / FIXTURE.name
            shutil.copy2(FIXTURE, source)
            source_before = sha256(source)
            folder = "fixture-review"
            clip_id = "clip_001"
            key = key_for(source.name, clip_id)
            workspace = work / folder
            (workspace / "stock_metadata").mkdir(parents=True)
            (workspace / "clip_candidates.json").write_text(json.dumps({
                "source": source.name, "duration": 13.0,
                "clips": [{"id": clip_id, "start": 0.0, "end": 5.0, "duration": 5.0}],
            }))
            (workspace / "reviews.json").write_text(json.dumps({
                key: {"status": "approved"},
            }))
            (workspace / "stock_metadata" / f"{clip_id}.json").write_text(json.dumps({
                "metadata": {"title": "Real DJI sample", "description": "Integration export test",
                             "keywords": ["drone", "coast", "aerial"]},
            }))
            with (patch.object(export_approved, "WORK", work),
                  patch.object(export_approved, "ORIGINALS", originals),
                  patch.object(export_approved, "DEST", dest)):
                export_approved.export(folder)
                target = dest / folder / key
                manifest = dest / folder / (key + ".source.json")
                self.assertTrue(target.is_file())
                self.assertTrue(manifest.is_file())
                details = json.loads(run_tool(
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height",
                    "-show_entries", "format=duration",
                    "-of", "json", str(target),
                ))
                self.assertEqual(details["streams"][0]["codec_name"], "h264")
                self.assertGreater(int(details["streams"][0]["width"]), 0)
                self.assertGreater(int(details["streams"][0]["height"]), 0)
                self.assertAlmostEqual(float(details["format"]["duration"]), 5.0, delta=0.6)
                self.assertEqual(run_tool("ffmpeg", "-v", "error", "-i", str(target),
                                          "-f", "null", "-"), "")
                with (dest / folder / "approved_metadata.csv").open(newline="", encoding="utf-8") as csv_stream:
                    rows = list(csv.DictReader(csv_stream))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["Filename"], key)
                first_hash = sha256(target)
                export_approved.export(folder)
                self.assertEqual(sha256(target), first_hash, "Unchanged export was rewritten")
                # Simulate the pre-move sidecar, preserving the existing MP4.
                historical = json.loads(manifest.read_text())
                historical["source"] = "/old/DroneStock/originals/" + source.name
                manifest.write_text(json.dumps(historical))
                manifest_before = manifest.read_bytes()
                export_mtime = target.stat().st_mtime_ns
                with patch.object(export_approved.subprocess, "run") as encode:
                    export_approved.export(folder)
                    encode.assert_not_called()
                self.assertEqual(target.stat().st_mtime_ns, export_mtime)
                self.assertEqual(sha256(target), first_hash)
                self.assertEqual(manifest.read_bytes(), manifest_before)
                # Exercise relocation through the real CLI rather than patched globals.
                repo = Path(__file__).resolve().parents[1]
                env = dict(os.environ, HOME=str(root), DJI_STOCK_ROOT=str(root),
                           TMPDIR=str(root), PYTHONPATH=str(repo))
                cli = subprocess.run(
                    [sys.executable, str(repo / "export_approved.py"), folder],
                    cwd=root, env=env, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
                self.assertIn("SKIP unchanged", cli.stdout)
                self.assertEqual(sha256(target), first_hash)
                self.assertEqual(manifest.read_bytes(), manifest_before)
                # Real Streamlit app and real FFmpeg preview in disposable data.
                preview = subprocess.run(
                    [sys.executable, "-c", """
import sys
from streamlit.testing.v1 import AppTest
app = AppTest.from_file(sys.argv[1]).run(timeout=60)
assert not app.exception, list(app.exception)
next(s for s in app.selectbox if s.label == 'Status').select('All').run(timeout=60)
assert not app.exception, list(app.exception)
assert not app.error, [e.value for e in app.error]
assert app.text_input[0].value == 'Real DJI sample'
assert len(app.get('video')) == 1, 'Real FFmpeg preview video missing'
""", str(repo / "review_app.py")],
                    cwd=root, env=env, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)

                self.assertEqual(sha256(source), source_before)
        self.assertEqual(sha256(FIXTURE), fixture_before, "Committed original was modified")


if __name__ == "__main__":
    unittest.main()
