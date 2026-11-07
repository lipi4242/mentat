"""The month-end rule matches the worker's (series.json = its test table)."""
import json
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cases_cli"))
import recurrence as rec  # noqa: E402

TABLE = json.loads((HERE / "series.json").read_text())


class TestSeries(unittest.TestCase):
    def test_first_dates_match_the_worker(self):
        for row in TABLE["first"]:
            got = [rec.nth(row["anchor"], row["rule"], k) for k in range(len(row["dates"]))]
            self.assertEqual(got, row["dates"], row)

    def test_anchor_check_matches_the_worker(self):
        for anchor, rule, ok in TABLE["anchor_ok"]:
            self.assertEqual(rec.anchor_ok(anchor, rule), ok, (anchor, rule))

    def test_rule_set(self):
        for s in TABLE["accept"]:
            self.assertIsNotNone(rec.parse(s), s)
        for s in TABLE["reject"]:
            self.assertIsNone(rec.parse(s), s)

    def test_open_window(self):
        self.assertEqual(rec.first_open_after("2027-01-31", "monthly:31", "2027-01-31"), "2027-02-28")
        self.assertEqual(rec.between("2026-08-10", "monthly:10", "2026-09-01", "2026-11-10"),
                         ["2026-09-10", "2026-10-10", "2026-11-10"])


if __name__ == "__main__":
    unittest.main()
