"""Precision, boundary and safety regressions for review trim edits."""
import unittest

from trim_bounds import adjust_trim_end, editor_duration, normalize_trim, valid_trim


class TrimBoundaryTests(unittest.TestCase):
    def test_editor_duration_rounds_inward_not_past_media(self):
        self.assertEqual(editor_duration(116.817), 116.81)
        self.assertEqual(editor_duration(5.009), 5.0)

    def test_normalization_clamps_to_source_and_five_second_minimum(self):
        for start, end, duration in (
            (-10, 2, 10), (9, 20, 10), (4, 4, 10),
            (0, 100, 10), (2.345, 7.345, 10),
        ):
            with self.subTest(start=start, end=end, duration=duration):
                a, b = normalize_trim(start, end, duration)
                self.assertTrue(valid_trim(a, b, duration))
                self.assertLessEqual(b, editor_duration(duration))

    def test_source_shorter_than_five_seconds_is_rejected(self):
        for duration in (0, 4.99, 4.999):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    normalize_trim(0, duration, duration)

    def test_end_adjustment_never_moves_start_or_exceeds_source(self):
        self.assertEqual(adjust_trim_end(2, 8, 10, 100), 10)
        self.assertEqual(adjust_trim_end(2, 8, 10, -100), 7)
        self.assertEqual(adjust_trim_end(0, 5, 5.009, 1), 5)

    def test_valid_trim_rejects_nonfinite_negative_or_too_short_values(self):
        for start, end, duration in (
            (float("nan"), 6, 10), (0, float("inf"), 10),
            (-1, 6, 10), (0, 4.99, 10), (6, 5, 10),
            (0, 11, 10),
        ):
            with self.subTest(start=start, end=end, duration=duration):
                self.assertFalse(valid_trim(start, end, duration))


if __name__ == "__main__":
    unittest.main()
