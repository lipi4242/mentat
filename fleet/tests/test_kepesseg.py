"""11-07: képesség-próba (ténylegesen lefut-e) és a független riasztási út.

11-07: minden jel zöld volt, és három ágens nem tudott írni a tulajdonosnak; a riasztás (ha lett
volna) ugyanazon a token nélküli hídon ment volna. Itt: a token nélküli ágens piros, és a riasztás
NEM megy az ágens hídján. 11-07 óta külön riasztó bot sincs: a központi jelentés
(test_flotta_report.py) viszi, annak hiányában a fájl-tartalék és a piros doctor-sor."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import os
import shutil
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from _essentials_box import entry, make_box
from fleet import BRIDGE_DIR, alerts, doctor_box, flotta_report as F, kepesseg as K, kepesseg_riaszt as R, postcheck as P

TOKEN = "123456789:HAMIS_agens_nem_valodi_0123456789abcdef"
FLEET_TOKEN = "987654321:HAMIS_flotta_nem_valodi_0123456789abcd"
NODE = shutil.which("node")


def box(case) -> Path:
    home = make_box(case)
    for a in ("vilma", "szervezo"):
        (home / ".config" / a / "telegram.env").write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_GROUP_CHAT_ID=-100\n")
        shutil.copytree(BRIDGE_DIR, home / ".config" / a / "sub-etha", ignore=shutil.ignore_patterns("test", "docs"))
        subprocess.run(["git", "init", "-q", str(home / a)], check=True)
    return home


@unittest.skipUnless(NODE, "node kell a send.mjs dry-run-jához")
class Check(unittest.TestCase):
    def setUp(self):
        self.home = box(self)
        self.vilma, self.szervezo = entry("vilma"), entry("szervezo", env_file="agent.env")

    def test_zold_agens_minden_lepese_lefut(self):
        r = K.check(self.vilma, self.home)
        self.assertEqual(r["red"], [], r)
        self.assertIn("küldés (dry-run)", r["ok"])
        self.assertIn("git", r["ok"])

    def test_token_nelkuli_unit_piros_es_az_operator_tokenje_nem_ad_hamis_zoldet(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_GROUP_CHAT_ID": "-1"}):
            r = K.check(self.szervezo, self.home)
        red = " ".join(r["red"])
        self.assertIn("NEM MENNE", red)
        self.assertNotIn("HAMIS", red)

    def test_serult_allapotfajl_piros(self):
        p = self.home / "vilma/data/state/anytime-state.json"
        p.parent.mkdir(parents=True)
        p.write_text("{nem json")
        self.assertTrue(any("anytime-state.json" in x for x in K.check(self.vilma, self.home)["red"]))

    def test_nem_git_repo_piros(self):
        shutil.rmtree(self.home / "vilma/.git")
        self.assertTrue(any(x.startswith("git:") for x in K.check(self.vilma, self.home)["red"]))

    def test_todo_ha_be_van_allitva_es_hibas_piros(self):
        (self.home / ".config/todo").mkdir(parents=True)
        (self.home / ".config/todo/env").write_text("TODO_API=http://127.0.0.1:9\n")
        exe = self.home / ".local/bin/mentat-todo"
        exe.parent.mkdir(parents=True)
        exe.write_text('#!/bin/sh\necho "mentat-todo: nincs token: x" >&2\nexit 2\n')
        exe.chmod(0o755)
        red = K.check(self.vilma, self.home)["red"]
        self.assertTrue(any("mentat-todo: nincs token" in x for x in red), red)

    def test_postcheck_kepesseg_hiba_failed_es_capability_only(self):
        from test_truthful_health import _m, NOW
        r = P.postcheck(self.szervezo, measure=lambda _e: _m(), restart_at=None, now=lambda: NOW,
                        capability=lambda e: K.check(e, self.home))
        self.assertEqual(r["status"], P.FAILED)
        self.assertTrue(r["capability_only"])
        self.assertTrue(r["problems"][0].startswith("képesség: "))


class FakeTelegram:
    def __init__(self, case):
        self.calls = []
        calls = self.calls

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                out = json.dumps({"ok": True, "result": {"message_id": 7}}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        case.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"


@unittest.skipUnless(NODE, "node kell a send.mjs-hez")
class NoAlertBot(unittest.TestCase):
    """11-07: nincs külön riasztó bot. A képesség-hiba a központba megy, annak hiányában fájlba;
    Telegramra sem a régi alert.env-en, sem az ágens tokenes hídján nem megy ki."""

    def setUp(self):
        self.home = box(self)
        self.szervezo = entry("szervezo", env_file="agent.env")
        st = self.home / ".config/fleet"
        self.tg = FakeTelegram(self)
        for obj, name, val in ((alerts, "ALERTS_PATH", st / "state/alerts.json"),
                               (alerts, "UNDELIVERED", st / "state/alerts-undelivered.jsonl"),
                               (R, "STATE", st / "state/kepesseg.json"),
                               (F, "ENV_PATH", st / "flotta.env"), (F, "STATE", st / "state/flotta-report.json")):
            p = mock.patch.object(obj, name, val)
            p.start()
            self.addCleanup(p.stop)
        env = mock.patch.dict(os.environ, {"SUBETHA_TELEGRAM_API": self.tg.url, "BRIDGE_STATE_DIR": str(st),
                                           "FLEET_ALERT_ENV": str(st / "alert.env")})
        env.start()
        self.addCleanup(env.stop)
        # a régi (#52) riasztó bot fájlja ott van: mégsem használja semmi
        st.mkdir(parents=True, exist_ok=True)
        (st / "alert.env").write_text(f"TELEGRAM_BOT_TOKEN={FLEET_TOKEN}\nTELEGRAM_ALERT_CHAT_ID=-555\n")
        self.measure = lambda e: {"red": K.check(e, self.home)["red"]}

    def test_a_riaszto_bot_utja_megszunt(self):
        self.assertFalse(hasattr(alerts, "independent_env"))
        self.assertFalse(hasattr(alerts, "ALERT_ENV"))
        lines = R.sweep([self.szervezo], self.home, now=1e9, measure=self.measure, host="box")
        self.assertTrue(any("[stderr]" in ln for ln in lines), lines)
        self.assertEqual(self.tg.calls, [])        # se a flotta botja, se az ágensé

    def test_kozpont_nelkul_fajl_es_doctor_piros_az_agens_hidja_sem_hasznalt(self):
        own = [self.home / ".config/szervezo/telegram.env"]   # tokenes: mégsem mehet ezen
        self.assertEqual(R.alert_red("szervezo", ["x"]), "stderr")
        self.assertEqual(alerts.alert("kepesseg:szervezo:y", "t", agent_env_file=own, independent_only=True), "stderr")
        self.assertEqual(self.tg.calls, [])
        rows = alerts.UNDELIVERED.read_text().splitlines()
        self.assertEqual(len(rows), 2)
        probs, warn, _, _ = doctor_box.alert_route(now=json.loads(rows[0])["ts"] + 1)
        self.assertTrue(any("NEM ment ki" in p for p in probs), probs)
        self.assertTrue(any("jelentés: kikapcsolva" in w for w in warn), warn)

    def test_nem_kepesseg_riasztas_az_agens_hidjara_eshet_vissza(self):
        own = [self.home / ".config/szervezo/telegram.env"]
        self.assertEqual(alerts.alert("rc:szervezo", "t", agent_env_file=own), "sent-agent")
        self.assertIn(TOKEN, self.tg.calls[0][0])
        self.assertNotIn(FLEET_TOKEN, self.tg.calls[0][0])


class ReconcileCapabilityOnly(unittest.TestCase):
    def test_kepesseg_hiba_nem_karantenoz_hanem_fuggetlenul_riaszt(self):
        from fleet import reconcile as rc
        sent = []
        st = {"failed_postchecks": 1, "pending_postcheck": {"restart_at": 1}}
        r = {"status": P.FAILED, "problems": ["képesség: küldés NEM MENNE"], "pending": [], "capability_only": True}
        with mock.patch.object(R, "alert_red", lambda a, red: sent.append((a, red)) or "sent"), \
                mock.patch.object(rc, "save_state", lambda a, s: None):
            log = []
            rc._record_postcheck(entry("vilma"), st, r, log=log.append)
        self.assertEqual(st["failed_postchecks"], 1)
        self.assertFalse(st.get("quarantined"))
        self.assertEqual(sent, [("vilma", r["problems"])])


if __name__ == "__main__":
    unittest.main()
