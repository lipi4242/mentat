"""mentat_contract.py: a change after the USER's yes. A material change is a new version that
needs a new yes (the old one is kept in the history); a note does not void the approval.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from _contract_fixture import PROPOSAL, approved, brain, run, write
from test_contract import TOOL, contract


class Changes(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        approved(self.root)

    def propose(self, **change):
        write(self.root, "p2.json", dict(PROPOSAL, **change))
        return str(self.root / "p2.json")

    def test_diff_names_a_material_change(self):
        r = run(TOOL, self.root, "diff", "dinner", "--file", self.propose(fields=["name", "email"]))
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("fields", r.stdout)
        r = run(TOOL, self.root, "diff", "dinner", "--file", self.propose(notes="typo fixed"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_material_redraft_needs_a_new_yes(self):
        r = run(TOOL, self.root, "draft", "dinner", "--file",
                self.propose(window=dict(PROPOSAL["window"], end="2026-11-15")))
        self.assertEqual(r.returncode, 0, r.stderr)
        c = contract(self.root)
        self.assertEqual((c["version"], c["status"]), (2, "draft"))
        self.assertEqual(c["history"][0]["version"], 1)
        self.assertEqual(run(TOOL, self.root, "check-write", "dinner").returncode, 2)
        run(TOOL, self.root, "approve", "dinner", "--quote", "yes, two weeks")
        self.assertEqual(run(TOOL, self.root, "check-write", "dinner", "--dates", "2026-11-14").returncode, 0)

    def test_a_non_material_redraft_keeps_the_approval(self):
        run(TOOL, self.root, "draft", "dinner", "--file", self.propose(notes="for the caterer"))
        c = contract(self.root)
        self.assertEqual((c["version"], c["status"]), (1, "approved"))
        self.assertEqual(run(TOOL, self.root, "check-write", "dinner").returncode, 0)

    def test_show_prints_the_status_and_the_approval(self):
        r = run(TOOL, self.root, "show", "dinner")
        self.assertEqual(r.returncode, 0)
        self.assertIn("approved", r.stdout)
        self.assertIn("yes, that's it", r.stdout)
        self.assertEqual(json.loads(run(TOOL, self.root, "show", "dinner", "--json").stdout)["version"], 1)


if __name__ == "__main__":
    unittest.main()
