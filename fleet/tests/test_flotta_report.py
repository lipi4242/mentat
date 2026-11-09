"""11-07: a box jelentése a központi flotta-ellenőrzésnek.

A központ itt egy hamis HTTP-szerver (127.0.0.1); valódi Admin és valódi token nincs. Mérjük:
a jelentés tartalmát (box, verzió, kiadás, ágensek és a piros sorok kulcsa), a 10 perces ritmust,
a hálózati hibát (korlátos idő, a reconcile nem törik, fájl-tartalék, doctor „elavult”), a
hiányzó beállítást (a funkció ki van kapcsolva, a doctor mondja), és hogy a token sehol nem látszik."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from fleet import alerts, doctor_box, flotta_coverage as C, flotta_report as F, kepesseg_riaszt as R, release_lag

TOKEN = "mentat_HAMIS_box_token_nem_valodi_0123456789"


class FakeAdmin:
    def __init__(self, case, status=200, delay=0.0, location=None, expires="2999-01-01 00:00:00", code=None):
        self.calls = []
        calls = self.calls

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, dict(self.headers), body))
                time.sleep(delay)
                self.send_response(status)
                if location:
                    self.send_header("Location", location)
                self.send_header("content-type", "application/json")
                self.end_headers()
                out = {"ok": True, "token_expires_at": expires} if status < 400 else {"error": "x", "rejected": True, "code": code}
                self.wfile.write(json.dumps(out).encode())

            def log_message(self, *a):
                pass
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        case.addCleanup(self.srv.server_close)
        case.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        for obj, name, val in ((F, "ENV_PATH", self.dir / "flotta.env"), (F, "STATE", self.dir / "state/flotta-report.json"),
                               (R, "STATE", self.dir / "state/kepesseg.json"), (alerts, "ALERTS_PATH", self.dir / "state/alerts.json"),
                               (alerts, "UNDELIVERED", self.dir / "state/alerts-undelivered.jsonl"),
                               (C, "UNREACHABLE", self.dir / "state/flotta-unreachable.json"),
                               (release_lag, "check", lambda home=None: ("régebbi a v0.5.2-nél", None, None)),
                               (release_lag, "describe", lambda *a: "v0.5.1-2-gabc"),
                               (release_lag, "cached_latest", lambda home=None: "v0.5.2")):
            p = mock.patch.object(obj, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.agents = [{"agent": "vilma"}, {"agent": "szervezo"}]
        self.results = {"vilma": {"red": [], "facts": ["képesség: küldés (dry-run) · git ✓"]},
                        "szervezo": {"red": ["küldés a tulajdonosnak NEM MENNE: missing TELEGRAM_BOT_TOKEN",
                                             "git: a /x/.git nem írható — commit nem menne"], "unknown": []}}
        self.measure = lambda e: self.results[e["agent"]]

    def configure(self, url):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "flotta.env").write_text(f"FLOTTA_URL={url}/\nFLOTTA_TOKEN={TOKEN}\n")

    def sweep(self, now=1e9):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            lines = R.sweep(self.agents, now=now, measure=self.measure, host="gondnok")
        return lines, out.getvalue() + err.getvalue()


class Report(Base):
    def test_a_jelentes_a_kepesseg_eredmenyet_viszi_kulccsal(self):
        admin = FakeAdmin(self)
        self.configure(admin.url)
        lines, _ = self.sweep()
        self.assertEqual(len(admin.calls), 1)
        path, headers, body = admin.calls[0]
        self.assertEqual(path, "/api/flotta/v1/report")
        self.assertEqual(headers["X-Mentat-Token"], TOKEN)
        self.assertEqual(body["box"], "gondnok")
        self.assertEqual(body["fleet_version"], F.__version__)
        self.assertEqual(body["release"], {"here": "v0.5.1-2-gabc", "latest": "v0.5.2", "lag": "régebbi a v0.5.2-nél"})
        by = {a["agent"]: a for a in body["agents"]}
        self.assertEqual(by["vilma"]["red"], [])
        self.assertEqual([r["check"] for r in by["szervezo"]["red"]], ["kuldes", "git"])
        self.assertIn("flotta-jelentés: elküldve (2 ágens)", lines)
        self.assertTrue(any("szervezo: képesség PIROS [kozpont]" in ln for ln in lines), lines)
        self.assertFalse(alerts.UNDELIVERED.exists())         # a központ megkapta: nincs tartalék
        self.assertTrue(F.status(1e9 + 60)[2][0].startswith("jelentés: friss"))

    def test_tiz_percenkent_kuld_es_a_force_elore_hozza(self):
        admin = FakeAdmin(self)
        self.configure(admin.url)
        self.sweep(1e9)
        self.sweep(1e9 + 300)
        self.assertEqual(len(admin.calls), 1)
        self.sweep(1e9 + F.REPORT_S + 1)
        self.assertEqual(len(admin.calls), 2)
        self.assertEqual(R.alert_red("vilma", ["todo: `mentat-todo me` hibás: kód 1"]), "kozpont")
        self.sweep(1e9 + F.REPORT_S + 60)
        self.assertEqual(len(admin.calls), 3)
        self.assertEqual(admin.calls[-1][2]["agents"][0]["red"][0]["check"], "todo")

    def test_a_token_nem_kerul_ki_sehova(self):
        admin = FakeAdmin(self, status=500)
        self.configure(admin.url)
        lines, printed = self.sweep()
        doc = doctor_box.alert_route(1e9 + 1)
        blob = json.dumps([lines, printed, doc, F.STATE.read_text(), alerts.UNDELIVERED.read_text()])
        self.assertNotIn(TOKEN, blob)


class NoNetwork(Base):
    def test_lassu_kozpont_korlatos_ido_a_reconcile_nem_torik_fajl_tartalek(self):
        admin = FakeAdmin(self, delay=1.5)
        self.configure(admin.url)
        with mock.patch.object(F, "TIMEOUT_S", 0.3):
            t = time.monotonic()
            lines, _ = self.sweep()
            self.assertLess(time.monotonic() - t, 1.4)
        self.assertTrue(any("flotta-jelentés: HIBA" in ln for ln in lines), lines)
        self.assertTrue(any("szervezo: képesség PIROS [stderr]" in ln for ln in lines), lines)
        self.assertTrue(alerts.UNDELIVERED.read_text().strip())
        probs, _, _, _ = doctor_box.alert_route(time.time())
        self.assertTrue(any("NEM ment ki" in p for p in probs), probs)

    def test_nincs_halozat_elavult_a_doctorban(self):
        self.configure("http://127.0.0.1:9")   # discard port: elutasítja a kapcsolatot
        lines, _ = self.sweep()
        self.assertTrue(any("HIBA" in ln for ln in lines), lines)
        self.assertEqual(F.maybe_report({}, [], "gondnok", 1e9 + 10), "failed")   # a ritmuson belül is: bukott
        probs, _, _, _ = F.status(1e9 + F.STALE_S + 1)   # flotta-menedzser: a Worker elérhetetlensége PIROS
        self.assertTrue(probs and probs[0].startswith("jelentés: elavult"), probs)
        self.assertIn("utolsó sikeres: soha", probs[0])
        self.assertTrue(C.UNREACHABLE.is_file())          # + helyi tartalék-fájl

    def test_varatlan_hiba_sem_toro(self):
        self.configure("http://127.0.0.1:9")
        def boom(*a, **k):
            raise RuntimeError("x")
        self.assertEqual(F.maybe_report({}, ["a"], "gondnok", 1e9, opener=boom), "failed")


class Off(Base):
    def test_beallitas_nelkul_ki_van_kapcsolva_es_a_doctor_mondja(self):
        self.assertIsNone(F.config())
        self.assertEqual(F.maybe_report({}, ["vilma"], "gondnok", 1e9), "off")
        _, warn, _, _ = F.status(1e9)
        self.assertIn("jelentés: kikapcsolva", warn[0])
        lines, _ = self.sweep()
        self.assertFalse(any("flotta-jelentés" in ln for ln in lines), lines)
        self.assertTrue(any("[stderr]" in ln for ln in lines), lines)

    def test_hianyos_beallitas_is_ki(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "flotta.env").write_text("FLOTTA_URL=ftp://x\nFLOTTA_TOKEN=t\n")
        self.assertIsNone(F.config())

    def test_hamarosan_lejaro_box_token_figyelmeztet(self):
        soon = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 3 * 86400))
        admin = FakeAdmin(self, expires=soon)
        self.configure(admin.url)
        F.maybe_report({}, ["vilma"], "gondnok", time.time())
        _, warn, _, _ = F.status(time.time() + 1)
        self.assertTrue(any("box-token" in w and "lejár" in w for w in warn), warn)
        far = FakeAdmin(self)
        self.configure(far.url)
        F.force()
        F.maybe_report({}, ["vilma"], "gondnok", time.time())
        self.assertEqual(F.status(time.time() + 1)[1], [])

    def test_elutasitott_jelentes_piros_doctor_sor(self):
        admin = FakeAdmin(self, status=409, code="cross-box")
        self.configure(admin.url)
        self.sweep()
        probs, _, _, _ = F.status(1e9 + 60)
        self.assertTrue(probs and "ELUTASÍTOTTA (HTTP 409 cross-box)" in probs[0], probs)
        self.assertIn("agents/<név>/release", probs[0])
        ok = FakeAdmin(self)                       # utána egy elfogadott jelentés: a piros eltűnik
        self.configure(ok.url)
        F.force()
        self.sweep(1e9 + 120)
        self.assertEqual(F.status(1e9 + 180)[0], [])

    def test_ritmus_korlat_nem_elutasitas(self):
        admin = FakeAdmin(self, status=429)
        self.configure(admin.url)
        self.sweep()
        self.assertEqual(F.status(1e9 + 60)[0], [])

    def test_https_kell_http_csak_helyben(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        for url, ok in (("http://admin.example.com", False), ("https://admin.example.com", True),
                        ("http://127.0.0.1:8787", True), ("http://localhost:8787", True), ("https://", False)):
            (self.dir / "flotta.env").write_text(f"FLOTTA_URL={url}\nFLOTTA_TOKEN=t\n")
            self.assertEqual(F.config() is not None, ok, url)

    def test_atiranyitast_nem_kovet_a_token_nem_megy_tovabb(self):
        other = FakeAdmin(self)
        admin = FakeAdmin(self, status=302, location=f"{other.url}/api/flotta/v1/report")
        self.configure(admin.url)
        lines, _ = self.sweep()
        self.assertEqual(len(admin.calls), 1)
        self.assertEqual(other.calls, [])                   # a token nem ment át a másik célhoz
        self.assertTrue(any("flotta-jelentés: HIBA" in ln for ln in lines), lines)
        self.assertIn("302", F._load().get("last_info", ""))

    def test_ismeretlen_ha_meg_nem_probalt(self):
        self.configure("http://127.0.0.1:9")
        self.assertIn("jelentés: ismeretlen", F.status(1e9)[3][0])


class Keys(unittest.TestCase):
    def test_a_piros_sorok_stabil_kulcsot_kapnak(self):
        cases = {"küldés a tulajdonosnak NEM MENNE: kód 1": "kuldes", "küldés: nincs telepítve a send.mjs (a)": "kuldes",
                 "todo: `mentat-todo me` hibás: x": "todo",
                 "todo-ébresztés: 12 perce nincs sikeres todo-poll (utolsó: 10:00)": "todo-ebresztes",
                 "todo-ébresztés KI: todo token x másnak is olvasható": "todo-ebresztes", "saját állapot nem olvasható: a.json (ValueError)": "allapot",
                 "git: `git status` hibás": "git", "képesség: nincs meg az ágens repója (/x)": "repo",
                 "Telegram-küldés TILTVA: titok-kapu": "kapu",
                 "a unit env-jében nincs TELEGRAM_BOT_TOKEN (betöltve: semmi)": "token",
                 "a send.mjs 3× futott token nélkül az elmúlt 24 órában": "nema-kuldes", "valami más": "egyeb"}
        for line, key in cases.items():
            self.assertEqual(F.check_key(line), key, line)


if __name__ == "__main__":
    unittest.main()
