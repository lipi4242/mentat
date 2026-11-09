"""11-07: a 0700-as job-szkript (pl. ~/.config/<a>/jobs/todo_poll.py) kód, nem titok.

11-07: a `fleet secrets scan` a mód miatt leltárba vette, és a titok-kapu a `lel.has(...)` ágon
megtagadta a futtatását („leltárban: todo_poll.py"). A literál titkot hordozó szkript marad titok,
és egy valódi kulcsfájl olvasása a javítás után is tilt (a kapu tud pirosat)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fleet import titok_leltar as L, titok_telepit as T

FAKE = "HAMIS-ERTEK-NEM-VALODI-0123456789"


OUT = {  # a 11-07-i box valódi alakjai, kitalált tartalommal: privát mód, de nincs titok-bizonyíték
    "vilma/scripts/anytime/anytime-state-v2.json": json.dumps({"schema_version": 1, "last_run": {"x": 1}}),
    "vilma/scripts/anytime/anytime-state-v2.json.prev.1": json.dumps({"schema_version": 1}),
    "vilma/scripts/review-state/current.json": json.dumps({"date": "2026-11-07", "items": []}),
    "vilma/data/travel/budget.json": json.dumps({"total": 1200, "currency": "EUR"}),
    "vilma/data/travel/heartbeat.json": json.dumps({"at": "2026-11-07T10:00", "owner_token": "lease-abcdefghij"}),
    "vilma/docs/trips/2026-12-lisszabon.json": json.dumps({"flights": ["BUD-LIS"], "hotel": "Alfama"}),
    "vilma/worker/migrations/0027_release_reverted_keys.sql": "ALTER TABLE x ADD COLUMN reverted_keys TEXT;\n",
    "vilma/worker/migrations/0031_api_tokens.sql": "CREATE TABLE api_tokens (id TEXT);\n",
    ".config/vilma/engine-state.json": json.dumps({"cursor": 5, "lease_token": "abcdefghijklmnop"}),
    ".config/vilma/repos.json": json.dumps({"repos": ["a/b"]}),
    ".config/vilma/jobs/todo_poll.py": "#!/usr/bin/env python3\ntok=open('/x/vilma.token').read().strip()\n",
    ".config/vilma/jobs/poll.sh": "#!/bin/sh\ncurl -s \"$TODO_API\"\n",
    ".config/vilma/jobs/futtato": "#!/bin/sh\necho kod\n",
}
IN = {  # valódi titok-alakok
    ".config/vilma/telegram.env": f"TELEGRAM_BOT_TOKEN={FAKE}\n",
    ".config/vilma/agent.env": f"OPENAI_API_KEY={FAKE}\nMODEL=opus\n",
    "vilma/data/health/strava_tokens.json": json.dumps({"access_token": FAKE, "expires_at": 1}),
    "vilma/.thufir/connect.json": json.dumps({"token": FAKE}),
    ".config/vilma/jobs/regi_kulcsos.py": f"API_KEY = \"{FAKE}\"\n",
    "vilma/data/state/leaked.json": json.dumps({"api_key": FAKE}),
}


class KodNemTitok(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        for rel, text in {**OUT, **IN}.items():
            (self.home / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.home / rel).write_text(text)
            os.chmod(self.home / rel, 0o700 if "/jobs/" in rel else 0o600)
        (self.home / ".config/vilma/approvers.txt").write_text("valaki\n")
        os.chmod(self.home / ".config/vilma/approvers.txt", 0o600)
        (self.home / ".config/vilma/adat.bin").write_bytes(b"\x00\x01ismeretlen")
        os.chmod(self.home / ".config/vilma/adat.bin", 0o600)
        self.inv = L.scan(["vilma"], home=self.home, repos={"vilma": self.home / "vilma"})
        self.paths = {f["path"] for f in self.inv["files"]}
        self.review = {Path(f["path"]).name for f in self.inv["review"]}

    def test_mod_egyedul_nem_titok(self):
        for rel in OUT:
            self.assertNotIn(str(self.home / rel), self.paths, rel)

    def test_valodi_titok_bent_marad(self):
        for rel in IN:
            self.assertIn(str(self.home / rel), self.paths, rel)

    def test_ismeretlen_privat_atnezendo_de_nem_titok(self):
        self.assertIn("adat.bin", self.review)
        self.assertNotIn(str(self.home / ".config/vilma/adat.bin"), self.paths)
        self.assertNotIn(FAKE, json.dumps(self.inv) + L.table(self.inv, self.home))

    def _gate(self, command: str) -> str:
        T.install(self.home, agents=[])
        L.save(self.inv, self.home)
        data = json.dumps({"tool_name": "Bash", "cwd": str(self.home), "tool_input": {"command": command}})
        r = subprocess.run([sys.executable, "-I", str(T.code_dir(self.home) / "current" / "titok_kapu.py"), "--hook"],
                           input=data, capture_output=True, text=True, env={**os.environ, "HOME": str(self.home)})
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_a_kapu_futtatni_engedi_a_job_szkriptet(self):
        self.assertEqual(self._gate("python3 ~/.config/vilma/jobs/todo_poll.py"), "")

    def test_a_kapu_a_kulcsfajlt_tovabbra_is_tiltja(self):
        self.assertIn('"deny"', self._gate("cat ~/.config/vilma/telegram.env"))


if __name__ == "__main__":
    unittest.main()
