"""flotta-menedzser: desktop-paritás és a lefutott tick jele.

- a saját gépen futó (`supervision: none`) tag is mérhető (todo, állapot, git; híd és unit nélkül),
  a session `fleet flotta-report`-tal jelent; újraindító lépés rá nem értelmezhető;
- a menedzser a saját incidensét nem javítja (engedély-mátrix);
- az utolsó LEFUTOTT tick csak a `last-tick.json`-ból jön; a régi nyom piros `tick`; a postcheck
  csak a processz indulása utáni tickkel zöld.
"""
import _hermetic  # noqa: F401
import io
import os
import shutil
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from fleet import flotta_now, flotta_report, kepesseg, tick_signal
from test_repair_exec import Base, FakeWorker, X


def _agent(wd: Path, **kw) -> dict:
    return {"agent": "laptop", "host": "alfa", "workdir": str(wd), "supervision": "none", "status": "active", **kw}


class TickSignal(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.wd, True)
        (self.wd / "data" / "state").mkdir(parents=True)

    def tick_at(self, t: float):
        p = self.wd / "data" / "state" / "last-tick.json"
        p.write_text("{}"); os.utime(p, (t, t))

    def test_csak_a_tick_nyoma_szamit_es_a_regi_piros(self):
        e = _agent(self.wd, proactive=True, tick_period_s=900)
        now = time.time()
        t = tick_signal.executed(e, now=now)
        self.assertEqual((t["owner"], t["last_tick_at"]), ("session", None))
        self.assertTrue(tick_signal.missing(t))                     # ütemezett, nincs nyom: mérhetetlen = PIROS
        self.assertTrue(tick_signal.stale(t))
        self.tick_at(now - 3600)
        self.assertTrue(tick_signal.stale(tick_signal.executed(e, now=now)))
        self.tick_at(now - 60)
        t = tick_signal.executed(e, now=now)
        self.assertFalse(tick_signal.stale(t))
        self.assertTrue(tick_signal.after(t, now - 120)); self.assertFalse(tick_signal.after(t, now - 30))

    def report_row(self, e):
        with mock.patch.object(flotta_report, "_entries", return_value={"laptop": e}):
            return flotta_report.build({"laptop": {"at": time.time(), "red": [], "ok": ["git"]}}, ["laptop"], "alfa")["agents"][0]

    def test_utemezett_agens_tick_nyom_nelkul_piros_tick(self):
        # a menedzser-ágens mérése (11-08): a régi tick sosem írt last-tick.json-t → a halott loop zöldnek látszott
        for key, val in (("proactive", True), ("loop_cmd", "/loop 15m /tick"), ("tick_period_s", 900)):
            row = self.report_row(_agent(self.wd, **{key: val}))
            self.assertEqual([r["check"] for r in row["red"]], ["tick"], key)
            self.assertIn("nincs tick-nyom", row["red"][0]["detail"])
            self.assertIsNone(row["tick"]["last_tick_at"])

    def row_started(self, e, started):
        with mock.patch.object(flotta_report, "_process_started", return_value=started):
            return self.report_row(e)

    def test_friss_indulas_a_turelmi_idon_belul_pending_nem_incidens(self):
        now = time.time()
        row = self.row_started(_agent(self.wd, tick_period_s=900), now - 60)
        self.assertEqual(row["red"], [])
        self.assertTrue(any("első tickre vár" in u for u in row["unknown"]))
        # a régi, indulás ELŐTTI nyom sem bizonyít: ugyanúgy pending
        self.tick_at(now - 120)
        self.assertEqual(self.row_started(_agent(self.wd, tick_period_s=900), now - 60)["red"], [])

    def test_a_turelmi_ido_utan_nyom_nelkul_piros(self):
        now = time.time()
        row = self.row_started(_agent(self.wd, tick_period_s=900), now - (900 + tick_signal.GRACE_MARGIN_S + 60))
        self.assertEqual([r["check"] for r in row["red"]], ["tick"])
        self.assertIn("nincs tick-nyom az indulás óta", row["red"][0]["detail"])

    def test_indulas_utani_nyom_zold(self):
        now = time.time()
        self.tick_at(now - 30)
        row = self.row_started(_agent(self.wd, tick_period_s=900), now - 600)
        self.assertEqual(row["red"], []); self.assertEqual(row["unknown"], [])

    def test_periodus_nelkuli_loop_90_perces_alappal(self):
        now = time.time()
        e = _agent(self.wd, proactive=True)
        self.assertEqual(self.row_started(e, now - 80 * 60)["red"], [])                  # 80 < 90 + 15 perc
        self.assertEqual([r["check"] for r in self.row_started(e, now - 110 * 60)["red"]], ["tick"])

    def test_utemezes_nelkuli_agens_nyom_nelkul_nem_ertelmezheto(self):
        row = self.report_row(_agent(self.wd))
        self.assertEqual(row["red"], [])
        self.assertEqual(row["tick"]["owner"], "none")

    def test_ütemezés_nélkül_soha_nem_piros(self):
        self.tick_at(time.time() - 99999)
        self.assertFalse(tick_signal.stale(tick_signal.executed(_agent(self.wd))))

    def test_a_jelentes_viszi_a_tick_et_es_a_piros_tick_kulcsot(self):
        e = _agent(self.wd, proactive=True, tick_period_s=900)
        self.tick_at(time.time() - 7200)
        with mock.patch.object(flotta_report, "_entries", return_value={"laptop": e}):
            rep = flotta_report.build({"laptop": {"at": time.time(), "red": [], "ok": ["git"]}}, ["laptop"], "alfa")
        row = rep["agents"][0]
        self.assertEqual(row["tick"]["owner"], "session")
        self.assertNotIn("_at", row["tick"])
        self.assertEqual([r["check"] for r in row["red"]], ["tick"])


