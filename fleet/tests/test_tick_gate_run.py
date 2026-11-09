"""a kapu egy tüzelése végig (nyom, kihagyás, beküldés, foglaltság, elveszett beküldés) és az egészség."""
import _hermetic  # noqa: F401
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fleet import kepesseg, liveness, signals, tick_gate_health as th, tick_gate_inject as inj
from fleet import tick_gate_run as run

NOW = 1_800_000_000.0


def obs(reasons=(), activity=None):
    return lambda cfg, gate, **kw: {"reasons": list(reasons), "activity": bool(reasons) if activity is None else activity,
                                    "error": None, "commit": {"seen": ["x"]}, "busy": None}


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.home, True)
        self.e = {"agent": "rel", "session": "rel", "workdir": str(self.home / "rel"), "status": "active",
                  "tick_gate": {"tick_cmd": "python3 entry.py --trigger hourly"}}
        self.sent = []
        p = mock.patch.object(run, "transcript_mtime", return_value=None); p.start(); self.addCleanup(p.stop)

    def send(self, session, line):
        self.sent.append((session, line)); return True, "beküldve"

    def once(self, now, o, busy=lambda e, n: None):
        return run.run_once(self.e, home=self.home, now=now, observe=o, busy=busy, send=self.send)

    def trace(self):
        return json.loads(run.trace_path(self.e, self.home).read_text())


class RunOnce(Base):
    def test_munka_egyszer_kuld_a_registry_parancsat(self):
        r = self.once(NOW, obs(["új PR"]))
        self.assertEqual(r["action"], "inject")
        self.assertEqual(self.sent, [("rel", "python3 entry.py --trigger hourly")])
        t = self.trace()
        self.assertEqual((t["fired_at"], t["checked_at"], t["injected_at"], t["seen"]), (NOW, NOW, NOW, ["x"]))

    def test_ures_kor_nem_kuld_es_tetlenben_a_koztes_tuzeles_http_nelkul(self):
        calls = []
        def o(cfg, gate, **kw):
            calls.append(1); return obs()(cfg, gate)
        self.assertEqual(self.once(NOW, o)["action"], "idle")
        r = self.once(NOW + 1800, o)                                    # tétlen: 60 perc a köv.
        self.assertEqual((r["action"], len(calls)), ("skip", 1))
        self.assertEqual(self.trace()["fired_at"], NOW + 1800)          # a timer él: nyom van
        self.assertEqual(self.once(NOW + 3600, o)["action"], "idle")
        self.assertEqual((len(calls), self.sent), (2, []))

    def test_foglalt_ugynok_nem_kap_es_kovetkezo_tuzelesnel_igen(self):
        r = self.once(NOW, obs(["új PR"]), busy=lambda e, n: "az ágens éppen dolgozik")
        self.assertEqual((r["action"], self.sent), ("busy", []))
        self.assertNotIn("seen", self.trace())                          # a munka nem veszett el
        self.assertEqual(self.once(NOW + 1800, obs(["új PR"]))["action"], "inject")

    def test_elveszett_bekuldes_ujra(self):
        self.once(NOW, obs(["új PR"]))
        with mock.patch.object(run, "transcript_mtime", return_value=NOW - 999):
            r = self.once(NOW + 1800, obs())
        self.assertEqual(r["action"], "inject")
        self.assertIn("nem érkezett meg", r["why"][0])

    def test_romlott_nyom_es_hibas_elooellenorzo_nem_dob(self):
        p = run.trace_path(self.e, self.home); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"injected_at": "x", "next_due_at": {}}))
        self.assertEqual(self.once(NOW, obs())["action"], "idle")
        bad = mock.Mock(returncode=0, stdout=json.dumps({"work": True, "reasons": 1}))
        self.assertIn("hibás alak", run.observe_cmd(["/bin/true"], run=lambda *a, **k: bad)["error"])

    def test_kapu_nelkul_semmi(self):
        self.e.pop("tick_gate")
        self.assertEqual(self.once(NOW, obs(["x"]))["action"], "none")


