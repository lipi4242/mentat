"""Titok-kapu, keresőparancsok: a grep/rg MINTÁJA szöveg, nem fájl (Kata hibajegye, 2026-10-31).
A tick `grep -o '"lease_token": *"[^"]*"' entry.out` parancsát a kapu kulcsfájl-névnek vette.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -p 'test_titok_grep.py' -q
"""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_titok_kapu import Base  # noqa: E402
from titok_kod import search_args  # noqa: E402


class MintaNemUt(Base):
    def test_kata_tick_parancsa_atmegy(self):
        self.put("code/repo/entry.out", '{"lease_token": "abc"}\n')
        for cmd in ("""grep -o '"lease_token": *"[^"]*"' code/repo/entry.out | sed 's/.*"\\([^"]*\\)"$/\\1/' > /tmp/tok""",
                    "grep -o '\"lease_token\": *\"[^\"]*\"' /tmp/x.out",
                    "rg -o 'api_key|secret_token' code/repo/src",
                    "grep -rn --include=*.py 'TOKEN' code/repo/src",
                    "grep -m 1 -e '\"lease_token\"' code/repo/entry.out",
                    "grep -- '--lease-token' code/repo/src/app.py"):
            self.assertIsNone(self.bash(cmd), cmd)

    def test_kulcsfajl_tovabbra_is_tilt(self):
        self.put(".config/vilma/telegram.env", "X=1\n")
        for cmd in ("grep KATA_TELEGRAM_BOT_TOKEN ~/.config/vilma/telegram.env",
                    "grep -o '\"lease_token\": *\"[^\"]*\"' vilma/.env",
                    "grep -e x -- vilma/.env",
                    "grep -f vilma/.env code/repo/src/app.py",
                    "grep --file=vilma/.env code/repo/src/app.py",
                    "rg -e TOKEN -g '*.py' ~/.config",
                    "grep -r TOKEN ~/.config",
                    "zgrep secret ~/.config/szervezo/service-account.json"):
            self.assertTrue(self.bash(cmd), cmd)

    def test_search_args(self):
        self.assertEqual(search_args("grep", ["-o", "PAT", "f"]), ["-o", "f"])
        self.assertEqual(search_args("grep", ["-m", "1", "PAT", "f"]), ["-m", "1", "f"])
        self.assertEqual(search_args("grep", ["-e", "PAT", "f"]), ["f"])
        self.assertEqual(search_args("grep", ["-f", "pats", "f"]), ["-f", "pats", "f"])
        self.assertEqual(search_args("grep", ["--", "-PAT", "f"]), ["f"])
        self.assertEqual(search_args("cat", ["a", "b"]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
