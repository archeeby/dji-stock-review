"""Relocation regression checks using disposable data only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workspace_paths import REPO_ROOT, data_root, video_work_dir, same_export


class WorkspacePathsTests(unittest.TestCase):
    def test_default_ignores_home_and_cwd(self):
        with patch.dict(os.environ, {"HOME": "/nonexistent"}):
            with patch.dict(os.environ):
                os.environ.pop("DJI_STOCK_ROOT", None)
                self.assertEqual(data_root(), REPO_ROOT.parent)

    def test_explicit_root_and_invalid_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, DJI_STOCK_ROOT=tmp):
                self.assertEqual(data_root(), Path(tmp).resolve())
        for value in ("", "relative/path"):
            with patch.dict(os.environ, DJI_STOCK_ROOT=value):
                with self.assertRaises(ValueError):
                    data_root()

    def test_reuses_metadata_after_move_and_refuses_ambiguous_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "metadata/videos/historical_hash"
            folder.mkdir(parents=True)
            record = folder / "clip_candidates.json"
            record.write_text(json.dumps({"source": "source.MP4", "clips": []}))
            before = record.read_bytes()
            self.assertEqual(video_work_dir(root / "originals/source.MP4", root), folder)
            self.assertEqual(record.read_bytes(), before)
            other = folder.with_name("duplicate")
            other.mkdir()
            (other / record.name).write_bytes(before)
            with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
                video_work_dir(root / "originals/source.MP4", root)

    def test_relocated_export_skips_encoding_but_changed_specs_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "originals/nested/source.MP4"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fixture")
            spec = {"source": str(source.resolve()), "source_size": 7,
                    "source_mtime_ns": source.stat().st_mtime_ns, "start": 0, "end": 5}
            old = dict(spec, source="/old/DroneStock/originals/nested/source.MP4")
            self.assertTrue(same_export(old, spec, root))
            for key, value in (("source_size", 8), ("source_mtime_ns", 0), ("end", 6)):
                self.assertFalse(same_export(dict(old, **{key: value}), spec, root))

    def test_current_folder_cannot_hide_historical_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'originals/source.MP4'
            current = video_work_dir(source, root)
            current.mkdir(parents=True)
            historical = current.with_name('historical')
            historical.mkdir()
            record = json.dumps({'source': source.name, 'clips': []})
            (historical / 'clip_candidates.json').write_text(record)
            # An empty newly created directory must not hide the old records.
            self.assertEqual(video_work_dir(source, root), historical)
            (current / 'clip_candidates.json').write_text(record)
            with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
                video_work_dir(source, root)

    def test_partial_analyses_are_reused_and_conflicts_stop_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'metadata/videos/historical'
            folder.mkdir(parents=True)
            motion = folder / 'camera_motion.json'
            motion.write_text(json.dumps({'filename': 'source.MP4', 'measurements': []}))
            before = motion.read_bytes()
            self.assertEqual(video_work_dir(root / 'originals/source.MP4', root), folder)
            (folder / 'composition_analysis.json').write_text(json.dumps({'filename': 'other.MP4'}))
            with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
                video_work_dir(root / 'originals/source.MP4', root)
            (folder / 'clip_candidates.json').write_text(json.dumps({'source': 'source.MP4'}))
            with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
                video_work_dir(root / 'originals/source.MP4', root)
            self.assertEqual(motion.read_bytes(), before)

    def test_duplicate_original_names_cannot_share_historical_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('a', 'b'):
                source = root / 'originals' / name / 'source.MP4'
                source.parent.mkdir(parents=True)
                source.write_bytes(name.encode())
            folder = root / 'metadata/videos/historical'
            folder.mkdir(parents=True)
            (folder / 'clip_candidates.json').write_text(json.dumps({'source': 'source.MP4'}))
            for name in ('a', 'b'):
                with self.assertRaisesRegex(RuntimeError, 'Ambiguous original'):
                    video_work_dir(root / 'originals' / name / 'source.MP4', root)

    def test_corrupt_historical_record_is_not_silently_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'metadata/videos/historical'
            folder.mkdir(parents=True)
            record = folder / 'camera_motion.json'
            record.write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                video_work_dir(root / 'originals/source.MP4', root)
            self.assertEqual(record.read_text(), '{broken')

    def test_external_same_name_video_cannot_reuse_workspace_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'workspace'
            source = root / 'originals/source.MP4'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'workspace original')
            external = Path(tmp) / 'source.MP4'
            external.write_bytes(b'unrelated external original')
            folder = root / 'metadata/videos/historical'
            folder.mkdir(parents=True)
            (folder / 'clip_candidates.json').write_text(json.dumps({'source': source.name}))
            with self.assertRaisesRegex(RuntimeError, 'external source'):
                video_work_dir(external, root)
            self.assertEqual(source.read_bytes(), b'workspace original')