class Inject(unittest.TestCase):
    def test_pane_orok(self):
        ok = "…\n  ⏵⏵ bypass permissions on (shift+tab to cycle)\n"
        self.assertIsNone(inj.pane_busy(ok))
        self.assertIn("ablak", inj.pane_busy("Do you want to proceed?\n❯ 1. Yes\n  2. No\n" + ok))
        self.assertIn("dolgozik", inj.pane_busy("✻ Working… (esc to interrupt)\n" + ok))
        self.assertIn("promptja", inj.pane_busy("$ \n"))
        self.assertIsNotNone(inj.pane_busy(None))

    def test_send_literal_es_kulon_enter(self):
        calls = []
        def r(cmd):
            calls.append(cmd)
            out = "x\nbypass permissions on\n" if "capture-pane" in cmd else ""
            return mock.Mock(returncode=0, stdout=out)
        self.assertEqual(inj.send("rel", "python3 entry.py --trigger hourly", run=r)[0], True)
        self.assertEqual(calls[1], ["tmux", "send-keys", "-t", "=rel:", "-l", "--", "python3 entry.py --trigger hourly"])
        self.assertEqual(calls[2], ["tmux", "send-keys", "-t", "=rel:", "Enter"])


class Health(Base):
    def write(self, **kv):
        p = run.trace_path(self.e, self.home); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(kv))

    def test_tetlen_de_ellenorzo_zold(self):
        self.write(fired_at=NOW - 600, checked_at=NOW - 600, interval_s=3600, decision="idle")
        v = th.verdict(self.e, self.home, NOW)
        self.assertEqual(v["state"], "ok"); self.assertIn("tétlen", v["detail"])

    def test_elakadt_timer_piros(self):
        self.write(fired_at=NOW - 2 * 1800 - 60, checked_at=NOW - 4000, interval_s=3600)
        self.assertIn("nem tüzelt", th.verdict(self.e, self.home, NOW)["detail"])

    def test_tuzel_de_az_ellenorzo_nem_fut_le_piros(self):
        self.write(fired_at=NOW - 60, checked_at=NOW - 3 * 3600, interval_s=3600)
        v = th.verdict(self.e, self.home, NOW)
        self.assertEqual(v["state"], "red"); self.assertIn("nem fut le", v["detail"])

    def test_tartos_hiba_es_ehezo_munka_piros(self):
        self.write(fired_at=NOW, checked_at=NOW, interval_s=1800, errors=3, error="github: x")
        self.assertEqual(th.verdict(self.e, self.home, NOW)["state"], "red")
        self.write(fired_at=NOW, checked_at=NOW, interval_s=1800, pending_since=NOW - 4 * 3600)
        self.assertIn("vár", th.verdict(self.e, self.home, NOW)["detail"])

    def test_nincs_nyom_piros_friss_telepitesnel_pending(self):
        self.assertEqual(th.verdict(self.e, self.home, NOW)["state"], "red")
        t = self.home / ".config" / "systemd" / "user" / "fleet-gate-rel.timer"
        t.parent.mkdir(parents=True); t.write_text("x"); os.utime(t, (NOW - 60, NOW - 60))
        self.assertEqual(th.verdict(self.e, self.home, NOW)["state"], "pending")

    def test_overlay_a_74_tick_signalra(self):
        self.write(fired_at=NOW - 60, checked_at=NOW - 60, interval_s=3600, decision="idle")
        t = th.overlay(self.e, self.home, NOW, {"owner": "session", "period_s": 1800, "_at": None, "age_s": None})
        self.assertEqual((t["owner"], t["period_s"], t["age_s"]), ("gate", 3600, 60))
        self.assertEqual(th.overlay({"agent": "x"}, self.home, NOW, {"owner": "none"}), {"owner": "none"})

    def test_bekotes_signals_kepesseg_rearm(self):
        self.write(fired_at=NOW - 60, checked_at=NOW - 60, interval_s=3600, decision="idle")
        with mock.patch.object(Path, "home", return_value=self.home):
            s = signals.schedule_signal(self.e, None, None, now=NOW)
        self.assertEqual((s.state, s.data["owner"]), ("armed", "gate"))
        self.assertEqual(th.kepesseg_line(self.e, self.home)[0], "ok")
        from fleet.flotta_report import check_key
        self.assertEqual(check_key("tick-kapu: a timer 99 perce nem tüzelt"), "tick")
        m = {"signals": {"schedule": {"data": {"tick_age_s": 99999}}}, "transcript_age_s": 9999, "rearm_age_s": None}
        self.assertIsNone(liveness.rearm_reason({**self.e, "proactive": True, "loop_cmd": "/x"}, m))
        self.assertIsNotNone(liveness.rearm_reason({"agent": "y", "proactive": True, "loop_cmd": "/x"}, m))
        self.assertTrue(callable(kepesseg.check))


if __name__ == "__main__":
    unittest.main()
