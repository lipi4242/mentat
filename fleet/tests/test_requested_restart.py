"""A kért leállás (`fleet stop`) utáni visszaindítás nem fogy a crash-loop
költségvetésből (2. kör, 06-flotta: a 4. leölésre nem maradt keret). A TERMELŐ
agentctl.stop()-ot, reconcile.reconcile()-t és reconcile.execute()-ot hívják."""
from __future__ import annotations
import functools
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import agentctl, alerts, reconcile, requested_stop  # noqa: E402
from fleet.registry import normalize  # noqa: E402


def _m(proc):
    sig = lambda s: {"state": s, "detail": "", "data": {}}
    return lambda e: {"agent": e["agent"], "transcript_age_s": 5, "pollers": [], "rearm_age_s": None,
                      "signals": {"process": sig(proc), "schedule": sig("n/a"), "channel": sig("n/a"),
                                  "rc": sig("n/a"), "auth": sig("ok")}}


class Box(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="fleet-req-"))
        for k, v in {"FLEET_MAINTENANCE_DIR": str(self.d / "maint")}.items():
            p = mock.patch.dict(os.environ, {k: v}); p.start(); self.addCleanup(p.stop)
        for obj, attr, val in [(reconcile, "STATE_DIR", self.d / "st"), (reconcile, "LOCK_PATH", self.d / "st" / "lock"),
                               (reconcile, "controller_is_us", lambda: True), (reconcile, "local_host", lambda: "box"),
                               (agentctl, "_generation", lambda e: None),
                               # HERMETIKUS: a riasztás se a valódi ~/.config/fleet-be, se Telegramra
                               (alerts, "ALERTS_PATH", self.d / "st" / "alerts.json"),
                               (alerts, "send_telegram", lambda *a, **k: False)]:
            p = mock.patch.object(obj, attr, val); p.start(); self.addCleanup(p.stop)
        self.e = normalize({"agent": "probe-agent", "workdir": "/x", "host": "box"})
        self.calls = []

    def stop(self):
        ok = SimpleNamespace(returncode=0, stderr="", stdout="")
        self.assertTrue(agentctl.stop(self.e, run=lambda cmd: ok, home=self.d)["ok"])

    def down_and_reconcile(self, now):
        ex = functools.partial(reconcile.execute, sysctl=lambda *a: self.calls.append(a) or 0,
                               run=lambda *a, **k: None,
                               do_postcheck=lambda e, **k: {"status": "ok", "ok": True, "pending": [], "problems": []})
        return reconcile.reconcile(agents=[self.e], now=now, measure=_m("down"), unit_active=lambda u: False,
                                   execute_fn=ex, oom_sweep=lambda: {"protected": 0}, procs=None)["lines"]

    def started(self):
        return sum(1 for c in self.calls if c[0] == "start")


class TestRequestedRestartIsFree(Box):
    def test_box_replay_fourth_real_kill_still_comes_back(self):
        """09:47 ágens-próba stop, 09:50 tesztelő stop, 09:52 kill -9, ~10:05 a check kill -9-e."""
        t = time.time()
        self.stop(); self.down_and_reconcile(t + 50)
        self.stop(); self.down_and_reconcile(t + 190)
        self.down_and_reconcile(t + 250)                       # kill -9: nem kért
        lines = self.down_and_reconcile(t + 1100)              # a kemény ellenőrzés leölése
        self.assertEqual(self.started(), 4, lines)
        st = reconcile.load_state("probe-agent")
        self.assertEqual(len(st["restarts"]), 2)               # csak a két nem kért
        self.assertEqual(len(st["requested_restarts"]), 2)

    def test_crash_loop_protection_unchanged_without_stop(self):
        t = time.time()
        for i in range(3):
            self.down_and_reconcile(t + 60 * i)
        lines = self.down_and_reconcile(t + 300)
        self.assertEqual(self.started(), 3)
        self.assertTrue(any("restart/óra elfogyott" in x for x in lines), lines)

    def test_requested_stop_returns_even_with_exhausted_budget(self):
        t = time.time()
        for i in range(3):
            self.down_and_reconcile(t + 60 * i)
        self.stop()
        self.down_and_reconcile(t + 300)
        self.assertEqual(self.started(), 4)
        self.assertFalse(requested_stop.pending("probe-agent"))   # egyszer használható

    def test_marker_expires(self):
        requested_stop.mark("probe-agent", now=1000.0)
        self.assertTrue(requested_stop.pending("probe-agent", 1000.0 + requested_stop.VALID_S - 1))
        self.assertFalse(requested_stop.take("probe-agent", 1000.0 + requested_stop.VALID_S + 1))
        self.assertFalse(requested_stop.pending("probe-agent", 1000.0))

    def test_failed_stop_leaves_no_marker(self):
        bad = SimpleNamespace(returncode=5, stderr="nope", stdout="")
        self.assertFalse(agentctl.stop(self.e, run=lambda cmd: bad, home=self.d)["ok"])
        self.assertFalse(requested_stop.pending("probe-agent"))

    def test_manual_restart_consumes_the_marker(self):
        ok = SimpleNamespace(returncode=0, stderr="", stdout="")
        self.stop()
        agentctl.restart(self.e, run=lambda cmd: ok, check=lambda e, **k: {"ok": True, "status": "ok", "agent": "probe-agent",
                                                                    "waited_s": 0, "problems": [], "pending": [],
                                                                    "measure": {"signals": {}}})
        self.assertFalse(requested_stop.pending("probe-agent"))

    def test_hold_extends_validity(self):
        requested_stop.mark("probe-agent", hold_min=60, now=0.0)
        self.assertTrue(requested_stop.pending("probe-agent", 3600 + requested_stop.VALID_S - 1))


if __name__ == "__main__":
    unittest.main()
