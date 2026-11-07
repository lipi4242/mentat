"""A first month with its own date stays in the series (mérés 11).

Gas from now on by the 10th, but October's 10th has passed: October is due on
the 20th. `add --recurrence monthly:10 --due 2026-10-20` keeps October as the
series' first occurrence (anchor 2026-10-10, due_at 2026-10-20) instead of a
separate one-off case, so "befizettem" closes the series' October.
"""
import json
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import Repo

GAS_20 = ("---\ntype: case\ncase_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RX\ntitle: Gázszámla\nstatus: open\n"
          "recurrence: monthly:20\nanchor_at: 2026-10-20\ndue_at: 2026-10-20\n---\n\nÁtutalással.\n")


class FirstMonth:
    def add(self):
        c = self.js("add", "--title", "Gázszámla", "--recurrence", "monthly:10", "--due", "2026-10-20")
        self.assertEqual((c["anchor_at"], c["due_at"], c["recurrence"]), ("2026-10-10", "2026-10-20", "monthly:10"))
        return c["id"]

    def closed(self, cid):
        return [o["due_at"] for o in self.js("show", cid)["occurrences"]]

    def test_the_moved_october_is_due_on_the_20th(self):
        cid = self.add()
        self.assertNotIn(cid, [i["case_id"] for i in self.js("due", "--until", "2026-10-19")])
        items = [(i["due_at"], i["closable"]) for i in self.js("due", "--until", "2026-11-10") if i["case_id"] == cid]
        self.assertEqual(items, [("2026-10-20", True), ("2026-11-10", False)])

    def test_befizettem_closes_the_series_october_once(self):
        cid = self.add()
        self.assertIn("next due 2026-11-10", self.cli("close", cid).stdout)
        self.assertEqual(self.closed(cid), ["2026-10-10"])
        for day in ("2026-10-20", "2026-10-10"):
            self.assertIn("already closed", self.cli("close", cid, "--occurrence", day).stdout)
        self.assertEqual(self.closed(cid), ["2026-10-10"])
        self.assertEqual(self.js("show", cid)["due_at"], "2026-11-10")

    def test_a_later_month_waits_for_the_moved_october(self):
        cid = self.add()
        p = self.cli("close", cid, "--occurrence", "2026-12-10", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("2026-10-20", p.stderr)
        self.assertEqual(self.closed(cid), [])

    def test_the_moved_date_stays_inside_its_month(self):
        p = self.cli("add", "--title", "Gáz", "--recurrence", "monthly:10", "--due", "2026-10-20",
                     "--anchor", "2026-09-10", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("2026-10-10", p.stderr)


class TestFirstMonthMarkdown(FirstMonth, Repo):
    files = {"gaz20.md": GAS_20}

    def test_frontmatter_keeps_the_series(self):
        self.add()
        text = self.text("gazszamla.md")
        for line in ("recurrence: monthly:10", "anchor_at: 2026-10-10", "due_at: 2026-10-20"):
            self.assertIn(line, text)

    def test_update_turns_monthly_20_into_monthly_10_with_october_on_the_20th(self):
        c = self.js("update", "01JAB6Z9Q3M8K7T2V5W4X1Y0RX", "--recurrence", "monthly:10", "--due", "2026-10-20")
        self.assertEqual((c["anchor_at"], c["due_at"]), ("2026-10-10", "2026-10-20"))
        self.cli("close", "01JAB6Z9Q3M8K7T2V5W4X1Y0RX")
        self.assertEqual(self.closed("01JAB6Z9Q3M8K7T2V5W4X1Y0RX"), ["2026-10-10"])


class TestFirstMonthAdmin(FirstMonth, Repo):
    backend = "admin"
    with_admin = True
    files = {}

    def test_the_admin_record_is_one_series(self):
        cid = self.add()
        self.cli("close", cid)
        row = self.store.detail(cid)
        self.assertEqual(json.loads(json.dumps([o["due_at"] for o in row["occurrences"]])), ["2026-10-10"])
        self.assertEqual((row["anchor_at"], row["due_at"]), ("2026-10-10", "2026-11-10"))


if __name__ == "__main__":
    unittest.main()
