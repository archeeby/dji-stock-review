import copy
import json
import unittest
from pathlib import Path

from stock.platforms import PLATFORMS, make_row

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "platform_records.json"
)


class PlatformAdapterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(
            FIXTURE.read_text(encoding="utf-8")
        )

    def test_valid_record_generates_csv_row(self):
        record = self.fixtures["valid"]

        expected_fields = {
            "pond5": {
                "OriginalFilename",
                "name",
                "Description",
                "Keywords",
                "City",
                "Region",
                "Country",
                "Created",
            },
            "adobe": {
                "Filename",
                "Title",
                "Keywords",
                "Category",
            },
            "shutterstock": {
                "Filename",
                "Description",
                "Keywords",
                "Categories",
                "Illustration",
                "Mature Content",
                "Editorial",
            },
        }

        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                row, filename, reason = make_row(
                    platform, record, {}
                )

                self.assertIsNone(reason)
                self.assertIsNotNone(row)
                self.assertEqual(
                    set(row),
                    expected_fields[platform],
                )
                self.assertTrue(filename.endswith(".mp4"))
                self.assertIn("coast", row["Keywords"])
                self.assertIn("drone", row["Keywords"])

    def test_insufficient_keywords_are_rejected(self):
        record = self.fixtures["insufficient_keywords"]

        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                row, filename, reason = make_row(
                    platform, record, {}
                )

                self.assertIsNone(row)
                self.assertIsNone(filename)
                self.assertEqual(
                    reason,
                    "fewer than 7 keywords",
                )

    def test_pond5_rejects_long_title(self):
        record = copy.deepcopy(self.fixtures["valid"])
        record["review"]["title"] = "A" * 81

        row, filename, reason = make_row(
            "pond5", record, {}
        )

        self.assertIsNone(row)
        self.assertIsNone(filename)
        self.assertEqual(
            reason,
            "Pond5 title/description exceeds conservative limits",
        )

    def test_unknown_platform_is_rejected(self):
        with self.assertRaises(ValueError):
            make_row(
                "unknown",
                self.fixtures["valid"],
                {},
            )


if __name__ == "__main__":
    unittest.main()