class Desktop(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.wd, True)

    def test_a_desktop_tag_merheto_kerésre_unit_es_hid_nelkul(self):
        e = _agent(self.wd)
        self.assertEqual(kepesseg.check(e, Path.home()), {"red": [], "unknown": [], "ok": []})   # a timer nem méri
        r = kepesseg.check(e, Path.home(), desktop=True)
        self.assertTrue(r["red"] or r["ok"])                        # a session kérésére igen
        self.assertFalse(any(x.startswith("küldés") for x in r["red"] + r["ok"]))   # hídja nincs

    def test_flotta_report_beallitas_nelkul_2_es_merni_mer(self):
        e = _agent(self.wd)
        with mock.patch.object(flotta_report, "config", return_value=None):
            rc, msg = flotta_now.report_now(agents=[e], host="alfa")
        self.assertEqual(rc, 2); self.assertIn("flotta.env", msg)


class Permissions(Base):
    def test_a_sajat_incidenset_nem_javitja(self):
        from fleet import incident_cli
        incident_cli.save_claim("i1", {"incident": "i1", "target": "agent:munkas", "fence": 7, "claim": "x" * 20,
                                       "attempt_until": "2999-01-01T00:00:00Z", "as": "munkas"})
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.USAGE)
        self.assertEqual(w.calls, [])
        self.assertIn("saját incidensét", self.out)

    def test_desktop_celra_ujrainditas_nem_ertelmezheto(self):
        agents = [{"agent": "munkas", "host": "alfa", "supervision": "none"}]
        w = FakeWorker(self)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = X.run("i1", "doctor-fix", "munkas", None, worker=w, steps=self.steps, host="alfa", agents=agents, say=print)
        self.assertEqual(rc, X.USAGE); self.assertEqual(w.calls, [])
        self.assertIn("saját gépen", out.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(X.run("i1", "doctor", "munkas", None, worker=w, steps=self.steps, host="alfa", agents=agents,
                                   say=lambda s: None), X.OK)


class CodexReviewFixes(Base):
    """A Codex-review valós találatai (11-08) — mindegyik egy regressziós teszt."""

    def test_a_sajat_zar_kerulouta_lejarat_vagy_atiras_utan_nem_el(self):
        from fleet import maintenance
        maintenance.lock("munkas", 5, own=True)
        self.assertFalse(maintenance.is_locked("munkas"))           # ebben a processzben a saját zárunk
        maintenance._root().joinpath("munkas").write_text(str(time.time() + 600))   # egy másik gazda átírta
        self.assertTrue(maintenance.is_locked("munkas"))
        maintenance.unlock("munkas")

    def test_az_atvetel_atomikusan_irodik_0600(self):
        from fleet import incident_cli
        p = incident_cli.save_claim("i9", {"claim": "x"})
        self.assertEqual(oct(p.stat().st_mode & 0o777), "0o600")
        self.assertEqual([x.name for x in p.parent.iterdir() if x.name.endswith(".tmp")], [])

    def test_doctor_ismert_hibaval_de_nem_merheto_sorral_nem_eldontott(self):
        from fleet import repair_steps
        rep = {"agent": "munkas", "health": "unhealthy", "problems": ["x"], "unknown": ["y"], "pending": []}
        with mock.patch("fleet.doctor.doctor", return_value=[rep]):
            self.assertEqual(repair_steps.doctor({"agent": "munkas"})[2], "undecidable")
        with mock.patch("fleet.doctor.doctor", return_value=[dict(rep, unknown=[])]):
            self.assertEqual(repair_steps.doctor({"agent": "munkas"})[2], "decided")

    def test_utolagos_registry_meres_hibaja_bizonytalan_de_az_eredmeny_megy(self):
        calls = iter(["h1"])
        def digest():
            try:
                return next(calls)
            except StopIteration:
                raise OSError("eltűnt")
        self.steps.registry_digest = digest
        w = FakeWorker(self)
        self.run_x("doctor-fix", worker=w)
        self.assertEqual(w.names()[-1], "result")
        self.assertEqual(w.calls[-1][1]["outcome"], "uncertain")


class CodexReview2(Base):
    """A második Codex-kör (11-08) végrehajtó-oldali találatai."""

    def marker(self):
        return self.dir / "repair" / "maint-munkas"

    def test_osszeomlas_utani_kezi_zarat_nem_veszi_at_es_nem_torli(self):
        from fleet import maintenance
        maintenance.lock("munkas", 30)                       # egy összeomlott végrehajtó zárja…
        self.marker().parent.mkdir(parents=True, exist_ok=True)
        self.marker().write_text("1.0")                      # …de a jelölője már NEM ezt a zárat jelöli
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertTrue(maintenance.is_locked("munkas"))     # az emberi zár maradt
        self.marker().write_text(maintenance.content("munkas"))   # most a jelölő a zárat jelöli: átvehető
        self.assertEqual(self.run_x("doctor-fix", worker=FakeWorker(self)), X.OK)
        self.assertFalse(maintenance.is_locked("munkas")); self.assertFalse(self.marker().exists())

    def test_futas_kozben_vett_kezi_zar_a_vegen_is_marad(self):
        from fleet import maintenance
        def fix(e):
            maintenance.lock("munkas", 30)                   # egy ember közben kézzel zárt
            return "ok", "kész", None
        self.steps.doctor_fix = fix
        self.assertEqual(self.run_x("doctor-fix", worker=FakeWorker(self)), X.OK)
        self.assertTrue(maintenance.is_locked("munkas"))
        self.assertFalse(self.marker().exists())
        maintenance.unlock("munkas")

    def test_ha_a_zar_feloldasa_bukik_a_jelolo_akkor_is_torlodik(self):
        from fleet import maintenance
        with mock.patch.object(maintenance, "release_own", side_effect=OSError("ro")):
            with self.assertRaises(OSError):
                self.run_x("doctor-fix", worker=FakeWorker(self))
        self.assertFalse(self.marker().exists())
        maintenance.unlock("munkas")

    def test_a_zar_atomikusan_irodik(self):
        from fleet import maintenance
        maintenance.lock("munkas", 5)
        root = maintenance._root()
        self.assertEqual([p.name for p in root.iterdir() if p.name.endswith(".tmp")], [])
        self.assertGreater(float(maintenance.content("munkas")), time.time())
        maintenance.unlock("munkas")

    def test_nem_merheto_registry_kimondva(self):
        self.steps.registry_digest = lambda: None
        w = FakeWorker(self)
        self.run_x("doctor-fix", worker=w)
        self.assertIn("nem mérhető", self.out)
        self.assertIn("registry-tripwire: nem mérhető", w.calls[-1][1]["summary"])


class TickLockCondition(unittest.TestCase):
    def test_masik_execcondition_mellett_is_bekerul_es_idempotens(self):
        from fleet.tick_schedule import with_lock_condition
        unit = "[Service]\nType=oneshot\nExecCondition=/bin/true\nExecStart=/bin/x\n"
        once = with_lock_condition(unit, "munkas")
        self.assertIn("/.config/fleet/maintenance/munkas", once)
        self.assertIn("ExecCondition=/bin/true", once)
        self.assertEqual(with_lock_condition(once, "munkas"), once)
        with self.assertRaises(ValueError):
            with_lock_condition(unit, "rossz név;x")

    def test_a_jelentes_viszi_a_desktop_jelet(self):
        wd = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, wd, True)
        e = _agent(wd)
        with mock.patch.object(flotta_report, "_entries", return_value={"laptop": e}):
            rep = flotta_report.build({"laptop": {"at": time.time(), "red": [], "ok": ["git"]}}, ["laptop"], "alfa")
        self.assertIs(rep["agents"][0]["desktop"], True)


if __name__ == "__main__":
    unittest.main()
