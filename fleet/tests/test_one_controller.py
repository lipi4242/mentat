"""Egy vezérlő: a liveness funkciói (OOM-védelem, tick
re-arm) a reconcile-ban futnak, egy timeren; a heartbeatet a flotta SEMMILYEN
úton nem írja — azt csak a motor írja („két író, egy olvasó" hibaosztály)."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import liveness, reconcile, registry  # noqa: E402

NOW = 1_800_000_000.0
HB = "data/state/orchestrator-heartbeat.json"


def _entry(workdir, **kw):
    b = {"agent": "probe-agent", "rc_name": "probe", "workdir": workdir, "proactive": True,
         "host": "probe-host", "tick_period_s": 1800, "loop_cmd": "/x:startup"}
    b.update(kw)
    return registry.normalize(b)


def _m(t_age, tick_age, rearm_age=None):
    return {"agent": "probe-agent", "session_id": "s", "transcript_age_s": t_age, "pollers": [],
            "rearm_age_s": rearm_age,
            "signals": {"process": {"state": "up", "detail": "", "data": {"pid": 1, "rss_mb": 100, "started_s": NOW - 9000}},
                        "schedule": {"state": "stale", "detail": "", "data": {"tick_age_s": tick_age, "period_s": 1800}},
                        "channel": {"state": "n/a", "detail": "", "data": {}},
                        "rc": {"state": "connected", "detail": "", "data": {}},
                        "auth": {"state": "ok", "detail": "", "data": {}}}}


class TestRearmInReconcile(unittest.TestCase):
    def acts(self, m):
        return [a for a, _ in reconcile.decide(_entry("/x"), m, {"restarts": []},
                                               unit_active=True, locked=False, now=NOW)]

    def test_idle_and_stale_is_rearmed(self):
        self.assertIn("rearm", self.acts(_m(t_age=1200, tick_age=1800 * 2)))

    def test_busy_agent_and_cooldown_are_left_alone(self):
        self.assertNotIn("rearm", self.acts(_m(t_age=30, tick_age=1800 * 2)))
        self.assertNotIn("rearm", self.acts(_m(t_age=1200, tick_age=1800 * 2, rearm_age=600)))

    def test_execute_rearm_marks_before_sending(self):
        sent = []
        with tempfile.TemporaryDirectory() as d:
            e = _entry(d)
            orig = (liveness.send_loop_cmd, reconcile._may_act)
            mark = Path(d) / "data/state/last-rearm"
            liveness.send_loop_cmd = lambda s, c: sent.append((s, c, mark.exists())) or True
            reconcile._may_act = lambda e, log: True
            try:
                reconcile.execute(e, "rearm", {"pollers": []}, {}, now=NOW, log=lambda x: None)
            finally:
                liveness.send_loop_cmd, reconcile._may_act = orig
        self.assertEqual(sent, [(e["session"], "/x:startup", True)])


class TestOneControllerNoHeartbeatWriter(unittest.TestCase):
    def run_reconcile(self, d, observe):
        swept = []
        e = _entry(d)
        orig = (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host)
        reconcile.STATE_DIR = Path(d) / "st"; reconcile.LOCK_PATH = Path(d) / "st" / "lock"
        reconcile.controller_is_us = lambda: True
        reconcile.local_host = lambda: "probe-host"
        try:
            # friss transzkript (dolgozik): a régi liveness itt írta a heartbeatet
            reconcile.reconcile(observe=observe, agents=[e], now=NOW,
                                measure=lambda _e: _m(t_age=5, tick_age=60),
                                unit_active=lambda u: True, execute_fn=lambda *a, **k: None,
                                oom_sweep=lambda: swept.append(1) or {"protected": 0, "oom_failed": 0})
        finally:
            (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host) = orig
        return swept

    def test_reconcile_sweeps_oom_when_acting_only(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_reconcile(d, observe=False), [1])
            self.assertEqual(self.run_reconcile(d, observe=True), [])

    def test_no_fleet_path_writes_the_heartbeat(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_reconcile(d, observe=False)
            self.assertEqual(liveness.main(), 0)   # a régi timer belépője: no-op
            self.assertFalse((Path(d) / HB).exists())

    def test_legacy_liveness_entry_does_nothing(self):
        t0 = time.time()
        self.assertEqual(liveness.main(), 0)
        self.assertFalse(hasattr(liveness, "run"))
        self.assertLess(time.time() - t0, 5)


if __name__ == "__main__":
    unittest.main()
