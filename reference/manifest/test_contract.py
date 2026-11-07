"""mentat_contract.py: the approved task contract lives in a file, not only in the chat.

Class of error (holdout, 0.3.0): fields, exclusions, recipients, the time window and the
defaults existed only in the conversation, so the agent drifted from them, added extras
unasked and turned "next week" into a 14-day window. The contract is written only after
the USER's explicit yes; a material change needs a new version and a new yes.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from _contract_fixture import PROPOSAL, approved, brain, run, write

TOOL = "mentat_contract.py"


def contract(root, cid="dinner", folder="brain"):
    return json.loads((root / folder / "contracts" / (cid + ".json")).read_text(encoding="utf-8"))


class Draft(unittest.TestCase):
    def setUp(self):
        self.root = brain()

    def draft(self, proposal, cid="dinner"):
        write(self.root, "p.json", proposal)
        return run(TOOL, self.root, "draft", cid, "--file", str(self.root / "p.json"))

    def test_draft_reads_back_in_plain_words_and_is_not_approved(self):
        r = self.draft(PROPOSAL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for part in ("confirmed guests", "name, email, date", "phone", "2026-11-02", "2026-11-08",
                     "Europe/Budapest", "cannot see each other", "yes"):
            self.assertIn(part, r.stdout, part)
        c = contract(self.root)
        self.assertEqual((c["schema"], c["version"], c["status"]), (1, 1, "draft"))
        self.assertIsNone(c["approval"])

    def test_relative_or_zoneless_dates_are_refused(self):
        for window in ({"start": "next week", "end": "2026-11-08", "tz": "Europe/Budapest"},
                       {"start": "2026-11-02", "end": "2026-11-08"},
                       {"start": "2026-11-09", "end": "2026-11-08", "tz": "Europe/Budapest"},
                       {"start": "2026-11-02", "end": "2026-11-08", "tz": "Mars/Base"}):
            r = self.draft(dict(PROPOSAL, window=window))
            self.assertEqual(r.returncode, 1, (window, r.stdout))
            self.assertFalse((self.root / "brain" / "contracts" / "dinner.json").exists(), window)

    def test_goal_is_required(self):
        r = self.draft(dict(PROPOSAL, goal=""))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_hungarian_readback(self):
        root = brain("hu")
        write(root, "p.json", PROPOSAL)
        r = run(TOOL, root, "draft", "vacsora", "--file", str(root / "p.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("igen", r.stdout)
        self.assertIn("nem látják egymást", r.stdout)
        self.assertTrue((root / "agy" / "contracts" / "vacsora.json").exists())


class Approve(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        write(self.root, "p.json", PROPOSAL)
        run(TOOL, self.root, "draft", "dinner", "--file", str(self.root / "p.json"))

    def test_without_the_users_words_nothing_is_approved(self):
        for quote in ("", "   "):
            r = run(TOOL, self.root, "approve", "dinner", "--quote", quote)
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn("NOT APPROVED", r.stdout)
        self.assertEqual(contract(self.root)["status"], "draft")

    def test_approval_records_the_quote_and_the_version_seen(self):
        r = run(TOOL, self.root, "approve", "dinner", "--quote", "yes, go", "--version", "2")
        self.assertEqual(r.returncode, 1, r.stdout)  # the USER saw another version
        r = run(TOOL, self.root, "approve", "dinner", "--quote", "yes, go", "--version", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = contract(self.root)
        self.assertEqual(c["status"], "approved")
        self.assertEqual(c["approval"]["quote"], "yes, go")
        self.assertTrue(c["approval"]["at"])


class CheckWrite(unittest.TestCase):
    def setUp(self):
        self.root = brain()

    def check(self, *args):
        return run(TOOL, self.root, "check-write", "dinner", *args)

    def test_no_approved_contract_means_no_write(self):
        self.assertEqual(self.check("--fields", "name").returncode, 2)
        write(self.root, "p.json", PROPOSAL)
        run(TOOL, self.root, "draft", "dinner", "--file", str(self.root / "p.json"))
        r = self.check("--fields", "name")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_planned_write_inside_and_outside_the_contract(self):
        approved(self.root)
        self.assertEqual(self.check("--fields", "name,date", "--dates", "2026-11-08").returncode, 0)
        r = self.check("--fields", "name,phone")
        self.assertEqual(r.returncode, 1)
        self.assertIn("phone", r.stdout)
        r = self.check("--fields", "name,notes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("notes", r.stdout)
        r = self.check("--recipients", "anna@example.com,stranger@example.org")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stranger@example.org", r.stdout)
        self.assertNotIn("anna@example.com", r.stdout)
        self.assertEqual(self.check("--recipients", "peter@example.com").returncode, 1)  # declined
        self.assertEqual(self.check("--dates", "2026-11-09").returncode, 1)

    def test_a_hand_edit_after_approval_voids_the_approval(self):
        approved(self.root)
        path = self.root / "brain" / "contracts" / "dinner.json"
        c = json.loads(path.read_text())
        c["terms"]["fields"].append("phone")
        path.write_text(json.dumps(c))
        r = self.check("--fields", "name")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("changed after", r.stdout)


if __name__ == "__main__":
    unittest.main()
