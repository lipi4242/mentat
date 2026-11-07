"""Guard: (1) a Grep/Glob that sweeps a source the role may not read is denied, the developer
included; (2) role Read rules match case-insensitively (Bank/ on a case-insensitive disk)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from test_guard import GuardBase


class SopresKisbetu(GuardBase):
    def setUp(self):
        super().setUp()
        biz = self.root / "agy" / "business" / "zoldag"
        biz.mkdir(parents=True, exist_ok=True)
        (self.root / "munka" / "bank").mkdir(parents=True, exist_ok=True)
        (self.root / "munka" / "bank" / "befizetesek.csv").write_text("datum;osszeg\n")
        (biz / "bekotes.json").write_text(json.dumps({"schema": 1, "business": "zoldag", "sources": [
            {"name": "bank", "kind": "live", "path": "munka/bank/befizetesek.csv"}]}))

    def test_developer_grep_over_an_ancestor_of_a_denied_source(self):
        for inp in ({"pattern": "60000", "path": str(self.root / "munka")},
                    {"pattern": "60000", "path": str(self.root)},
                    {"pattern": "60000"}):  # no path: the cwd (repo root)
            self.assertEqual(self.decide("Grep", inp, "fejleszto"), "deny", inp)
        self.assertEqual(self.decide("Glob", {"pattern": "**/*.csv", "path": str(self.root)}, "fejleszto"), "deny")

    def test_developer_grep_elsewhere_and_assistant_stay_allowed(self):
        (self.root / "src").mkdir(exist_ok=True)
        self.assertEqual(self.decide("Grep", {"pattern": "x", "path": str(self.root / "src")}, "fejleszto"), "allow")
        self.assertEqual(self.decide("Grep", {"pattern": "x", "path": str(self.root)}, "asszisztens", "s2"), "allow")

    def test_role_rule_is_case_insensitive(self):
        p = str(self.root / "munka" / "Bank" / "x.csv")
        self.assertEqual(self.decide("Read", {"file_path": p}, "fejleszto"), "deny")
        self.assertEqual(self.decide("Bash", {"command": "cat %s" % p}, "fejleszto"), "deny")


if __name__ == "__main__":
    unittest.main()
