"""The receipt is written by `where --find`, the decision by `where --decide`; the agent writes neither."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from _caps_base import CapsBase

WHY = "a cases csomag ügyenként szól; itt egy tagonként összesítő heti lista kell, ami nincs benne"


class Receipt(CapsBase):
    def receipt(self, query):
        out = self.find(query)
        path = self.root / out["receipt"]
        self.assertTrue(path.is_file(), out["receipt"])
        self.assertTrue(out["receipt"].startswith(".mentat/state/capability-receipts/"))
        return out, path

    def decide(self, path, *args):
        return self.run_where("--decide", str(path), *args)

    def test_find_writes_the_receipt_with_index_candidates_and_recommendation(self):
        out, path = self.receipt("minden reggel írd ki, ki nem fizetett")
        doc = json.loads(path.read_text())
        self.assertEqual(doc["query"], "minden reggel írd ki, ki nem fizetett")
        self.assertRegex(doc["index"]["hash"], r"^[0-9a-f]{16,}$")
        self.assertTrue(doc["index"]["version"])
        self.assertEqual(doc["candidates"][0]["id"], "engine.cases")
        self.assertEqual(doc["recommendation"]["decision"], "enable")
        self.assertIsNone(doc["decision"])

    def test_use_is_recorded_once(self):
        _, path = self.receipt("minden reggel írd ki, ki nem fizetett")
        r = self.decide(path, "enable", "--candidate", "engine.cases")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(path.read_text())
        self.assertEqual((doc["decision"]["decision"], doc["decision"]["candidate"]), ("enable", "engine.cases"))
        self.assertEqual(self.decide(path, "use", "--candidate", "engine.cases").returncode, 1)

    def test_use_needs_a_candidate_from_this_receipt(self):
        _, path = self.receipt("minden reggel írd ki, ki nem fizetett")
        self.assertEqual(self.decide(path, "use").returncode, 1)
        self.assertEqual(self.decide(path, "use", "--candidate", "web.publish").returncode, 1)

    def test_new_needs_the_closest_candidate_and_what_it_lacks(self):
        _, path = self.receipt("minden reggel írd ki, ki nem fizetett")
        self.assertEqual(self.decide(path, "new", "--why", WHY).returncode, 1)
        r = self.decide(path, "new", "--candidate", "engine.cases", "--why", "kell")
        self.assertEqual(r.returncode, 1)
        r = self.decide(path, "new", "--candidate", "engine.cases", "--why", WHY)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(path.read_text())["decision"]["why"], WHY)

    def test_inconclusive_receipt_authorizes_nothing_without_the_users_yes(self):
        _, path = self.receipt("fordítsd le ezt a verset szonettbe")
        self.assertEqual(self.decide(path, "use", "--candidate", "brain.new").returncode, 1)
        r = self.decide(path, "new", "--why", WHY)
        self.assertEqual(r.returncode, 2)
        self.assertIn("nem dönthető", r.stdout)
        r = self.decide(path, "new", "--why", WHY, "--approved", "igen, írd meg")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_new_over_a_planned_suite_capability_needs_the_users_yes(self):
        _, path = self.receipt("írj egy új rutint, egy saját concernt")
        args = ("new", "--candidate", "engine.concern_template", "--why", WHY)
        self.assertEqual(self.decide(path, *args).returncode, 2)
        self.assertEqual(self.decide(path, *args, "--approved", "igen").returncode, 0)

    def test_a_changed_index_makes_the_receipt_stale(self):
        _, path = self.receipt("minden reggel írd ki, ki nem fizetett")
        self.write("projects/uj/README.md", "# Új\n")
        r = self.decide(path, "enable", "--candidate", "engine.cases")
        self.assertEqual(r.returncode, 1)
        self.assertIn("STALE", r.stdout)

    def test_map_is_a_generated_markdown_table(self):
        self.write("projects/tagdij/README.md", "# Tagdíj\n")
        r = self.run_where("--map")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("| id |", r.stdout)
        for cid in ("engine.cases", "google.calendar", "web.publish", "own.project.tagdij"):
            self.assertIn("| %s |" % cid, r.stdout)


if __name__ == "__main__":
    unittest.main()
