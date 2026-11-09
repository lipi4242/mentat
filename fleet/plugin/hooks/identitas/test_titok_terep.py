"""2026-11-07: a terepről jelentett téves tiltások, és hogy a valódi tiltás szigorú marad.

1. 0700-as job-szkript futtatása; 2. 0600-as travel/budget.json olvasása; 3. `python3 -c` egy
`best_key` mezőnévvel; 4. szabad szöveg `env`-vel / kulcsfájl nevével; 5. `find .` a repóban;
6. `grep -r minta .` egy `…_keys.sql` migráció mellett (név-heurisztika) — `--exclude-dir`-rel
átmegy; 7. a telegram.env `.`-tal betöltése, a kulcsfájl olvasása: TILT (helyes, szigorú).
A téves gyanús tiltás bejelentést kér (nem kerülőutat); az erős tiltás nem.
Futtatás: python3 -I -m unittest discover -s fleet/plugin/hooks/identitas -p 'test_titok_terep.py' -q
"""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_titok_kapu import Base  # noqa: E402
import titok_kapu as K  # noqa: E402


class TerepiTevesTiltas(Base):
    def setUp(self):
        super().setUp()
        for d in (".config/thufir/jobs", "agent/data/travel", "agent/tmp/arany/db/migrations", "agent/src"):
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self.put(".config/thufir/jobs/todo_poll.py", "print(1)\n")
        os.chmod(os.path.join(self.home, ".config/thufir/jobs/todo_poll.py"), 0o700)
        self.put(".config/thufir/telegram.env", "TELEGRAM_BOT_TOKEN=x\n")
        self.put("agent/data/travel/budget.json", '{"total": 1}')
        self.put("agent/tmp/arany/db/migrations/0027_release_reverted_keys.sql", "ALTER TABLE x;\n")
        self.put("agent/src/app.py", "print(1)\n")
        self.cwd = os.path.join(self.home, "agent")

    def test_terepi_parancsok_atmennek(self):
        for cmd in ("python3 ~/.config/thufir/jobs/todo_poll.py",
                    "python3 -c \"d={'best_key': 1}; print(d['best_key'])\"",
                    "gh pr create --title x --body 'a tokent a ~/.config/todo/env adja, nem a repó'",
                    "echo 'a credentials.json fájlt ne olvasd'",
                    "find .",
                    "grep -rn --exclude-dir=tmp minta .",
                    "grep -r --exclude-dir tmp minta .",
                    "git status --short"):
            self.assertIsNone(self.bash(cmd), cmd)
        self.assertIsNone(K.decide("Read", {"file_path": "data/travel/budget.json"}, self.cwd, None))

    def test_sql_migracio_neve_nem_kulcsfajl(self):
        self.assertIsNone(self.bash("cat tmp/arany/db/migrations/0027_release_reverted_keys.sql"))

    def test_valodi_titok_szigoruan_tilt(self):
        for cmd in ("set -a; . ~/.config/thufir/telegram.env; set +a",
                    "cat ~/.config/thufir/telegram.env",
                    "grep -r --exclude-dir=tmp TOKEN ~/.config"):
            self.assertTrue(self.bash(cmd), cmd)

    def test_kizart_mappa_csak_a_sajatjat_engedi(self):
        self.put("agent/src/deploy.key", "x\n")
        self.assertTrue(self.bash("grep -r --exclude-dir=tmp minta ."))  # a src/ kulcsa nincs kizárva

    def test_gyanus_tiltas_bejelentest_ker_az_eros_nem(self):
        self.put("agent/src/api_keys", "x\n")
        weak = K.hook({"tool_name": "Bash", "cwd": self.cwd, "tool_input": {"command": "cat src/api_keys"}})
        strong = K.hook({"tool_name": "Bash", "cwd": self.cwd,
                         "tool_input": {"command": "cat ~/.config/thufir/telegram.env"}})
        self.assertIn("NE kerüld meg", weak["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertNotIn("NE kerüld meg", strong["hookSpecificOutput"]["permissionDecisionReason"])

    def test_mappa_talalat_megnevezi_a_kizarhato_mappat(self):
        self.put("agent/src/deploy.key", "x\n")
        self.assertIn("(src)", self.bash("grep -r minta ."))


if __name__ == "__main__":
    unittest.main()
