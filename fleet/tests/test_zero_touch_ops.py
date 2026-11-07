"""06-flotta, a telepítés utáni rész: a flotta timerén futó tick felügyelete
proactive:false mellett is, a valódi marketplace-cím, a plugin-hiba nem
blokkol, célzott stop/restart (a `fleet setup`: test_setup_one_command.py). A TERMELŐ
kódot hívják (signals, reconcile.decide, postcheck, plugin_install,
agentctl).
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import agentctl, join, maintenance, plugin_install, plugin_source, registry, signals  # noqa: E402
from fleet.postcheck import _schedule  # noqa: E402
from fleet.reconcile import decide  # noqa: E402
from fakebin import FakeBin  # noqa: E402


class Home(unittest.TestCase):
    def setUp(self):
        self.fb = FakeBin()
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.work = self.home / "agent"
        (self.work / "data/state").mkdir(parents=True)
        p = mock.patch.object(Path, "home", return_value=self.home)
        p.start(); self.addCleanup(p.stop)
        self.e = registry.normalize({"agent": "probe", "workdir": "%h/agent", "host": "box1"})

    def tearDown(self):
        self.fb.cleanup(); self.tmp.cleanup()

    def fleet_owned(self, timer="OnCalendar=hourly\n", tick_age=None, armed_age=60):
        (self.work / "mentat.json").write_text(json.dumps(
            {"schema": 1, "components": {"engine": {"path": "anytime_engine", "schedule_owner": "fleet"}}}))
        t = self.home / ".config/systemd/user/fleet-tick-probe.timer"
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text("[Timer]\n" + timer)
        os.utime(t, (time.time() - armed_age, time.time() - armed_age))
        if tick_age is not None:
            f = self.work / "data/state/last-tick.json"
            f.write_text("{}")
            os.utime(f, (time.time() - tick_age, time.time() - tick_age))


class TestFleetOwnedTickIsWatched(Home):
    def test_not_proactive_and_engine_owned_stays_na(self):
        self.assertEqual(signals.schedule_signal(self.e, None, None).state, "n/a")

    def test_fleet_owned_fresh_tick_is_armed_even_if_not_proactive(self):
        self.fleet_owned(tick_age=600)
        s = signals.schedule_signal(self.e, None, None)
        self.assertEqual((s.state, s.data["owner"], s.data["period_s"]), ("armed", "fleet", 3600.0))

    def test_stuck_fleet_tick_is_stale_and_reconcile_alerts(self):
        self.fleet_owned(tick_age=13 * 3600, armed_age=30 * 3600)
        s = signals.schedule_signal(self.e, None, None).as_dict()
        self.assertEqual(s["state"], "stale")
        acts = self._decide(s)
        self.assertTrue(any(a.startswith("alert:silence:probe") for a, _ in acts), acts)

    def _decide(self, sched):
        m = {"signals": {"process": {"state": "up", "data": {"pid": 1, "started_s": 1}, "detail": ""},
                         "schedule": sched, "channel": {"state": "n/a", "data": {}, "detail": ""},
                         "rc": {"state": "unknown", "data": {}, "detail": ""},
                         "auth": {"state": "ok", "data": {}, "detail": ""}},
             "pollers": [], "transcript_age_s": 10}
        return decide(self.e, m, {}, unit_active=True, locked=False, now=time.time())

    def test_fleet_timer_that_never_ticked_is_stale_after_grace_and_alerts(self):
        self.fleet_owned(armed_age=14 * 3600)
        s = signals.schedule_signal(self.e, None, None).as_dict()
        self.assertEqual(s["state"], "stale")
        self.assertGreater(s["data"]["silent_s"], 12 * 3600)
        self.assertTrue(any(a.startswith("alert:silence:probe") for a, _ in self._decide(s)))

    def test_restart_postcheck_does_not_wait_for_fleet_timer_tick(self):
        self.fleet_owned(armed_age=60)
        s = signals.schedule_signal(self.e, None, None).as_dict()
        self.assertEqual(s["state"], "pending")
        self.assertEqual(_schedule({"schedule": s}, time.time() - 30, time.time()), (True, ""))


class TestMarketplaceAndPlugin(Home):
    def test_default_marketplace_is_the_real_repo_not_a_placeholder(self):
        self.assertEqual(join.DEFAULT_MARKETPLACE["repo"], plugin_source.PUBLIC_REPO)

    def test_private_repo_failure_is_explained_and_does_not_raise(self):
        self.fb.plugin_fail("fatal: Repository not found.")
        r = plugin_install.install_plugin(self.e, claude_bin=self.fb.claude, home=self.home)
        self.assertFalse(r["ok"])
        self.assertIn("privát repó", r["note"])
        self.assertIn("gh auth login", r["note"])

    def test_success_installs_marketplace_then_plugin(self):
        r = plugin_install.install_plugin(self.e, claude_bin=self.fb.claude, home=self.home)
        self.assertTrue(r["ok"], r)
        calls = self.fb.calls()
        self.assertIn(f"claude plugin marketplace add {plugin_source.PUBLIC_REPO}", calls)
        self.assertIn("claude plugin install fleet@mentat --scope local", calls)


class TestTargetedStopRestart(Home):
    def test_stop_touches_only_the_agent_unit(self):
        r = agentctl.stop(self.e)
        self.assertTrue(r["ok"])
        self.assertEqual(self.fb.calls(), ["systemctl --user stop probe.service"])
        self.assertFalse(maintenance.is_locked("probe"))

    def test_stop_hold_locks_so_reconcile_leaves_it_down(self):
        agentctl.stop(self.e, hold_min=30)
        self.assertTrue(maintenance.is_locked("probe"))
        r = agentctl.restart(self.e, check=lambda e, restart_at, wait_s: {
            "ok": True, "status": "ok", "agent": "probe", "problems": [], "pending": [], "waited_s": 0,
            "measure": {"signals": {}}})
        self.assertEqual(r["status"], "ok")
        self.assertFalse(maintenance.is_locked("probe"))
        self.assertIn("systemctl --user restart probe.service", self.fb.calls())


if __name__ == "__main__":
    unittest.main()
