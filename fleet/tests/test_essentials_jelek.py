"""11-07: a scan boxszinten semmit nem kapcsol be; a doctor pirosat ad; a futásidejű
szerződés (token a unit env-jéből, a sh -c tölti be) a renderelt unitban, a szabályszövegben és a
kapuban egyezik."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import shutil
import time
import unittest
from argparse import Namespace as NS
from pathlib import Path
from unittest import mock

from _essentials_box import entry, make_box
from fleet import TEMPLATES_DIR, doctor, essentials as E, essentials_env as EE, render, titok_cli, titok_telepit as T

TMPL = (TEMPLATES_DIR / "agent.service.tmpl").read_text()
RULES = (TEMPLATES_DIR / "rules" / "fleet.md.tmpl").read_text()


class Scan(unittest.TestCase):
    def setUp(self):
        self.home = Path.home()
        self.settings = self.home / ".claude" / "settings.json"
        self.settings.parent.mkdir(exist_ok=True)
        self.settings.write_text(json.dumps({"model": "x"}))
        self.addCleanup(shutil.rmtree, self.home / ".claude", True)
        self.addCleanup(shutil.rmtree, self.home / ".mentat", True)

    def test_a_scan_nem_telepit_es_nem_kapcsol_merge_modot(self):
        before = self.settings.read_bytes()
        rc = titok_cli.cmd_scan(NS(agent=["a", "b"], repo=None, json=False))
        self.assertEqual(rc, 0)
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertFalse((T.code_dir(self.home) / "current").exists())
        self.assertFalse((self.home / ".mentat/titkok/hatar-aktiv").exists())

    def test_az_alfunkciot_tilto_uj_leltar_nem_el(self):
        cur = T.code_dir(self.home) / "current"
        cur.mkdir(parents=True)
        (cur / "titok_kapu.py").write_text("")
        red = {"a": {"red": ["Telegram-küldés TILTVA"], "warn": [], "unknown": []}}
        with mock.patch.object(E, "probe", return_value=red), mock.patch.object(E, "local_agents", return_value=[]):
            self.assertEqual(titok_cli.cmd_scan(NS(agent=["a"], repo=None, json=False)), 2)
        self.assertFalse((self.home / ".mentat/titkok/leltar.json").exists())  # nem volt régi: nem marad új

    def test_dry_run_nem_ir_leltart(self):
        titok_cli.cmd_scan(NS(agent=["a"], repo=None, json=False, dry_run=True))
        self.assertFalse((self.home / ".mentat/titkok/leltar.json").exists())


class Doctor(unittest.TestCase):
    def setUp(self):
        self.home = make_box(self)

    def _m(self):
        sig = {k: {"state": "up", "detail": "", "data": {}} for k in ("process", "schedule", "channel", "rc")}
        return {"signals": sig, "pollers": []}

    def test_essentials_piros_a_doctorban(self):
        with mock.patch("fleet.doctor.judge", return_value={"health": "healthy", "pending": [], "unknown": [],
                                                             "unhealthy": [], "per_signal": {k: ("ok",) for k in
                                                             ("process", "schedule", "channel", "rc")}}):
            rep = doctor.assess(entry("vilma"), self._m(), {}, unit_active="active", unit_enabled="enabled",
                                drop_in=True, bridge_installed="x", bridge_current="x", locked=False,
                                essentials={"red": ["Telegram-küldés TILTVA: x"], "warn": ["w"], "unknown": []})
        self.assertFalse(rep["ok"])
        self.assertIn("Telegram-küldés TILTVA: x", rep["problems"])
        self.assertIn("w", rep["warnings"])

    def test_tokennelkuli_kuldes_a_naplobol(self):
        inbox = self.home / ".config/vilma/telegram-inbox"
        inbox.mkdir(parents=True)
        now = time.time()
        row = {"v": 1, "type": "notice", "event": "missing_token", "ts": int(now * 1000)}
        (inbox / f"delivery-{time.strftime('%Y-%m-%d', time.gmtime(now))}.jsonl").write_text(json.dumps(row) + "\n")
        self.assertIn("token nélkül", EE.send_failures(entry("vilma"), self.home, now))
        self.assertIsNone(EE.send_failures(entry("vilma"), self.home, now + 2 * 86400))


class Szerzodes(unittest.TestCase):
    """Egy hely, egy állítás: a hidas ágens tokenje a unit env-jéből jön."""

    def test_a_pane_shellje_tolti_be_a_telegram_env_et(self):
        u = render.render_unit(entry("szervezo", env_file="agent.env"), template=TMPL)
        exec_line = next(ln for ln in u.splitlines() if ln.startswith("ExecStart="))
        sh = exec_line.split("/bin/sh -c '", 1)[1]
        self.assertIn("if [ -r %h/.config/szervezo/telegram.env ]; then . %h/.config/szervezo/telegram.env; fi;", sh)
        self.assertLess(sh.index("telegram.env"), sh.index("exec %h/.local/bin/claude"))

    def test_szabaly_es_essentials_ugyanazt_az_alakot_mondja(self):
        self.assertIn("A token env-ből", RULES)
        self.assertIn("~/.config/@@AGENT@@/sub-etha/send.mjs", RULES)
        cmds = [c[2].get("command", "") for c in E.commands(entry("vilma"), Path("/nincs"))]
        self.assertIn("node ~/.config/vilma/sub-etha/send.mjs --chat 1 -- x", cmds)
        self.assertTrue(any("--text-stdin" in c for c in cmds))
        self.assertIn("mentat-todo me", cmds)


if __name__ == "__main__":
    unittest.main()
