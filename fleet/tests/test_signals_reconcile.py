"""A négy jel tiszta ítéletei és a reconcile döntései. Nincs systemd, nincs
/proc: minden bemenet kézzel adott, ezért minden ág bejárható — beleértve
azt is, hogy a kapu tud pirosat mutatni."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# HERMETIKUS: a reconcile a maintenance.is_locked()-en át VALÓDI zárfájlokat
# olvasna (~/.config/fleet/maintenance/). 2026-09-23-án egy kiadási kapu
# ezen pirosodott ki: két élő zár volt a boxon, és a fixture egy létező ágens
# nevét viselte. A tesztnek saját zár-könyvtára van, a fixture-név pedig nem
# ütközhet flotta-névvel.
import os, tempfile  # noqa: E402
_LOCKS = tempfile.mkdtemp(prefix="fleet-test-locks-")
os.environ["FLEET_MAINTENANCE_DIR"] = _LOCKS

from fleet import signals, reconcile, registry  # noqa: E402
from fleet.postcheck import postcheck_verdict  # noqa: E402

NOW = 1_800_000_000.0


def _procs():
    claude = ["/home/t/.local/bin/claude", "--dangerously-skip-permissions", "--remote-control", "probe", "--model", "opus"]
    return [
        {"pid": 10, "ppid": 1, "argv": ["/usr/bin/tmux", "new-session", "-d", "-s", "x", "/bin/sh", "-c", " ".join(claude)], "rss_mb": 3, "started_s": NOW - 5000},
        {"pid": 11, "ppid": 10, "argv": claude, "rss_mb": 300, "started_s": NOW - 4000},
        {"pid": 12, "ppid": 11, "argv": ["bun", "run", "--cwd", "/x/telegram", "start"], "rss_mb": 9, "started_s": NOW - 3900},
        {"pid": 13, "ppid": 12, "argv": ["/home/t/.bun/bin/bun", "server.ts"], "rss_mb": 70, "started_s": NOW - 3900},
        {"pid": 20, "ppid": 1, "argv": ["/home/t/.local/bin/claude", "--dangerously-skip-permissions", "--remote-control", "other"], "rss_mb": 200, "started_s": NOW - 100},
    ]


def _entry(**kw):
    b = {"agent": "probe-agent", "rc_name": "probe", "workdir": "/x", "proactive": True,
         "tick_period_s": 61200, "loop_cmd": "/x:startup", "bridge": {"unit": "probe-telegram-bridge.service"}}
    b.update(kw)
    return registry.normalize(b)


class TestProcess(unittest.TestCase):
    def test_finds_binary_not_wrapper(self):
        p = signals.find_agent_process(_entry(), _procs())
        self.assertEqual(p["pid"], 11)

    def test_restart_overlap_picks_the_newest_claude(self):
        procs = _procs() + [{"pid": 9, "ppid": 1, "argv": _procs()[1]["argv"], "rss_mb": 50,
                             "started_s": NOW - 1}]
        self.assertEqual(signals.find_agent_process(_entry(), procs)["pid"], 9)

    def test_missing_rc_name_is_down_and_no_proc_is_unknown(self):
        self.assertEqual(signals.process_signal(_entry(rc_name="nope"), _procs()).state, "down")
        self.assertEqual(signals.process_signal(_entry(), []).state, signals.UNKNOWN)

    def test_pollers_only_under_agent(self):
        self.assertEqual([p["pid"] for p in signals.plugin_pollers(11, _procs())], [13])
        self.assertEqual(signals.plugin_pollers(20, _procs()), [])
        self.assertEqual(signals.plugin_pollers(None, _procs()), [])


class TestSchedule(unittest.TestCase):
    def v(self, **kw):
        base = dict(proactive=True, tick_age=None, period_s=3600, process_started_s=NOW - 10_000, now=NOW)
        base.update(kw)
        return signals.schedule_verdict(**base)[0]

    def test_vocabulary(self):
        self.assertEqual(self.v(proactive=False), "n/a")
        # a türelmi idő után a nyom-nélküliség 'stale', nem 'unknown'
        self.assertEqual(self.v(tick_age=None), "stale")
        self.assertEqual(self.v(tick_age=None, process_started_s=None), signals.UNKNOWN)
        self.assertEqual(self.v(tick_age=None, process_started_s=NOW - 60), "pending")
        self.assertEqual(self.v(tick_age=1000), "armed")
        self.assertEqual(self.v(tick_age=5399), "armed")     # 1.5 × 3600 = 5400
        self.assertEqual(self.v(tick_age=5401), "stale")
        self.assertEqual(self.v(tick_age=5401, process_started_s=NOW - 60), "pending")


class TestChannel(unittest.TestCase):
    def test_vocabulary(self):
        v = signals.channel_verdict
        self.assertEqual(v(has_bridge=False, health_age_s=None, conflicts_10min=None)[0], "n/a")
        self.assertEqual(v(has_bridge=True, health_age_s=10, conflicts_10min=3)[0], "conflict")
        self.assertEqual(v(has_bridge=True, health_age_s=None, conflicts_10min=None)[0], signals.UNKNOWN)
        self.assertEqual(v(has_bridge=True, health_age_s=None, conflicts_10min=0)[0], signals.UNKNOWN)
        self.assertEqual(v(has_bridge=True, health_age_s=900, conflicts_10min=0)[0], "stale")
        self.assertEqual(v(has_bridge=True, health_age_s=30, conflicts_10min=0)[0], "ok")


class TestRC(unittest.TestCase):
    def _lines(self):
        return [
            '{"timestamp":"2026-09-03T10:00:00Z","x":"Remote Control disconnected — signed-in claude.ai account changed"}',
            '{"timestamp":"2026-09-16T20:08:00Z","x":"Remote Control connected"}',
        ]

    def test_only_events_after_process_start_count(self):
        ev = signals.rc_events(self._lines())
        self.assertEqual(len(ev), 2)
        started_after_both = ev[1][0] + 100
        self.assertEqual(signals.rc_verdict(ev, started_after_both)[0], signals.UNKNOWN)
        started_between = ev[0][0] + 100
        self.assertEqual(signals.rc_verdict(ev, started_between)[0], "connected")
        started_before = ev[0][0] - 100
        self.assertEqual(signals.rc_verdict(ev, started_before)[0], "connected")   # az utolsó számít
        self.assertEqual(signals.rc_verdict(ev[:1], started_before)[0], signals.UNKNOWN)   # a leszakadás nem állapot
        self.assertEqual(signals.rc_verdict(ev, None)[0], signals.UNKNOWN)


def _measure(proc="up", pollers=(), channel="ok", rc="connected", sched="armed",
             rss=300, t_age=1200.0, tick_age=100.0, period=61200):
    return {"agent": "probe-agent", "session_id": "s", "transcript_age_s": t_age,
            "pollers": list(pollers),
            "signals": {"process": {"state": proc, "detail": "", "data": {"pid": 11, "rss_mb": rss, "started_s": NOW - 4000}},
                        "schedule": {"state": sched, "detail": "", "data": {"tick_age_s": tick_age, "period_s": period}},
                        "channel": {"state": channel, "detail": "409", "data": {}},
                        "rc": {"state": rc, "detail": "", "data": {}},
                        "auth": {"state": "ok", "detail": "", "data": {}}}}


class TestDecide(unittest.TestCase):
    def d(self, entry=None, m=None, st=None, unit_active=True, locked=False):
        return reconcile.decide(entry or _entry(), m or _measure(), st or {"restarts": []},
                                unit_active=unit_active, locked=locked, now=NOW)

    def test_healthy_is_noop(self):
        self.assertEqual(self.d()[0][0], "noop")

    def test_dormant_running_is_stopped_and_dormant_stopped_is_noop(self):
        self.assertEqual(self.d(_entry(status="dormant"))[0][0], "stop")
        self.assertEqual(self.d(_entry(status="dormant"), _measure(proc="down"), unit_active=False)[0][0], "noop")

    def test_lock_quarantine_and_corrupt_state_skip_everything(self):
        self.assertEqual(self.d(m=_measure(proc="down"), locked=True)[0][0], "skip:lock")
        self.assertEqual(self.d(_entry(status="dormant"), locked=True)[0][0], "skip:lock")
        self.assertEqual(self.d(m=_measure(proc="down"), st={"restarts": [], "quarantined": True})[0][0], "skip:quarantine")
        self.assertEqual(self.d(m=_measure(proc="down"), st=reconcile.CORRUPT)[0][0], "skip:state-corrupt")
        self.assertEqual(self.d(m=_measure(proc="down"), unit_active=None)[0][0], "skip:unmeasurable")

    def test_bridge_restart_is_budgeted(self):
        st = {"restarts": [], "bridge_restarts": [NOW - 10, NOW - 20, NOW - 30]}
        acts = [a for a, _ in self.d(m=_measure(channel="conflict"), st=st)]
        self.assertTrue(acts[0].startswith("alert:bridge-budget"))

    def test_pending_postcheck_triggers_recheck(self):
        st = {"restarts": [NOW - 200], "pending_postcheck": {"restart_at": NOW - 200}}
        self.assertEqual(self.d(st=st)[0][0], "recheck")

    def test_down_restarts_within_budget_then_alerts(self):
        self.assertEqual(self.d(m=_measure(proc="down"))[0][0], "restart")
        self.assertEqual(self.d(m=_measure(proc="down"), unit_active=False)[0][0], "start")
        exhausted = {"restarts": [NOW - 100, NOW - 200, NOW - 300]}
        self.assertTrue(self.d(m=_measure(proc="down"), st=exhausted)[0][0].startswith("alert:budget"))
        old = {"restarts": [NOW - 4000, NOW - 4100, NOW - 4200]}
        self.assertEqual(self.d(m=_measure(proc="down"), st=old)[0][0], "restart")

    def test_unmeasurable_is_a_skip_not_a_restart(self):
        self.assertEqual(self.d(m=_measure(proc=signals.UNKNOWN))[0][0], "skip:unmeasurable")

    def test_poller_beats_bridge_restart(self):
        acts = self.d(m=_measure(pollers=[13], channel="conflict"))
        self.assertEqual([a for a, _ in acts], ["kill_pollers"])
        acts = self.d(m=_measure(channel="conflict"))
        self.assertEqual([a for a, _ in acts], ["restart_bridge"])

    def test_rc_disconnected_only_alerts(self):
        acts = [a for a, _ in self.d(m=_measure(rc="disconnected"))]
        self.assertEqual(len(acts), 1)
        self.assertTrue(acts[0].startswith("alert:rc:"))

    def test_memory_reports_by_default(self):
        acts = [a for a, _ in self.d(m=_measure(rss=1300))]
        self.assertTrue(acts[0].startswith("alert:memory"))

    def test_silence_alert_after_12_periods(self):
        acts = [a for a, _ in self.d(m=_measure(sched="stale", tick_age=61200 * 13))]
        self.assertTrue(any(a.startswith("alert:silence") for a in acts))
        # 2 periódus csend: még nem riasztás — tétlen ágensnél a reconcile
        # újrahúzza a loopot (a liveness tick-őre beolvadt), dolgozónál nem nyúl hozzá
        acts = [a for a, _ in self.d(m=_measure(sched="stale", tick_age=61200 * 2))]
        self.assertEqual(acts, ["rearm"])
        acts = [a for a, _ in self.d(m=_measure(sched="stale", tick_age=61200 * 2, t_age=60.0))]
        self.assertEqual(acts, ["noop"])


class TestPostcheck(unittest.TestCase):
    def v(self, m, restart_at=NOW - 4500, grace_over=False):
        return postcheck_verdict(m, restart_at=restart_at, now=NOW, grace_over=grace_over)[0]

    def test_three_states(self):
        self.assertEqual(self.v(_measure()), "ok")
        for bad in (_measure(proc="down"), _measure(pollers=[13]), _measure(channel="conflict"),
                    _measure(rc="disconnected")):
            self.assertEqual(self.v(bad), "failed")
        self.assertEqual(self.v(_measure(sched="stale")), "pending")
        self.assertEqual(self.v(_measure(sched="stale"), grace_over=True), "failed")
        self.assertEqual(self.v(_measure(channel="stale")), "pending")
        self.assertEqual(self.v(_measure(channel=signals.UNKNOWN), grace_over=True), "failed")
        self.assertEqual(self.v(_measure(rc=signals.UNKNOWN)), "ok")

    def test_old_process_generation_is_a_failure(self):
        # a processz NOW-4000-kor indult; a restart NOW-100-kor → a régi processz fut
        self.assertEqual(self.v(_measure(), restart_at=NOW - 100), "failed")


class TestReconcileObserve(unittest.TestCase):
    def test_observe_mode_never_executes(self):
        import os, tempfile
        e = _entry(host="probe-host")
        calls = []
        with tempfile.TemporaryDirectory() as d:
            orig_dirs = (reconcile.STATE_DIR, reconcile.LOCK_PATH)
            reconcile.STATE_DIR = Path(d); reconcile.LOCK_PATH = Path(d) / "lock"
            try:
                os.environ["FLEET_HOST"] = "probe-host"
                r = reconcile.reconcile(observe=True, agents=[e], measure=lambda _e: _measure(proc="down"),
                                        now=NOW, unit_active=lambda u: True,
                                        execute_fn=lambda *a, **k: calls.append(a))
                self.assertEqual(list(Path(d).glob("*.json")), [])   # observe nem ír állapotot
            finally:
                reconcile.STATE_DIR, reconcile.LOCK_PATH = orig_dirs
                os.environ.pop("FLEET_HOST", None)
        self.assertEqual(r["mode"], "OBSERVE")
        self.assertEqual(calls, [])
        self.assertTrue(any("restart" in line and "nem hajtom végre" in line for line in r["lines"]))

    def test_unknown_host_only_observes(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            # A gépet NEM a környezet dönti el: a boxon a ~/.config/fleet/host és a
            # hostnév is "alpha"-t ad, ezért ott ez a teszt ACT-ot kapott (Gamma
            # kapuja, 2026-09-23). Az "ismeretlen host" itt injektált tény.
            orig = (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host)
            reconcile.STATE_DIR = Path(d); reconcile.LOCK_PATH = Path(d) / "lock"
            reconcile.controller_is_us = lambda: True
            reconcile.local_host = lambda: None
            try:
                r = reconcile.reconcile(agents=[_entry(host="nowhere")], measure=lambda _e: _measure(), now=NOW,
                                        unit_active=lambda u: True, execute_fn=lambda *a, **k: None)
            finally:
                reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host = orig
        self.assertEqual(r["mode"], "OBSERVE")


if __name__ == "__main__":
    unittest.main()


class TestLockIsHermetic(unittest.TestCase):
    def test_lock_in_own_dir_is_seen_and_real_dir_is_not_read(self):
        from fleet import maintenance
        self.assertEqual(str(maintenance._root()), _LOCKS)
        self.assertFalse(maintenance.is_locked("probe-agent"))
        maintenance.lock("probe-agent", 5)
        self.assertTrue(maintenance.is_locked("probe-agent"))
        maintenance.unlock("probe-agent")
        self.assertFalse(maintenance.is_locked("probe-agent"))
