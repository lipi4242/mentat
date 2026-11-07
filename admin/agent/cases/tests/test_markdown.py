"""cases.backend: markdown — the frontmatter of <brain>/cases/*.md is the record."""
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import GAZ_ID, Repo

ADO_ID, KAR_ID, LAK_ID = "01JAB6Z9Q3M8K7T2V5W4X1Y0RT", "01JAB6Z9Q3M8K7T2V5W4X1Y0RV", "01JAB6Z9Q3M8K7T2V5W4X1Y0RW"


class TestRead(Repo):
    def test_list_is_cases_only_earliest_first(self):
        rows = self.js("list")
        self.assertEqual([r["title"] for r in rows], ["Lakbér", "Gázszámla", "Kárigény", "Adóbevallás"])
        self.assertEqual(rows[1]["brain_ref"], "agy/cases/gazszamla.md")

    def test_due_lists_every_open_month_and_only_the_first_is_closable(self):
        items = [(i["title"], i["due_at"], i["closable"]) for i in self.js("due", "--days", "7")]
        self.assertEqual(items, [("Lakbér", "2026-08-31", True), ("Lakbér", "2026-09-30", False),
                                 ("Gázszámla", "2026-10-10", True), ("Kárigény", "2026-10-20", True)])

    def test_show_has_fields_history_and_context(self):
        one = self.js("show", GAZ_ID)
        self.assertEqual(one["occurrences"][0]["due_at"], "2026-09-10")
        self.assertEqual(one["open_occurrences"], ["2026-10-10"])
        self.assertIn("12 400 Ft", one["context"])
        self.assertIn("Gázszámla", self.cli("show", GAZ_ID).stdout)


class TestWrite(Repo):
    def test_close_moves_to_next_month_and_keeps_the_rest_of_the_file(self):
        self.cli("close", GAZ_ID, "--note", "átutalva")
        self.assertEqual(self.js("show", GAZ_ID)["due_at"], "2026-11-10")
        text = self.text("gazszamla.md")
        self.assertIn("tags: [háztartás, pénzügy]", text)
        self.assertIn("**Számítás:** 12 400 Ft átalány.", text)
        before = text
        p = self.cli("close", GAZ_ID, "--occurrence", "2026-10-10")
        self.assertIn("already closed", p.stdout)
        self.assertEqual(self.text("gazszamla.md"), before)

    def test_a_later_month_cannot_be_closed_before_an_earlier_one(self):
        p = self.cli("close", LAK_ID, "--occurrence", "2026-09-30", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("2026-08-31", p.stderr)
        self.assertEqual(self.js("show", LAK_ID)["due_at"], "2026-08-31")

    def test_quarterly_vat_closes_quarter_by_quarter(self):
        vat = self.js("create", "--title", "ÁFA-bevallás", "--recurrence", "quarterly:20", "--anchor", "2026-07-20")
        self.assertEqual(vat["due_at"], "2026-07-20")
        due = [(i["due_at"], i["closable"]) for i in self.js("due", "--until", "2027-01-31") if i["case_id"] == vat["id"]]
        self.assertEqual(due, [("2026-07-20", True), ("2026-10-20", False), ("2027-01-20", False)])
        p = self.cli("close", vat["id"], "--occurrence", "2026-10-20", ok=False)
        self.assertIn("2026-07-20", p.stderr)
        self.cli("close", vat["id"])
        self.assertEqual(self.js("show", vat["id"])["due_at"], "2026-10-20")

    def test_close_one_off_sets_done(self):
        self.cli("close", ADO_ID)
        self.assertEqual(self.js("show", ADO_ID)["status"], "done")
        self.assertNotIn("Adóbevallás", [r["title"] for r in self.js("list")])

    def test_create_and_update(self):
        new = self.js("create", "--title", "Autó műszaki", "--due", "2026-12-01", "--next", "Időpontot kérni")
        self.assertRegex(new["id"], r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
        self.assertTrue(new["brain_ref"].startswith("agy/cases/"))
        self.cli("update", KAR_ID, "--status", "open", "--description", "Csőtörés a fürdőben")
        kar = self.js("show", KAR_ID)
        self.assertEqual((kar["status"], kar["description"]), ("open", "Csőtörés a fürdőben"))
        self.assertNotIn("waiting_on", kar)
        self.assertEqual(kar["extra"], {"waiting_on": "a biztosító"})
        self.assertIn("A csőtörés.", self.text("karigeny.md"))

    def test_create_from_an_existing_note_in_the_cases_folder(self):
        note = self.root / "agy" / "cases" / "auto.md"
        note.write_text("Műszaki: november.\n")
        new = self.js("create", "--file", str(note), "--title", "Autó", "--due", "2026-11-30")
        self.assertEqual(self.js("show", new["id"])["context"], "Műszaki: november.\n")
        elsewhere = self.root / "agy" / "jegyzet.md"
        elsewhere.write_text("x\n")
        p = self.cli("create", "--file", str(elsewhere), "--title", "X", "--due", "2026-11-30", ok=False)
        self.assertIn("agy/cases", p.stderr)
        self.assertEqual(elsewhere.read_text(), "x\n")

    def test_recurring_create_rejects_an_anchor_off_the_series(self):
        p = self.cli("create", "--title", "X", "--recurrence", "monthly:10", "--anchor", "2026-10-12", ok=False)
        self.assertIn("anchor", p.stderr)


if __name__ == "__main__":
    unittest.main()
