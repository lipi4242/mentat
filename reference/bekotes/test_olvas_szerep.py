"""olvas grep|show honours the active role's Read denials (h1-16, DeepSeek, 20261022-192044).

The developer role read bank lines with `bekotes.py olvas grep … --source bank`: the guard
only sees the Bash command, not the files olvas opens. olvas now applies the same deny list
itself, and fails closed when the role cannot be resolved."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import shutil
import subprocess
import sys
import unittest

from _bekotes_repo import BIZ, done, env, make_agent, write


class OlvasSzerep(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        write(self.root, ".home/bank/befizetesek.csv", "datum;osszeg_ft\n2026-07-21;60000\n")
        p = self.root / BIZ / "bekotes.json"
        d = json.loads(p.read_text())
        d["sources"].append({"name": "bank", "kind": "live", "path": "~/bank/befizetesek.csv"})
        p.write_text(json.dumps(d, ensure_ascii=False))
        done(self.root)  # roles: default asszisztens, installed fejleszto (Read(**/bank/**))

    def olvas(self, role, *a):
        e = env(self.root)
        if role:
            e["MENTAT_ROLE"] = role
        return subprocess.run([sys.executable, str(self.root / ".mentat/bin/bekotes/bekotes.py"), "olvas", *a],
                              capture_output=True, text=True, cwd=self.root, env=e)

    def test_developer_cannot_read_bank_through_olvas(self):
        for args in (("grep", "60000", "--source", "bank"), ("show", "bank:befizetesek.csv")):
            r = self.olvas("fejleszto", *args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertNotIn("60000", r.stdout + r.stderr, args)
            self.assertIn("fejleszto", r.stderr, args)

    def test_developer_grep_over_all_sources_skips_bank_loudly(self):
        r = self.olvas("fejleszto", "grep", "60000")
        self.assertNotIn("60000", r.stdout)
        self.assertIn("bank", r.stderr)

    def test_assistant_still_reads_bank(self):
        r = self.olvas(None, "show", "bank:befizetesek.csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("60000", r.stdout)

    def test_unresolvable_role_fails_closed(self):
        os.remove(self.root / "agy" / "szerepek" / "fejleszto.md")
        r = self.olvas("fejleszto", "show", "zoldag-web:README.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Zöldág", r.stdout)


if __name__ == "__main__":
    unittest.main()
