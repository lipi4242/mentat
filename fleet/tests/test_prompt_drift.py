"""Prompt-drift → resume-restart, az elfogadási esetek. A kapu tud pirosat:
változatlan prompt, dolgozó ágens és kimerült keret mellett NINCS restart."""
from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest  # noqa: F401  (repo konvenció)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drift_box import BUSY, T0, Box  # noqa: E402

from fleet import prompt_drift, reconcile, request_restart_cli, requested_stop  # noqa: E402


class TestPromptDrift(Box):
    def test_unchanged_prompt_no_restart(self):
        self.round(T0); self.round(T0 + 300); lines = self.round(T0 + 300 + prompt_drift.STABLE_S + 1)
        self.assertEqual(self.restarts(), [], lines)
        self.assertEqual(self.alerts, [])

    def test_mtime_only_change_is_not_drift(self):
        self.round(T0)
        p = self.wd / ".claude" / "rules" / "r.md"
        p.write_text(p.read_text()); os.utime(p, (T0 + 99, T0 + 99))
        self.settle(T0 + 300)
        self.assertEqual(self.restarts(), [])

    def test_changed_and_idle_restarts_with_resume_budget_notice_log_alert(self):
        self.round(T0)
        self.change(".claude/rules/r.md", "új szabály\n")
        lines = self.settle(T0 + 300)
        self.assertEqual(len(self.restarts()), 1, lines)
        st = self.st()
        self.assertEqual(len(st["resume_restarts"]), 1)
        self.assertEqual(st.get("restarts"), [])                    # a crash-keret érintetlen
        self.assertEqual(len(self.sent), 1)
        self.assertIn(".claude/rules/r.md", self.sent[0])
        self.assertIsNone(st.get("drift_notice"))
        log = (self.d / "st" / "prompt-drift.log").read_text().splitlines()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].split("\t")[1:], ["probe-agent", "változott prompt: .claude/rules/r.md",
                                                  ".claude/rules/r.md", "postcheck ok"])
        self.assertEqual(len(self.alerts), 1)

    def test_include_chain_change_is_detected(self):
        self.round(T0)
        self.change("docs/extra.md", "átírva\n")
        self.settle(T0 + 300)
        self.assertEqual(len(self.restarts()), 1)
        self.assertIn("docs/extra.md", self.sent[0])

    def test_changed_but_busy_waits_then_signals_after_6h_without_forcing(self):
        self.round(T0)
        self.change("AGENTS.md", "másik\n")
        self.settle(T0 + 300, age=BUSY)
        self.assertEqual(self.restarts(), [])
        self.assertEqual(self.alerts, [])                           # a rövid várakozás nem riaszt
        lines = self.round(T0 + 300 + prompt_drift.WAIT_ALERT_S + 60, age=BUSY)
        self.assertEqual(self.restarts(), [], lines)
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("dolgozik-6h+", self.alerts[0])
        self.round(T0 + 600 + prompt_drift.WAIT_ALERT_S + 60, age=BUSY)
        self.assertEqual(len(self.alerts), 1)                       # ugyanaz az epizód: nem ismétel

    def test_budget_exhausted_no_restart_and_signal(self):
        self.round(T0)
        st = self.st(); st["resume_restarts"] = [T0 - 10] * prompt_drift.RESUME_BUDGET
        reconcile.save_state("probe-agent", st)
        self.change("CLAUDE.md", "# más\n")
        lines = self.settle(T0 + 300)
        self.assertEqual(self.restarts(), [], lines)
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("keret-elfogyott", self.alerts[0])
        self.assertEqual(self.st().get("restarts"), [])

    def test_new_generation_rebaselines_without_restart(self):
        self.round(T0)
        self.change("CLAUDE.md", "# más\n")
        self.gen["probe-agent"] = 101                               # közben más út indította újra
        self.started = T0 + 250
        self.settle(T0 + 300)
        self.assertEqual(self.restarts(), [])

    def test_agent_request_goes_through_marker_and_reconcile(self):
        self.round(T0)
        with mock.patch.dict(os.environ, {"FLEET_AGENT": "probe-agent"}), \
             mock.patch("fleet.registry.get_agent", lambda n: self.agents[0]):
            self.assertEqual(request_restart_cli.cmd_request_restart(SimpleNamespace(agent=None)), 0)
        self.assertTrue(requested_stop.restart_pending("probe-agent"))
        self.round(T0 + 300, age=BUSY)                              # a kérő kör még fut
        self.assertEqual(self.restarts(), [])
        self.round(T0 + 400, age=prompt_drift.REQUEST_IDLE_S + 30)
        self.assertEqual(len(self.restarts()), 1)
        self.assertFalse(requested_stop.restart_pending("probe-agent"))
        self.assertIn("kérted", self.sent[0])
        self.assertEqual(len(self.st()["resume_restarts"]), 1)


if __name__ == "__main__":
    unittest.main()
