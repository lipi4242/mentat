"""mentat_accept.py: the contract's assertions run on the output BEFORE it goes out or is called done.

Class of error (holdout, 0.3.0): "it ran, HTTP 200" stood in for "the right people got the
right list". A morning list with the wrong names went out, invitations showed every guest to
every other guest, and excluded data came back in. Exit 0 green, 1 red, 2 cannot check.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import sys
import unittest

from _contract_fixture import GOOD_CSV, PROPOSAL, approved, brain, run, write

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_accept  # noqa: E402

TOOL = "mentat_accept.py"
HIDDEN_INVITE = {"to": [], "bcc": ["anna@example.com", "bob@example.com"], "visibility": "hidden"}


class Files(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        approved(self.root)

    def accept(self, text, name="out.csv"):
        return run(TOOL, self.root, "dinner", str(write(self.root, name, text)))

    def red(self, text, *expect, name="out.csv"):
        r = self.accept(text, name)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("RED", r.stdout)
        for e in expect:
            self.assertIn(e, r.stdout)
        return r

    def test_the_exact_list_is_green_and_says_what_would_go_out(self):
        r = self.accept(GOOD_CSV)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GREEN", r.stdout)
        self.assertIn("2 rows", r.stdout)

    def test_an_extra_column_is_red(self):
        self.red(GOOD_CSV.replace("date\n", "date,total\n", 1).replace("03\n", "03,1\n")
                 .replace("05\n", "05,1\n"), "total")

    def test_an_excluded_column_record_or_value_is_red(self):
        self.red("name,email,date,phone\nAnna,anna@example.com,2026-11-03,x\n"
                 "Bob,bob@example.com,2026-11-05,y\n", "phone")
        self.red(GOOD_CSV + "Péter,peter@example.com,2026-11-04\n", "peter@example.com")
        self.red(GOOD_CSV.replace("Bob,", "Bob (+36 1 333 3333),"), "+36 1 333")

    def test_a_missing_or_late_record_is_red(self):
        self.red("name,email,date\nAnna,anna@example.com,2026-11-03\n", "bob@example.com")
        self.red(GOOD_CSV + "Alice,alice@example.com,2026-11-12\n", "2026-11-12")

    def test_the_window_is_read_in_the_contract_timezone(self):
        # 23:30 UTC on the 8th is already the 9th in Budapest: outside the window
        self.red(GOOD_CSV.replace("2026-11-05", "2026-11-08T23:30:00Z"), "2026-11-08T23:30:00Z")

    def test_json_and_markdown_outputs(self):
        rows = [{"name": "Anna", "email": "anna@example.com", "date": "2026-11-03"},
                {"name": "Bob", "email": "bob@example.com", "date": "2026-11-05"}]
        self.assertEqual(self.accept(json.dumps(rows), "out.json").returncode, 0)
        md = ("# Guests\n\n| name | email | date |\n|---|---|---|\n"
              "| Anna | anna@example.com | 2026-11-03 |\n| Bob | bob@example.com | 2026-11-05 |\n")
        self.assertEqual(self.accept(md, "out.md").returncode, 0)
        self.red(md.replace("| date |", "| date | paid |").replace("|---|---|---|", "|---|---|---|---|")
                 .replace("03 |", "03 | yes |").replace("05 |", "05 | yes |"), "paid", name="out.md")

    def test_an_unreadable_output_is_red_not_green(self):
        self.red("", name="out.csv")


class Sends(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        approved(self.root)

    def send(self, plan):
        return run(TOOL, self.root, "dinner", str(write(self.root, "send.json", plan)))

    def test_eligible_hidden_recipients_are_green(self):
        r = self.send(HIDDEN_INVITE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 recipients", r.stdout)

    def test_a_recipient_outside_the_audience_is_red_and_named(self):
        r = self.send(dict(HIDDEN_INVITE, bcc=HIDDEN_INVITE["bcc"] + ["Péter <peter@example.com>"]))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("peter@example.com", r.stdout)

    def test_guests_who_see_each_other_are_red(self):
        for plan in ({"to": ["anna@example.com", "bob@example.com"]},
                     {"guests": ["anna@example.com", "bob@example.com"], "guestsCanSeeOtherGuests": True},
                     {"guests": ["anna@example.com", "bob@example.com"]}):
            r = self.send(plan)
            self.assertEqual(r.returncode, 1, (plan, r.stdout))
            self.assertIn("see", r.stdout)
        ok = {"guests": ["anna@example.com", "bob@example.com"], "guestsCanSeeOtherGuests": False}
        self.assertEqual(self.send(ok).returncode, 0)

    def test_a_recipient_list_on_the_command_line(self):
        out = write(self.root, "out.csv", GOOD_CSV)
        lst = write(self.root, "to.txt", "anna@example.com\nstranger@example.org\n")
        r = run(TOOL, self.root, "dinner", str(out), "--recipients", str(lst))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("stranger@example.org", r.stdout)


class CannotCheck(unittest.TestCase):
    def test_no_approved_contract_or_no_output_is_exit_2(self):
        root = brain()
        out = write(root, "out.csv", GOOD_CSV)
        self.assertEqual(run(TOOL, root, "dinner", str(out)).returncode, 2)
        approved(root)
        self.assertEqual(run(TOOL, root, "dinner", str(root / "missing.csv")).returncode, 2)


class PythonApi(unittest.TestCase):
    def test_the_engine_can_call_it_without_a_subprocess(self):
        root = brain()
        approved(root)
        code, lines = mentat_accept.accept(root, "dinner", write(root, "out.csv", GOOD_CSV))
        self.assertEqual(code, 0, lines)
        code, lines = mentat_accept.accept(root, "dinner", write(root, "s.json", {"to": ["x@example.org"]}))
        self.assertEqual(code, 1)
        self.assertTrue(any("x@example.org" in line for line in lines))

    def test_hungarian_sentences(self):
        root = brain("hu")
        approved(root, PROPOSAL, "vacsora")
        r = run(TOOL, root, "vacsora", str(write(root, "out.csv", GOOD_CSV)))
        self.assertIn("ZÖLD", r.stdout)
        self.assertIn("2 sor", r.stdout)


if __name__ == "__main__":
    unittest.main()
