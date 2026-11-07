"""Guard: a Read-denied path is denied in a Bash command too (h1-16: `cat …/bank/…`)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from test_guard import GuardBase


class GuardBashPath(GuardBase):
    def test_developer_cannot_cat_the_bank(self):
        for cmd in ("cat ~/business/bank/befizetesek.csv",
                    "head -5 $HOME/business/bank/befizetesek.csv",
                    "grep 2026 ${HOME}/business/bank/x.csv | wc -l",
                    "cp munka/bank/x.csv /tmp/y",
                    "cd munka && less bank/x.csv"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto"), "deny", cmd)

    def test_relative_path_from_the_hook_cwd(self):
        (self.root / "munka").mkdir()
        self.assertEqual(self.decide("Bash", {"command": "cat bank/x.csv"}, "fejleszto",
                                     cwd=str(self.root / "munka")), "deny")

    def test_other_commands_and_roles_stay_allowed(self):
        # outside the folder only an onboarded source is readable (szerep_kint, friction #8)
        cfg = self.root / "agy" / "business" / "zoldag" / "bekotes.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"schema": 1, "sources": [
            {"name": "bank", "kind": "live", "path": "~/business/bank/befizetesek.csv"}]}))
        self.assertEqual(self.decide("Bash", {"command": "cat ~/business/bank/befizetesek.csv"},
                                     "asszisztens"), "allow")
        for cmd in ("ls README.md", "git log --oneline -3", "echo bankkartya", "cat munka/banking.md"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto"), "allow", cmd)


if __name__ == "__main__":
    unittest.main()
