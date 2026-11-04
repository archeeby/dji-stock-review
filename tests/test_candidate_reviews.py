import csv
from contextlib import contextmanager
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import candidate_reviews as cr
import export_approved
import library_stats


class CandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'metadata/videos'
        self.folder = self.work / 'source'
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'reviews.json'
        self.data = {'source': 'source.MP4', 'duration': 30, 'clips': [
            {'id': 'auto_01', 'start': 0, 'end': 10},
            {'id': 'auto_02', 'start': 10, 'end': 20}]}
        (self.folder / 'clip_candidates.json').write_text(json.dumps(self.data))
        self.path.write_text('{}')
        (self.root / 'originals').mkdir()
        (self.root / 'originals/source.MP4').write_bytes(b'fake original')
        (self.folder / 'stock_metadata').mkdir()
        for clip in self.data['clips']:
            (self.folder / 'stock_metadata' / (clip['id'] + '.json')).write_text(json.dumps(
                {'metadata': {'title': 'Title', 'description': 'Description', 'keywords': ['drone']}}))

    def reviews(self):
        return json.loads(self.path.read_text())

    def save(self, clip, status):
        return cr.save_review(self.path, 'source.MP4', clip, {'status': status})

    def status(self, clip):
        return cr.review_status(cr.get_review(self.reviews(), 'source.MP4', clip))

    def test_decisions_and_undo_are_candidate_scoped(self):
        reject = self.save('auto_01', 'rejected')
        self.assertEqual(self.status('auto_02'), 'pending')
        approve = self.save('auto_02', 'approved')
        self.assertEqual(self.status('auto_01'), 'rejected')
        cr.undo_review(self.path, approve)
        self.assertEqual(self.status('auto_02'), 'pending')
        self.assertEqual(self.status('auto_01'), 'rejected')
        cr.undo_review(self.path, reject)
        self.assertEqual(self.reviews(), {})

    def test_undo_preserves_legacy_and_unrelated_changes(self):
        legacy = {'auto_01': {'status': 'approved', 'note': 'legacy'}}
        self.path.write_text(json.dumps(legacy))
        action = self.save('auto_01', 'rejected')
        self.save('auto_02', 'approved')
        cr.undo_review(self.path, action)
        self.assertEqual(self.status('auto_01'), 'approved')
        self.assertEqual(self.status('auto_02'), 'approved')
        self.assertNotIn('source_auto_01.mp4', self.reviews())

    def test_counters_and_labels_match_json(self):
        for clip, status in [('auto_01', 'rejected'), ('auto_02', 'approved')]:
            self.save(clip, status)
        with patch.object(library_stats, 'WORK', self.work), patch.object(library_stats, 'EXPORTS', self.root / 'exports'):
            totals, _ = library_stats.get_library_stats()
        self.assertEqual([totals[k] for k in ('candidates', 'approved', 'rejected', 'pending')], [2, 1, 1, 0])
        self.assertEqual(cr.status_label(self.status('auto_01')), '❌ Rejected')
        self.assertEqual(cr.status_label(self.status('auto_02')), '✅ Approved')
        self.assertEqual(cr.status_label('pending'), 'Pending')

    def test_queue_order_stays_stable_after_decision(self):
        other = self.work / 'z_other'
        other.mkdir()
        data = dict(self.data, source='other.MP4')
        (other / 'clip_candidates.json').write_text(json.dumps(data))
        with patch.object(library_stats, 'WORK', self.work), patch.object(library_stats, 'EXPORTS', self.root / 'exports'):
            before = [v['folder'] for v in library_stats.get_library_stats()[1]]
            self.save('auto_01', 'rejected')
            after = [v['folder'] for v in library_stats.get_library_stats()[1]]
        self.assertEqual(before, after)

    def test_export_only_approved_without_video_encoding(self):
        self.save('auto_01', 'rejected')
        self.save('auto_02', 'approved')
        commands = []
        def fake_run(command, **kwargs):
            commands.append(command)
            if command[0] == 'ffmpeg':
                Path(command[-1]).write_bytes(b'fake export')
        with patch.object(export_approved, 'WORK', self.work), patch.object(export_approved, 'ORIGINALS', self.root / 'originals'), patch.object(export_approved, 'DEST', self.root / 'exports'), patch.object(export_approved.subprocess, 'run', side_effect=fake_run):
            export_approved.export('source')
        output = self.root / 'exports/source'
        self.assertEqual([p.name for p in output.glob('*.mp4')], ['source_auto_02.mp4'])
        with (output / 'approved_metadata.csv').open() as f:
            self.assertEqual([r['Filename'] for r in csv.DictReader(f)], ['source_auto_02.mp4'])
        self.assertEqual(sum(c[0] == 'ffmpeg' for c in commands), 1)
        self.assertEqual((self.root / 'originals/source.MP4').read_bytes(), b'fake original')

    def test_dropdown_navigation_and_actions(self):
        from streamlit.testing.v1 import AppTest
        script = Path('review_app.py').read_text().replace('ROOT = Path.home() / "DroneStock"', f'ROOT = Path({str(self.root)!r})')
        app_path = self.root / 'test_app.py'
        app_path.write_text(script)
        def button(app, label):
            return next(b for b in app.button if b.label == label)
        def dropdown(app):
            return next(s for s in app.selectbox if s.label == 'Clip')
        with patch.object(library_stats, 'WORK', self.work), patch.object(library_stats, 'EXPORTS', self.root / 'exports'), patch('subprocess.run') as run:
            run.return_value.stdout = b'fake preview'
            app = AppTest.from_file(str(app_path)).run()
            self.assertFalse(app.exception)
            button(app, '❌ Reject').click().run()
            self.assertEqual(self.status('auto_01'), 'rejected')
            self.assertEqual(self.status('auto_02'), 'pending')
            self.assertIn('auto_02', dropdown(app).options[0])
            next(x for x in app.selectbox if x.label == 'Status').select('All').run()
            button(app, '✅ Approve').click().run()
            self.assertEqual(self.status('auto_01'), 'rejected')
            self.assertEqual(self.status('auto_02'), 'approved')
            self.assertTrue(any('✅ Approved' in o for o in dropdown(app).options))
            self.assertTrue(any('❌ Rejected' in o for o in dropdown(app).options))
            button(app, '↶ Undo').click().run()
            self.assertEqual(dropdown(app).value, 1)
            self.assertIn('Pending', dropdown(app).options[1])
            self.assertEqual(self.status('auto_01'), 'rejected')
            button(app, '◀').click().run()
            self.assertEqual(dropdown(app).value, 0)
            button(app, '▶').click().run()
            self.assertEqual(dropdown(app).value, 1)
            self.assertFalse(app.exception)


    @contextmanager
    def ui(self):
        from streamlit.testing.v1 import AppTest
        script = Path('review_app.py').read_text().replace(
            'ROOT = Path.home() / "DroneStock"', f'ROOT = Path({str(self.root)!r})')
        app_path = self.root / 'audit_app.py'
        app_path.write_text(script)
        with patch.object(library_stats, 'WORK', self.work), patch.object(
                library_stats, 'EXPORTS', self.root / 'exports/approved'), patch('subprocess.run') as run:
            run.return_value.stdout = b'fake preview'
            app = AppTest.from_file(str(app_path)).run()
            self.assertFalse(app.exception)
            yield app, run
            self.assertFalse(app.exception)

    def click(self, app, label):
        next(b for b in app.button if b.label == label).click().run()
        self.assertFalse(app.exception)

    def exports(self, clip):
        folder = self.root / 'exports/approved/source'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / cr.key_for('source.MP4', clip)
        manifest = Path(str(target) + '.source.json')
        target.write_bytes(b'fake exported video')
        manifest.write_text(json.dumps({'start': 0, 'end': 10}))
        return target, manifest

    def assert_counts(self, app, approved, rejected, pending):
        labels = [b.label for b in app.button]
        for name, count in [('Approved', approved), ('Rejected', rejected), ('Pending', pending)]:
            self.assertIn(f'{name}: {count}', labels)

    def test_undo_preserves_all_fields_after_auto_navigation(self):
        for decision in ('✅ Approve', '❌ Reject'):
            with self.subTest(decision=decision):
                self.path.write_text('{}')
                with self.ui() as (app, _):
                    app.number_input[0].set_value(1.0).run()
                    app.number_input[1].set_value(9.0).run()
                    app.text_input[0].set_value('Edited title').run()
                    for label, value in [('Description', 'Edited description'),
                                         ('Keywords', 'drone, test'), ('Review notes', 'Keep this note')]:
                        next(x for x in app.text_area if x.label == label).set_value(value).run()
                    self.click(app, decision)
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 1)
                    self.click(app, '↶ Undo')
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 0)
                    self.assertEqual(self.status('auto_01'), 'pending')
                    self.assertEqual(self.status('auto_02'), 'pending')
                    self.assertEqual([x.value for x in app.number_input], [1.0, 9.0])
                    self.assertEqual(app.text_input[0].value, 'Edited title')
                    self.assertEqual([x.value for x in app.text_area],
                                     ['Edited description', 'drone, test', 'Keep this note'])
                    # Preserve edits in persisted Pending data, not just transient widgets.
                    saved = cr.get_review(self.reviews(), 'source.MP4', 'auto_01')
                    self.assertEqual(saved['note'], 'Keep this note')
                    self.assertEqual(saved['start'], 1.0)
                    self.assert_counts(app, 0, 0, 2)
                    next(x for x in app.selectbox if x.label == 'Status').select('Pending').run()
                    self.assertEqual(len(next(s for s in app.selectbox if s.label == 'Clip').options), 2)

    def test_undo_revokes_only_affected_export(self):
        sibling = self.exports('auto_02')
        self.save('auto_02', 'approved')
        with self.ui() as (app, _):
            self.click(app, '✅ Approve')
            target = self.exports('auto_01')  # Simulate an explicit export after approval.
            self.click(app, '↶ Undo')
            self.assertTrue(all(not p.exists() for p in target))
            self.assertTrue(all(p.exists() for p in sibling))
            self.assertEqual(self.status('auto_02'), 'approved')
            self.assert_counts(app, 1, 0, 1)

    def test_reject_removes_only_selected_export(self):
        self.save('auto_01', 'approved')
        self.save('auto_02', 'approved')
        target, sibling = self.exports('auto_01'), self.exports('auto_02')
        with self.ui() as (app, _):
            next(x for x in app.selectbox if x.label == 'Status').select('Approved').run()
            self.click(app, '❌ Reject')
            self.assertTrue(all(not p.exists() for p in target))
            self.assertTrue(all(p.exists() for p in sibling))
            self.assertEqual(self.status('auto_02'), 'approved')
            self.assert_counts(app, 1, 1, 0)

    def test_preview_minimum_reset_and_candidate_edit_isolation(self):
        with self.ui() as (app, run):
            app.number_input[0].set_value(2.0).run()
            command = run.call_args.args[0]
            self.assertEqual(command[command.index('-ss') + 1], '2.0')
            self.assertEqual(command[command.index('-t') + 1], '8.0')
            app.number_input[1].set_value(3.0).run()
            self.assertEqual(app.number_input[1].value, 7.0)
            app.number_input[0].set_value(29.0).run()
            self.assertEqual(app.number_input[0].value, 2.0)
            self.click(app, 'Reset')
            self.assertEqual([x.value for x in app.number_input], [0.0, 10.0])
            app.text_input[0].set_value('Candidate one only').run()
            self.assertEqual(self.reviews(), {})
            self.assertNotIn('source_auto_02.mp4', self.reviews())
            self.assertEqual(self.status('auto_01'), 'pending')
            self.click(app, '▶')
            self.assertEqual(app.text_input[0].value, 'Title')

    def test_field_changes_and_navigation_do_not_persist_without_decision(self):
        for status, filter_name in [('pending', 'Pending'), ('approved', 'All')]:
            with self.subTest(status=status):
                self.path.write_text('{}')
                self.save('auto_01', status)
                before = self.path.read_bytes()
                with self.ui() as (app, _):
                    self.assertFalse(any('save edits' in b.label.lower() for b in app.button))
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    next(s for s in app.selectbox if s.label == 'Clip').select(0).run()
                    app.number_input[0].set_value(1.0).run()
                    app.number_input[1].set_value(9.0).run()
                    app.text_input[0].set_value('Uncommitted title').run()
                    for label in ('Description', 'Keywords', 'Review notes'):
                        next(x for x in app.text_area if x.label == label).set_value('Uncommitted text').run()
                    self.assertEqual(self.path.read_bytes(), before)
                    self.click(app, '▶')
                    self.assertEqual(self.path.read_bytes(), before)
                    self.assertEqual(app.session_state.get('decision_history', []), [])
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)

    def test_both_decisions_save_current_boundaries_and_all_metadata(self):
        for status, button in [('approved', '✅ Approve'), ('rejected', '❌ Reject')]:
            with self.subTest(status=status):
                self.path.write_text('{}')
                with self.ui() as (app, _):
                    app.number_input[0].set_value(1.0).run()
                    app.number_input[1].set_value(9.0).run()
                    app.text_input[0].set_value('Edited title').run()
                    for label, value in [('Description', 'Edited description'),
                                         ('Keywords', 'drone, test'), ('Review notes', 'Edited note')]:
                        next(x for x in app.text_area if x.label == label).set_value(value).run()
                    self.assertEqual(self.reviews(), {})
                    self.click(app, button)
                    self.assertEqual(self.reviews(), {'source_auto_01.mp4': {
                        'status': status, 'start': 1.0, 'end': 9.0,
                        'title': 'Edited title', 'description': 'Edited description',
                        'keywords': 'drone, test', 'note': 'Edited note'}})
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, 'Pending')

    def test_reset_stays_in_editor_until_approve_or_reject(self):
        for status, button in [('approved', '✅ Approve'), ('rejected', '❌ Reject')]:
            with self.subTest(status=status):
                self.path.write_text('{}')
                cr.save_review(self.path, 'source.MP4', 'auto_01',
                               {'status': 'pending', 'start': 1.0, 'end': 9.0})
                before = self.path.read_bytes()
                candidates_before = (self.folder / 'clip_candidates.json').read_bytes()
                with self.ui() as (app, _):
                    self.assertEqual([x.value for x in app.number_input], [1.0, 9.0])
                    self.click(app, 'Reset')
                    self.assertEqual([x.value for x in app.number_input], [0.0, 10.0])
                    self.assertEqual(self.path.read_bytes(), before)
                    self.click(app, button)
                    saved = self.reviews()['source_auto_01.mp4']
                    self.assertEqual((saved['status'], saved['start'], saved['end']), (status, 0.0, 10.0))
                    self.assertNotIn('source_auto_02.mp4', self.reviews())
                    self.assertEqual((self.folder / 'clip_candidates.json').read_bytes(), candidates_before)
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, 'Pending')

    def test_selected_persisted_decision_returns_to_pending_without_history(self):
        for status, filter_name in [('approved', 'Approved'), ('rejected', 'Rejected')]:
            with self.subTest(status=status):
                saved = {'status': status, 'start': 1.0, 'end': 8.0,
                         'title': 'Saved title', 'description': 'Saved description',
                         'keywords': 'drone, saved', 'note': 'Saved note'}
                cr.save_review(self.path, 'source.MP4', 'auto_01', saved)
                self.save('auto_02', 'approved')
                sibling_review = self.reviews()['source_auto_02.mp4'].copy()
                target = self.exports('auto_01')
                sibling = self.exports('auto_02')
                with self.ui() as (app, _):
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    self.assertFalse(next(b for b in app.button if b.label == '↶ Undo').disabled)
                    self.click(app, '↶ Undo')
                    expected = dict(saved, status='pending')
                    self.assertEqual(self.reviews()['source_auto_01.mp4'], expected)
                    self.assertEqual(self.reviews()['source_auto_02.mp4'], sibling_review)
                    self.assertTrue(all(not p.exists() for p in target))
                    self.assertTrue(all(p.exists() for p in sibling))
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)
                    next(s for s in app.selectbox if s.label == 'Status').select('Pending').run()
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 0)
                    self.assertIn('Pending', next(s for s in app.selectbox if s.label == 'Clip').options[0])
                    self.assert_counts(app, 1, 0, 1)

    def test_selected_decision_takes_precedence_over_other_candidate_history(self):
        self.save('auto_02', 'approved')
        with self.ui() as (app, _):
            self.click(app, '❌ Reject')
            # Explicitly select another persisted decision after auto-navigation.
            next(s for s in app.selectbox if s.label == 'Status').select('Approved').run()
            app.text_input[0].set_value('Unsaved selected title').run()
            self.click(app, '↶ Undo')
            self.assertEqual(self.status('auto_01'), 'rejected')
            self.assertEqual(self.status('auto_02'), 'pending')
            self.assertEqual(self.reviews()['source_auto_02.mp4']['title'], 'Unsaved selected title')
            self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, 'Approved')
            self.assertTrue(next(s for s in app.selectbox if s.label == 'Clip').disabled)
            next(s for s in app.selectbox if s.label == 'Status').select('Pending').run()
            self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 1)

    def test_undo_filtered_selection_continues_forward_wraps_and_shows_empty(self):
        for status, filter_name in [('approved', 'Approved'), ('rejected', 'Rejected')]:
            with self.subTest(status=status):
                data = dict(self.data, clips=self.data['clips'] + [
                    {'id': 'auto_03', 'start': 20, 'end': 30}])
                (self.folder / 'clip_candidates.json').write_text(json.dumps(data))
                self.path.write_text('{}')
                for clip in data['clips']:
                    cr.save_review(self.path, 'source.MP4', clip['id'],
                                   {'status': status, 'title': clip['id']})
                with self.ui() as (app, _):
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    next(s for s in app.selectbox if s.label == 'Clip').select(1).run()
                    for expected in (2, 0, None):
                        self.click(app, '↶ Undo')
                        self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)
                        dropdown = next(s for s in app.selectbox if s.label == 'Clip')
                        self.assertEqual(dropdown.value, expected)
                        if expected is not None:
                            self.assertEqual(app.text_input[0].value, data['clips'][expected]['id'])
                            self.assertTrue(all(filter_name in option for option in dropdown.options))
                        else:
                            self.assertTrue(dropdown.disabled)
                            self.assertEqual(dropdown.options, [])
                            self.assertTrue(any('No clips match' in message.value for message in app.info))
                            for label in ('◀', '▶'):
                                self.assertTrue(next(b for b in app.button if b.label == label).disabled)
                    self.assert_counts(app, 0, 0, 3)
                    next(s for s in app.selectbox if s.label == 'Status').select('Pending').run()
                    self.assertEqual(len(next(s for s in app.selectbox if s.label == 'Clip').options), 3)

    def test_undo_keeps_pending_or_all_and_returns_to_candidate(self):
        for filter_name in ('Pending', 'All'):
            with self.subTest(filter_name=filter_name):
                self.path.write_text('{}')
                with self.ui() as (app, _):
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    self.click(app, '✅ Approve')
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 1)
                    self.click(app, '↶ Undo')
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 0)
                    self.assertEqual(self.status('auto_01'), 'pending')
                    self.assert_counts(app, 0, 0, 2)

    def test_empty_pending_filter_retains_undo_history(self):
        self.save('auto_02', 'rejected')
        with self.ui() as (app, _):
            self.click(app, '✅ Approve')
            self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, 'Pending')
            self.assertTrue(next(s for s in app.selectbox if s.label == 'Clip').disabled)
            self.assertFalse(next(b for b in app.button if b.label == '↶ Undo').disabled)
            self.click(app, '↶ Undo')
            self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, 'Pending')
            self.assertEqual(next(s for s in app.selectbox if s.label == 'Clip').value, 0)
            self.assertEqual(self.status('auto_02'), 'rejected')
            self.assert_counts(app, 0, 1, 1)

    def test_fractional_duration_normalizes_loaded_candidates_and_reviews(self):
        cases = [(116.817, 111.82, 116.82), (116.817, -0.02, 116.817),
                 (116.817, 200.0, 300.0), (116.817, 116.82, 1.0),
                 (5.001, 0.01, 5.01), (5.0, -1.0, 4.99)]
        for duration, start, end in cases:
            for origin in ('candidate', 'review'):
                with self.subTest(duration=duration, start=start, end=end, origin=origin):
                    data = dict(self.data, duration=duration, clips=[
                        dict(self.data['clips'][0], start=start, end=end)] + self.data['clips'][1:])
                    candidates = self.folder / 'clip_candidates.json'
                    candidates.write_text(json.dumps(data))
                    self.path.write_text('{}')
                    if origin == 'review':
                        cr.save_review(self.path, 'source.MP4', 'auto_01',
                                       {'status': 'pending', 'start': start, 'end': end})
                    before = self.path.read_bytes(), candidates.read_bytes()
                    # Each subcase must exercise preview generation, not its cache.
                    import streamlit as st
                    st.cache_data.clear()
                    with self.ui() as (app, run):
                        a, b = [x.value for x in app.number_input]
                        for widget in app.number_input:
                            self.assertLessEqual(widget.min, widget.value)
                            self.assertLessEqual(widget.value, widget.max)
                        self.assertGreaterEqual(a, 0)
                        self.assertGreaterEqual(b - a, 5.0 - 1e-9)
                        self.assertLessEqual(b, duration)
                        command = run.call_args.args[0]
                        preview_start = float(command[command.index('-ss') + 1])
                        preview_length = float(command[command.index('-t') + 1])
                        self.assertLessEqual(preview_start + preview_length, duration)
                        self.assertEqual((self.path.read_bytes(), candidates.read_bytes()), before)

    def test_fractional_duration_edit_reset_decision_and_undo(self):
        for label in ('✅ Approve', '❌ Reject'):
            with self.subTest(decision=label):
                data = dict(self.data, duration=116.817, clips=[
                    dict(self.data['clips'][0], start=111.82, end=116.82)] + self.data['clips'][1:])
                candidates = self.folder / 'clip_candidates.json'
                candidates.write_text(json.dumps(data))
                self.path.write_text('{}')
                before = candidates.read_bytes()
                with self.ui() as (app, _):
                    self.assertEqual([x.value for x in app.number_input], [111.81, 116.81])
                    self.assertEqual(app.number_input[1].max, 116.81)
                    app.number_input[0].set_value(115.0).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.number_input[0].value, 111.81)
                    app.number_input[1].set_value(116.82).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.number_input[1].value, 116.81)
                    app.number_input[0].set_value(100.0).run()
                    self.click(app, 'Reset')
                    self.assertEqual([x.value for x in app.number_input], [111.81, 116.81])
                    self.assertEqual(self.reviews(), {})
                    self.click(app, label)
                    saved = self.reviews()['source_auto_01.mp4']
                    self.assertEqual((saved['start'], saved['end']), (111.81, 116.81))
                    self.click(app, '↶ Undo')
                    self.assertEqual([x.value for x in app.number_input], [111.81, 116.81])
                    self.assertEqual(self.status('auto_01'), 'pending')
                    self.assertEqual(candidates.read_bytes(), before)

    def test_export_rejects_end_beyond_actual_duration_without_encoding(self):
        data = dict(self.data, duration=116.817)
        (self.folder / 'clip_candidates.json').write_text(json.dumps(data))
        cr.save_review(self.path, 'source.MP4', 'auto_01',
                       {'status': 'approved', 'start': 100.0, 'end': 116.818})
        with patch.object(export_approved, 'WORK', self.work), patch.object(
                export_approved, 'ORIGINALS', self.root / 'originals'), patch.object(
                export_approved, 'DEST', self.root / 'exports/approved'), patch.object(
                export_approved.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Invalid boundaries'):
                export_approved.export('source')
            run.assert_not_called()

    def navigation_source(self, folder_name, source_name, ids, decisions):
        folder = self.work / folder_name
        folder.mkdir(exist_ok=True)
        clips = [{'id': clip_id, 'start': i * 10, 'end': i * 10 + 10}
                 for i, clip_id in enumerate(ids)]
        (folder / 'clip_candidates.json').write_text(json.dumps(
            {'source': source_name, 'duration': 120, 'clips': clips}))
        (folder / 'reviews.json').write_text(json.dumps({
            cr.key_for(source_name, clip_id): {'status': status, 'note': 'Existing decision'}
            for clip_id, status in decisions.items()}))
        (self.root / 'originals' / source_name).write_bytes(b'fake original')
        (folder / 'stock_metadata').mkdir(exist_ok=True)
        for clip_id in ids:
            (folder / 'stock_metadata' / (clip_id + '.json')).write_text(json.dumps(
                {'metadata': {'title': source_name + ':' + clip_id,
                              'description': 'Description', 'keywords': ['drone']}}))
        return folder

    def assert_selected_candidate(self, app, index, source, clip_id, filter_name):
        dropdown = next(s for s in app.selectbox if s.label == 'Clip')
        self.assertEqual(dropdown.value, index)
        self.assertEqual(app.session_state['queue_index'], index)
        self.assertEqual(app.session_state['queue_selection'], index)
        self.assertEqual(app.text_input[0].value, source + ':' + clip_id)
        self.assertTrue(any(source in c.value and clip_id in c.value for c in app.caption))
        self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)

    def test_decisions_prioritize_same_source_in_natural_order_then_next_pending_source(self):
        for filter_name in ('Pending', 'All'):
            with self.subTest(filter_name=filter_name):
                self.navigation_source('source', 'source.MP4',
                    ['auto_10', 'auto_03', 'auto_01', 'auto_04', 'auto_02'],
                    {'auto_02': 'approved', 'auto_04': 'rejected'})
                skipped = self.navigation_source('source_b', 'second.MP4', ['auto_01'], {'auto_01': 'approved'})
                next_source = self.navigation_source('source_c', 'third.MP4', ['auto_02', 'auto_01'], {})
                untouched = {p: p.read_bytes() for p in self.work.rglob('*.json')
                             if p.name != 'reviews.json'}
                other_reviews = {p: p.read_bytes() for p in
                                 (skipped / 'reviews.json', next_source / 'reviews.json')}
                with self.ui() as (app, _):
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    dropdown = next(s for s in app.selectbox if s.label == 'Clip')
                    if filter_name == 'All':
                        self.assertEqual([o.split(' · ')[2] for o in dropdown.options[:5]],
                                         ['auto_01', 'auto_02', 'auto_03', 'auto_04', 'auto_10'])
                    dropdown.select(2).run()  # Start midway through the current source.
                    self.click(app, '✅ Approve')
                    self.assert_selected_candidate(app, 4, 'source.MP4', 'auto_10', filter_name)
                    app.run()
                    self.assert_selected_candidate(app, 4, 'source.MP4', 'auto_10', filter_name)
                    self.click(app, '❌ Reject')
                    self.assert_selected_candidate(app, 0, 'source.MP4', 'auto_01', filter_name)
                    self.click(app, '✅ Approve')
                    self.assert_selected_candidate(app, 6, 'third.MP4', 'auto_01', filter_name)
                    for clip_id, status in [('auto_01', 'approved'), ('auto_02', 'approved'),
                                            ('auto_03', 'approved'), ('auto_04', 'rejected'),
                                            ('auto_10', 'rejected')]:
                        self.assertEqual(self.status(clip_id), status)
                    before_navigation = self.path.read_bytes()
                    self.click(app, '▶')
                    self.assert_selected_candidate(app, 7, 'third.MP4', 'auto_02', filter_name)
                    self.assertEqual(self.path.read_bytes(), before_navigation)
                for p, contents in {**untouched, **other_reviews}.items():
                    self.assertEqual(p.read_bytes(), contents)

    def test_decisions_respect_approved_rejected_filters_and_empty_state(self):
        for status, filter_name, same_button, opposite in (
                ('approved', 'Approved', '✅ Approve', '❌ Reject'),
                ('rejected', 'Rejected', '❌ Reject', '✅ Approve')):
            with self.subTest(filter_name=filter_name):
                self.navigation_source('source', 'source.MP4',
                    ['auto_04', 'auto_02', 'auto_01', 'auto_03'],
                    {'auto_01': status, 'auto_02': status})
                other = self.navigation_source('source_b', 'second.MP4',
                    ['auto_02', 'auto_01'], {'auto_01': status})
                with self.ui() as (app, _):
                    next(s for s in app.selectbox if s.label == 'Status').select(filter_name).run()
                    next(s for s in app.selectbox if s.label == 'Clip').select(0).run()
                    self.click(app, same_button)
                    self.assert_selected_candidate(app, 1, 'source.MP4', 'auto_02', filter_name)
                    self.click(app, opposite)
                    self.assert_selected_candidate(app, 4, 'second.MP4', 'auto_01', filter_name)
                    self.click(app, opposite)
                    self.assert_selected_candidate(app, 0, 'source.MP4', 'auto_01', filter_name)
                    self.click(app, opposite)
                    self.assertEqual(next(s for s in app.selectbox if s.label == 'Status').value, filter_name)
                    self.assertTrue(next(s for s in app.selectbox if s.label == 'Clip').disabled)
                    self.assertTrue(any('No clips match' in m.value for m in app.info))
                    self.assertEqual(self.status('auto_03'), 'pending')
                    self.assertEqual(self.status('auto_04'), 'pending')
                    other_reviews = json.loads((other / 'reviews.json').read_text())
                    self.assertNotIn('second_auto_02.mp4', other_reviews)
                    self.assertEqual(other_reviews['second_auto_01.mp4']['note'], 'Existing decision')

    def test_undo_keeps_legacy_status_and_latest_edits(self):
        self.path.write_text(json.dumps({'auto_01': {'status': 'approved', 'note': 'Old note'}}))
        action = self.save('auto_01', 'rejected')
        cr.save_review(self.path, 'source.MP4', 'auto_01', {'status': 'rejected', 'note': 'Latest note'})
        self.save('auto_02', 'approved')
        cr.undo_review(self.path, action, preserve_edits=True)
        self.assertEqual(self.status('auto_01'), 'approved')
        self.assertEqual(cr.get_review(self.reviews(), 'source.MP4', 'auto_01')['note'], 'Latest note')
        self.assertEqual(self.status('auto_02'), 'approved')

    def test_undo_returns_to_identity_after_queue_insertion(self):
        with self.ui() as (app, _):
            self.click(app, '✅ Approve')
            # Simulate a library refresh in temporary data while auto-navigated.
            data = dict(self.data, clips=[{'id': 'auto_00', 'start': 20, 'end': 30}] + self.data['clips'])
            (self.folder / 'clip_candidates.json').write_text(json.dumps(data))
            self.click(app, '↶ Undo')
            selected = next(s for s in app.selectbox if s.label == 'Clip')
            self.assertEqual(selected.value, 1)
            self.assertIn('auto_01', selected.options[1])
            self.assertEqual(self.status('auto_01'), 'pending')

    def test_approved_edits_are_outdated_until_explicit_export(self):
        self.save('auto_01', 'approved')
        commands = []
        def fake_run(command, **kwargs):
            commands.append(command)
            if command[0] == 'ffmpeg':
                Path(command[-1]).write_bytes(b'fake export')
        with patch.object(export_approved, 'WORK', self.work), patch.object(
                export_approved, 'ORIGINALS', self.root / 'originals'), patch.object(
                export_approved, 'DEST', self.root / 'exports/approved'), patch.object(
                export_approved.subprocess, 'run', side_effect=fake_run), patch.object(
                library_stats, 'WORK', self.work), patch.object(
                library_stats, 'EXPORTS', self.root / 'exports/approved'):
            self.assertEqual(library_stats.get_library_stats()[0]['needs_export'], 1)
            export_approved.export('source')
            self.assertEqual(library_stats.get_library_stats()[0]['exported'], 1)
            target = self.root / 'exports/approved/source/source_auto_01.mp4'
            before = target.stat().st_mtime_ns
            cr.save_review(self.path, 'source.MP4', 'auto_01', {'status': 'approved', 'title': 'New title'})
            self.assertEqual(library_stats.get_library_stats()[0]['outdated'], 1)
            self.assertEqual(target.stat().st_mtime_ns, before)
            export_approved.export('source')
            self.assertEqual(library_stats.get_library_stats()[0]['exported'], 1)
            self.assertEqual(sum(c[0] == 'ffmpeg' for c in commands), 1)
            cr.save_review(self.path, 'source.MP4', 'auto_01', {'status': 'approved', 'start': 1, 'end': 9})
            self.assertEqual(library_stats.get_library_stats()[0]['outdated'], 1)
            export_approved.export('source')
            self.assertEqual(library_stats.get_library_stats()[0]['exported'], 1)
            self.assertEqual(sum(c[0] == 'ffmpeg' for c in commands), 2)


if __name__ == '__main__':
    unittest.main()
