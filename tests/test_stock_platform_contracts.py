"""Stock-platform adapter contract tests; no real library or network access."""
import unittest

from stock.platforms import PLATFORMS, make_row
from stock.platforms import adobe, pond5, shutterstock
from stock.records import clean_keywords


class StockPlatformContractTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "filename": "DJI_coast_auto_01.mp4",
            "review": {
                "title": "Croatia coast, boats at sunset",
                "description": "Aerial travel footage of boats along the coast.",
                "keywords": "Croatia, coast, sea, boats, sunset, travel, aerial, drone",
            },
            "location": {"city": "Split", "region": "Dalmatia", "country": "Croatia"},
            "created": "2025-06-01",
        }

    def test_all_platform_rows_match_declared_column_contracts(self):
        columns = {"adobe": adobe.COLUMNS, "pond5": pond5.COLUMNS,
                   "shutterstock": shutterstock.COLUMNS}
        self.assertEqual(set(PLATFORMS), set(columns))
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                row, name, reason = make_row(platform, self.record)
                self.assertIsNone(reason)
                self.assertEqual(set(row), set(columns[platform]))
                self.assertTrue(name.endswith(".mp4"))
                self.assertTrue(all(isinstance(value, str) for value in row.values()))

    def test_keyword_normalization_deduplicates_case_and_caps_at_fifty(self):
        values = [" Coast ", "coast", "", "SEA", "sea"] + [
            f"keyword{i}" for i in range(60)
        ]
        result = clean_keywords(values)
        self.assertEqual(result[:2], ["Coast", "SEA"])
        self.assertEqual(len(result), 50)
        self.assertEqual(len({x.casefold() for x in result}), len(result))

    def test_all_adapters_reject_insufficient_keywords(self):
        record = dict(self.record)
        record["review"] = dict(self.record["review"], keywords="sea, coast")
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                row, filename, reason = make_row(platform, record)
                self.assertIsNone(row)
                self.assertIsNone(filename)
                self.assertIn("fewer than 7", reason)

    def test_adobe_filename_is_stable_bounded_and_collision_resistant(self):
        long_name = "very_long_drone_source_filename_with_a_unique_suffix_auto_01.mp4"
        other = "very_long_drone_source_filename_with_a_unique_suffix_auto_02.mp4"
        a = adobe.destination_name(long_name)
        self.assertEqual(a, adobe.destination_name(long_name))
        self.assertLessEqual(len(a), 30)
        self.assertTrue(a.endswith(".mp4"))
        self.assertNotEqual(a, adobe.destination_name(other))

    def test_pond5_rejects_overlong_title_and_description(self):
        for key, value in (("title", "T" * 81), ("description", "D" * 501)):
            with self.subTest(field=key):
                record = dict(self.record)
                record["review"] = dict(self.record["review"], **{key: value})
                row, filename, reason = make_row("pond5", record)
                self.assertIsNone(row)
                self.assertIsNone(filename)
                self.assertIn("exceeds", reason)

    def test_shutterstock_override_validation_and_precedence(self):
        filename = self.record["filename"]
        for invalid in ([], ["Nature", "Travel", "Other"], [""], 42):
            with self.subTest(override=invalid):
                row, _, reason = make_row("shutterstock", self.record,
                                          {filename: invalid})
                self.assertIsNone(row)
                self.assertEqual(reason, "invalid category override")
        row, _, reason = make_row("shutterstock", self.record,
                                  {filename: ["Sports", "Travel"]})
        self.assertIsNone(reason)
        self.assertEqual(row["Categories"], "Sports, Travel")

    def test_shutterstock_requires_category_or_manual_override(self):
        record = dict(self.record)
        record["review"] = {
            "title": "Abstract textures",
            "description": "Geometric patterns.",
            "keywords": "abstract, geometric, pattern, texture, detail, closeup, shapes",
        }
        row, _, reason = make_row("shutterstock", record)
        self.assertIsNone(row)
        self.assertIn("no category suggestion", reason)
        row, _, reason = make_row("shutterstock", record,
                                  {record["filename"]: "Abstract"})
        self.assertIsNone(reason)
        self.assertEqual(row["Categories"], "Abstract")


if __name__ == "__main__":
    unittest.main()
