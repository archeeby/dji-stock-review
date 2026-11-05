"""Verify batch retry/resume using disposable HOME and a fake pipeline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = """
import hashlib, json, sys
from pathlib import Path
source = Path(sys.argv[1]).resolve()
root = Path.home() / 'DroneStock'
folder = root / 'metadata' / 'videos' / (source.stem + '_' + hashlib.sha256(str(source).encode()).hexdigest()[:10])
attempts = root / 'attempts.json'
state = json.loads(attempts.read_text()) if attempts.exists() else {}
state[source.name] = state.get(source.name, 0) + 1
attempts.write_text(json.dumps(state))
if source.name == 'b.MP4' and state[source.name] == 1:
    sys.exit(9)
folder.mkdir(parents=True, exist_ok=True)
clip = {'id': 'auto_01', 'start': 0, 'end': 5}
(folder / 'clip_candidates.json').write_text(json.dumps({'source': source.name, 'duration': 5, 'clips': [clip]}))
(folder / 'camera_motion.json').write_text('{}')
(folder / 'composition_analysis.json').write_text('{}')
(folder / 'ai').mkdir(exist_ok=True)
(folder / 'stock_metadata').mkdir(exist_ok=True)
(folder / 'ai' / 'auto_01.json').write_text(json.dumps({'clip': clip, 'analysis': 'valid analysis'}))
(folder / 'stock_metadata' / 'auto_01.json').write_text(json.dumps({'clip': clip, 'metadata': {'title': 'Coast', 'description': 'Aerial footage', 'keywords': ['keyword' + str(i) for i in range(15)]}}))
"""


class BatchResumeIntegrationTests(unittest.TestCase):
    def test_failed_video_retries_without_reprocessing_completed_video(self):
        with tempfile.TemporaryDirectory(prefix="dji-batch-resume-") as tmp:
            home = Path(tmp)
            root = home / "DroneStock"
            originals = root / "originals"
            originals.mkdir(parents=True)
            for name in ("a.MP4", "b.MP4"):
                (originals / name).write_bytes(b"immutable " + name.encode())
            before = {p.name: p.read_bytes() for p in originals.iterdir()}
            (root / "run_pipeline.py").write_text(PIPELINE)
            env = dict(os.environ, HOME=str(home))

            def batch():
                return subprocess.run(
                    [sys.executable, str(ROOT / "run_batch.py")],
                    env=env, cwd=ROOT, capture_output=True, text=True, timeout=120,
                )

            first = batch()
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("1 successful, 1 failed", first.stdout)
            attempts = root / "attempts.json"
            self.assertEqual(json.loads(attempts.read_text()), {"a.MP4": 1, "b.MP4": 1})
            second = batch()
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("SKIPPED: already processed", second.stdout)
            self.assertIn("2 successful, 0 failed", second.stdout)
            self.assertEqual(json.loads(attempts.read_text()), {"a.MP4": 1, "b.MP4": 2})
            log = json.loads((root / "metadata" / "batch_results.json").read_text())
            self.assertEqual(len(log), 2)
            self.assertEqual({entry["status"] for entry in log}, {"success"})
            self.assertEqual({p.name: p.read_bytes() for p in originals.iterdir()}, before)
            third = batch()
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertEqual(json.loads(attempts.read_text()), {"a.MP4": 1, "b.MP4": 2})


if __name__ == "__main__":
    unittest.main()
