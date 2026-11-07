"""`fleet init` (a registry-bejegyzés egy parancsa) és `fleet wait-up` (a
visszajövés ideje). A TERMELŐ init()/wait_up() függvényeket hívják."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_zero_touch_ops import Home  # noqa: E402


def _S(state, pid=1, started=1):
    from fleet.signals import Signal
    return Signal("process", state, "", {"pid": pid, "started_s": started})


class TestInit(Home):
    def setUp(self):
        super().setUp()
        self.repo = self.work
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "mentat.json").write_text(json.dumps(
            {"schema": 1, "agent": {"name": "mini-agent"}, "components": {"brain": {}}}))
        env = {"FLEET_HOST": "", "HOME": str(self.home)}
        p = mock.patch.dict(os.environ, env); p.start(); self.addCleanup(p.stop)
        os.environ.pop("FLEET_REGISTRY", None); os.environ.pop("FLEET_HOST", None)

    def _init(self, agent=None, **kw):
        from fleet.init import init
        return init(agent, repo=self.repo, home=self.home, claude_bin=self.fb.claude,
                    tmux_bin=self.fb.tmux, host_name="boxx", **kw)

    def test_fresh_box_writes_minimal_registry_that_validates(self):
        r = self._init()
        self.assertEqual(r["status"], "ok", r["summary"])
        reg = Path((self.home / ".config/fleet/registry").read_text().strip())
        e = json.loads((reg / "agents.json").read_text())[0]
        self.assertEqual((e["agent"], e["model"], e["host"], e["status"]), ("mini-agent", "opus", "boxx", "active"))
        self.assertEqual(e["workdir"], "%h/agent")
        self.assertTrue((reg / "runbooks/mini-agent.md").is_file())
        self.assertIn("fleet setup mini-agent", r["summary"])
        os.environ["FLEET_REGISTRY"] = str(reg)
        from fleet.validate import validate
        self.assertEqual(validate(reg)[1], [])

    def test_idempotent_and_keeps_existing_entry(self):
        self._init("mini-agent")
        reg = Path((self.home / ".config/fleet/registry").read_text().strip())
        a = json.loads((reg / "agents.json").read_text()); a[0]["model"] = "sonnet"
        (reg / "agents.json").write_text(json.dumps(a))
        r = self._init("mini-agent")
        self.assertEqual(json.loads((reg / "agents.json").read_text())[0]["model"], "sonnet")
        self.assertEqual(len(json.loads((reg / "agents.json").read_text())), 1)
        self.assertIn("már a registryben", r["summary"])

    def test_missing_tmux_one_line_fix_but_registry_written(self):
        from fleet.init import init
        r = init(None, repo=self.repo, home=self.home, claude_bin=self.fb.claude,
                 tmux_bin=self.home / "nincs", host_name="boxx")
        self.assertEqual(r["status"], "failed")
        self.assertIn("hiányzik a tmux", r["summary"])
        self.assertTrue((self.home / ".config/fleet/registry").is_file())

    def test_logged_out_names_fleet_auth(self):
        (self.fb.dir / "logged-out").write_text("")
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        r = self._init()
        self.assertEqual(r["status"], "failed")
        self.assertIn("fleet auth mini-agent", r["summary"])

    def test_not_a_git_repo_says_git_init(self):
        import shutil; shutil.rmtree(self.repo / ".git")
        r = self._init()
        self.assertEqual(r["status"], "failed")
        self.assertIn("git init", r["summary"])

    def test_bad_name_rejected(self):
        r = self._init("Rossz Név")
        self.assertEqual(r["status"], "failed")

    def test_pointer_goes_to_the_given_home_not_to_env_home(self):
        """2026-10-18: a mutató a `home`-tól független $HOME alá ment (a valódi
        ~/.config/fleet/registry egy tmp registry.d-re mutatott)."""
        other = Path(self.tmp.name + "-env-home"); other.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        os.environ["HOME"] = str(other)
        r = self._init()
        self.assertEqual(r["status"], "ok", r["summary"])
        self.assertTrue((self.home / ".config/fleet/registry").is_file())
        self.assertEqual(list(other.iterdir()), [])


class TestWaitUp(Home):
    def _timer(self, sec):
        t = self.home / ".config/systemd/user/fleet-reconcile.timer"
        t.parent.mkdir(parents=True, exist_ok=True); t.write_text(f"[Timer]\nOnUnitActiveSec={sec}\n")

    def test_period_read_from_installed_timer(self):
        from fleet.agentctl import reconcile_period_s
        self._timer("1min"); self.assertEqual(reconcile_period_s(self.home), 60)
        self._timer("5min"); self.assertEqual(reconcile_period_s(self.home), 300)

    def test_returns_when_process_comes_up(self):
        from fleet.agentctl import wait_up
        seq = iter([_S("down"), _S("down"), _S("up", 2, 20)])
        r = wait_up(self.e, timeout_s=60, home=self.home, sig=lambda e: next(seq),
                    sleep=lambda s: None, clock=iter(range(0, 1000, 5)).__next__)
        self.assertTrue(r["ok"]); self.assertIn("visszajött", r["notes"][-1])

    def test_lock_means_no_return_expected(self):
        from fleet import maintenance
        from fleet.agentctl import wait_up
        maintenance.lock("probe", 30)
        self.addCleanup(maintenance.unlock, "probe")
        r = wait_up(self.e, timeout_s=60, home=self.home, sig=lambda e: _S("down"), sleep=lambda s: None)
        self.assertFalse(r["ok"]); self.assertIn("zár", r["notes"][0])

    def test_timeout_reports_not_back(self):
        from fleet.agentctl import wait_up
        self._timer("1min")
        r = wait_up(self.e, timeout_s=20, home=self.home, sig=lambda e: _S("down"),
                    sleep=lambda s: None, clock=iter(range(0, 1000, 5)).__next__)
        self.assertFalse(r["ok"]); self.assertIn("NEM jött vissza", r["notes"][-1])


if __name__ == "__main__":
    unittest.main()


class TestFastPath(Home):
    """A gyors út: a leölt processz ≤~1 percen belül visszajön, a többi
    (híd-restart, riasztás, re-arm) marad az 5 perces teljes körön."""

    def setUp(self):
        super().setUp()
        import tempfile
        from fleet import reconcile_fast
        self.d = Path(tempfile.mkdtemp())
        p = mock.patch.object(reconcile_fast, "MARK_DIR", self.d); p.start(); self.addCleanup(p.stop)

    def test_down_needs_two_observations_before_start(self):
        from fleet.reconcile_fast import filter_acts
        down = [("start", "nincs claude-processz")]
        self.assertEqual(filter_acts("probe", down, 100.0), [])          # első látás: csak jelöl
        self.assertEqual(filter_acts("probe", down, 110.0), [])          # még a megerősítési időn belül
        self.assertEqual(filter_acts("probe", down, 130.0), down)        # megerősítve: indít

    def test_back_up_clears_the_mark(self):
        from fleet.reconcile_fast import filter_acts
        filter_acts("probe", [("restart", "nincs claude-processz")], 100.0)
        self.assertEqual(filter_acts("probe", [("noop", "egészséges")], 105.0), [])
        self.assertEqual(filter_acts("probe", [("start", "x")], 200.0), [])   # újra első látás

    def test_other_actions_never_pass_the_fast_path(self):
        from fleet.reconcile_fast import filter_acts
        busy = [("restart_bridge", "409"), ("alert:auth:x", "lejárt"), ("kill_pollers", "p"), ("rearm", "r")]
        self.assertEqual(filter_acts("probe", busy, 100.0), [])
        self.assertEqual(filter_acts("probe", busy, 500.0), [])

    def test_skip_lock_and_quarantine_do_not_start(self):
        from fleet.reconcile_fast import filter_acts
        for _ in range(2):
            self.assertEqual(filter_acts("probe", [("skip:lock", "zár")], 100.0), [])

    def test_return_bound_prefers_fast_timer(self):
        from fleet.agentctl import return_bound_s
        d = self.home / ".config/systemd/user"; d.mkdir(parents=True, exist_ok=True)
        (d / "fleet-reconcile.timer").write_text("[Timer]\nOnUnitActiveSec=5min\n")
        self.assertEqual(return_bound_s(self.home), 300)
        (d / "fleet-reconcile-fast.timer").write_text("[Timer]\nOnUnitActiveSec=30s\n")
        self.assertEqual(return_bound_s(self.home), 70)


class TestFastReconcileEndToEnd(unittest.TestCase):
    """A TERMELŐ reconcile(fast=True): a leölt processz a második megfigyelésnél
    indul; közben és egészséges ágensnél néma; a híd/riasztás nem gyorsul."""

    def _run(self, d, measure, now, executed):
        import tempfile  # noqa: F401
        from fleet import reconcile, reconcile_fast
        from fleet.registry import normalize
        e = normalize({"agent": "probe-agent", "workdir": "/x", "host": "probe-host"})
        orig = (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host,
                reconcile_fast.MARK_DIR)
        reconcile.STATE_DIR = Path(d) / "st"; reconcile.LOCK_PATH = Path(d) / "st" / "lock"
        reconcile.controller_is_us = lambda: True; reconcile.local_host = lambda: "probe-host"
        reconcile_fast.MARK_DIR = Path(d) / "down"
        try:
            return reconcile.reconcile(
                agents=[e], now=now, fast=True, measure=measure, unit_active=lambda u: True,
                execute_fn=lambda ent, act, *a, **k: executed.append(act), oom_sweep=lambda: {})
        finally:
            (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us, reconcile.local_host,
             reconcile_fast.MARK_DIR) = orig

    @staticmethod
    def _m(proc, channel="n/a"):
        sig = lambda s: {"state": s, "detail": "", "data": {}}
        return lambda e: {"agent": e["agent"], "transcript_age_s": 5, "pollers": [], "rearm_age_s": None,
                          "signals": {"process": sig(proc), "schedule": sig("n/a"), "channel": sig(channel),
                                      "rc": sig("n/a"), "auth": sig("ok")}}

    def test_down_agent_restarts_on_second_look_and_healthy_is_silent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ex = []
            r1 = self._run(d, self._m("down"), 1000.0, ex)
            self.assertEqual((ex, r1["lines"]), ([], []))
            r2 = self._run(d, self._m("down"), 1030.0, ex)
            self.assertEqual(ex, ["restart"]); self.assertTrue(r2["lines"])
            ex.clear()
            self.assertEqual(self._run(d, self._m("up"), 1060.0, ex)["lines"], [])
            self.assertEqual(ex, [])

    def test_bridge_conflict_is_not_a_fast_path_job(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ex = []
            for t in (1000.0, 1030.0, 1060.0):
                self._run(d, self._m("up", channel="conflict"), t, ex)
            self.assertEqual(ex, [])


class TestSupervisionInstallsFastTimer(Home):
    def _install(self, templates):
        from fleet import supervision
        from fleet.txn import Txn
        unit_dir = self.home / "units"; cfg = self.home / "cfg"
        with mock.patch.object(supervision, "TEMPLATES_DIR", templates):
            t = Txn()
            return supervision.ensure_supervision(t, unit_dir=unit_dir, config_dir=cfg,
                                                  fleet_root="/opt/fleet", registry=self.home), unit_dir

    def test_fast_units_written_and_enabled_when_templates_exist(self):
        from fleet import TEMPLATES_DIR
        notes, unit_dir = self._install(TEMPLATES_DIR)
        self.assertTrue((unit_dir / "fleet-reconcile-fast.timer").is_file())
        self.assertIn("reconcile --fast", (unit_dir / "fleet-reconcile-fast.service").read_text())
        self.assertNotIn("@@", (unit_dir / "fleet-reconcile-fast.service").read_text())
        calls = (self.fb.dir / "calls").read_text()
        self.assertIn("enable --now fleet-reconcile-fast.timer", calls)

    def test_old_checkout_without_fast_templates_still_installs(self):
        import shutil, tempfile
        from fleet import TEMPLATES_DIR
        old = Path(tempfile.mkdtemp()); shutil.copytree(TEMPLATES_DIR / "systemd", old / "systemd")
        for n in ("fleet-reconcile-fast.service", "fleet-reconcile-fast.timer"):
            (old / "systemd" / n).unlink()
        notes, unit_dir = self._install(old)
        self.assertFalse((unit_dir / "fleet-reconcile-fast.timer").exists())
        self.assertTrue((unit_dir / "fleet-reconcile.timer").is_file())
