import unittest
from trim_bounds import adjust_trim_end, normalize_trim, valid_trim


class TrimDurationControlsTests(unittest.TestCase):
    def test_extend_preserves_start_and_changes_end(self):
        self.assertEqual(adjust_trim_end(10, 20, 60, 1), 21)

    def test_shorten_preserves_start_and_changes_end(self):
        self.assertEqual(adjust_trim_end(10, 20, 60, -1), 19)

    def test_minimum_five_seconds(self):
        self.assertEqual(adjust_trim_end(10, 15, 60, -1), 15)
        self.assertTrue(valid_trim(10, 15, 60))

    def test_source_end_clamped_inward(self):
        self.assertEqual(adjust_trim_end(10, 19, 19.997, 1), 19.99)

    def test_repeat_clicks(self):
        end = 20
        for _ in range(4):
            end = adjust_trim_end(10, end, 60, -1)
        self.assertEqual(end, 16)

    def test_reset_restores_ai_bounds(self):
        original = normalize_trim(8.5, 25.5, 60)
        changed_end = adjust_trim_end(*original, 60, -1)
        self.assertNotEqual(changed_end, original[1])
        self.assertEqual(normalize_trim(8.5, 25.5, 60), original)


if __name__ == "__main__":
    unittest.main()
