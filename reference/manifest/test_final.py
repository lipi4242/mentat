"""A final external action (sent, recorded, created) goes out only after a read-back and a yes.

Failure classes: a final external action without a read-back and approval (the promised preview
skipped); a final record with empty mandatory fields, then a corrective counter-record. The
receipt holds the payload's sha256: a changed payload is not approved.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import re
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "mentat_final.py"


def said(root, text):
    d = root / ".mentat" / "state" / "user-said"
    d.mkdir(parents=True, exist_ok=True)
    import time
    with open(d / "s1.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.time() + 0.01, "text": text}) + "\n")


def code_of(out):
    return re.search(r"reply: (\d{4})", out).group(1)


def run(root, *args):
    return subprocess.run([sys.executable, "-I", str(TOOL), "--repo", str(root), *args],
                          capture_output=True, text=True, timeout=30)


class Final(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.pay = self.root / "szamla.json"
        self.pay.write_text(json.dumps({"vevo": "Kovács Kft.", "osszeg": 12000, "megjegyzes": ""}))

    def test_preview_reads_back_and_approval_binds_to_the_exact_payload(self):
        r = run(self.root, "preview", "szamla-7", "--what", "számla a Kovács Kft.-nek", "--to", "https://api.example.com/i", "--file", "szamla.json",
                "--require", "vevo,osszeg")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("READ BACK", r.stdout)
        code = code_of(r.stdout)
        self.assertIn("If it is OK, reply: %s" % code, r.stdout)
        self.assertIn("Kovács Kft.", r.stdout)
        self.assertEqual(run(self.root, "check", "szamla-7").returncode, 1, "not approved yet")
        self.assertEqual(run(self.root, "approve", "szamla-7").returncode, 1, "no reply with the code yet")
        self.assertEqual(run(self.root, "approve", "szamla-7").returncode, 1, "no USER message")
        said(self.root, "Igen, mehet!")  # a plain yes is not the code (CISO round 2)
        self.assertEqual(run(self.root, "approve", "szamla-7").returncode, 1)
        said(self.root, "ok %s" % code)
        self.assertEqual(run(self.root, "approve", "szamla-7").returncode, 0)
        self.assertEqual(run(self.root, "approve", "szamla-7").returncode, 1, "single use")
        self.assertEqual(run(self.root, "check", "szamla-7").returncode, 0)
        self.pay.write_text(json.dumps({"vevo": "Kovács Kft.", "osszeg": 21000}))
        r = run(self.root, "check", "szamla-7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed since", r.stdout)

    def test_an_empty_mandatory_field_stops_the_preview(self):
        r = run(self.root, "preview", "szamla-8", "--what", "x", "--to", "t", "--file", "szamla.json", "--require", "vevo,megjegyzes,adoszam")
        self.assertEqual(r.returncode, 1)
        self.assertIn("megjegyzes", r.stdout)
        self.assertIn("adoszam", r.stdout)
        self.assertIn("structured field", r.stdout)

    def test_after_the_action_the_read_back_from_there_is_recorded(self):
        code = code_of(run(self.root, "preview", "s9", "--what", "x", "--to", "t", "--file", "szamla.json").stdout)
        said(self.root, code)
        run(self.root, "approve", "s9")
        self.assertEqual(run(self.root, "after", "s9").returncode, 2, "it needs what was read back")
        r = run(self.root, "after", "s9", "--seen", "a rendszerben: 12000 Ft, Kovács Kft.")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("DONE", r.stdout)


    def test_every_recipient_is_listed_and_an_excluded_one_stops_it(self):
        (self.root / "level.json").write_text(json.dumps({"to": ["anna@example.com", "bela@example.com"],
                                                         "cc": "csaba@example.com", "subject": "Értesítés"}))
        r = run(self.root, "preview", "m1", "--what", "értesítés", "--to", "smtp", "--file", "level.json")
        self.assertIn("Recipients (3):", r.stdout)
        self.assertIn("  - csaba@example.com", r.stdout)
        r = run(self.root, "preview", "m2", "--what", "értesítés", "--to", "smtp", "--file", "level.json",
                "--exclude", "Bela@Example.com")
        self.assertEqual(r.returncode, 1)
        self.assertIn("excluded recipient", r.stdout)


if __name__ == "__main__":
    unittest.main()
