"""`fleet setup <ágens>` — a kihelyezés egy parancsa (06-flotta: a README
láncát az ágensnek hét külön parancsként kellett végigolvasnia és -vinnie).
A TERMELŐ setup()-ot hívja; a systemd-függő lépések (install, reconcile,
doctor) a láncsorrend és az összefoglaló próbájához csonkolva."""
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


class TestSetupOneCommand(Home):
    def setUp(self):
        super().setUp()
        reg = self.home / "reg"
        (reg / "runbooks").mkdir(parents=True)
        (reg / "runbooks/probe.md").write_text("# probe\n")
        (reg / "boxes.json").write_text(json.dumps({"boxes": [{"key": "box1", "hostname": "box1"}]}))
        (reg / "agents.json").write_text(json.dumps([{
            "agent": "probe", "unit": "probe.service", "session": "probe", "workdir": str(self.work),
            "model": "opus", "host": "box1", "runbook": "runbooks/probe.md"}]))
        p = mock.patch.dict(os.environ, {"FLEET_REGISTRY": str(reg), "FLEET_HOST": "box1"})
        p.start(); self.addCleanup(p.stop)
        subprocess.run(["git", "init", "-q", str(self.work)], check=True)
        (self.work / "AGENTS.md").write_text("# agy\n")

    def test_check_mode_writes_nothing_and_lists_what_it_would_set(self):
        from fleet.setup import setup
        r = setup("probe", check=True, home=self.home, claude_bin=self.fb.claude, tmux_bin=self.fb.tmux)
        self.assertFalse((self.home / ".claude.json").exists())
        self.assertFalse((self.work / ".claude").exists())
        text = json.dumps(r, ensure_ascii=False)
        self.assertIn("hasCompletedOnboarding", text)
        self.assertIn("skipDangerousModePermissionPrompt", text)
        self.assertTrue(r["summary"].startswith("fleet setup probe --check:"), r["summary"])

    def test_missing_tmux_stops_at_preflight_with_one_line_fix(self):
        from fleet.setup import setup
        r = setup("probe", check=True, home=self.home, claude_bin=self.fb.claude,
                  tmux_bin=self.home / "nincs-tmux")
        self.assertEqual(r["status"], "failed")
        self.assertIn("NEM KÉSZ (preflight) — hiányzik a tmux", r["summary"])

    def _deploy(self, health, install_status="ok"):
        from fleet.setup import setup
        sig = {"process": {"state": "up"}, "rc": {"state": "unknown"}}
        doc = [{"agent": "probe", "health": health, "signals": sig, "problems": [], "pending": [], "unknown": []}]
        with mock.patch("fleet.install_flow.install_agent", return_value={
                "status": install_status, "notes": ["n"], "problems": ["p"], "journal": []}), \
             mock.patch("fleet.plugin_install.install_plugin", return_value={"ok": False, "note": "plugin: NEM települt — x"}), \
             mock.patch("fleet.reconcile.reconcile", return_value={"lines": []}), \
             mock.patch("fleet.doctor.doctor", return_value=doc):
            return setup("probe", home=self.home, claude_bin=self.fb.claude, tmux_bin=self.fb.tmux)

    def test_full_chain_ends_in_one_summary_line_from_doctor(self):
        r = self._deploy("healthy")
        self.assertEqual(r["status"], "ok")
        self.assertEqual([s[0] for s in r["steps"]],
                         ["validate", "join", "preflight", "install", "plugin", "titok-kapu", "reconcile", "doctor"])
        self.assertTrue(r["summary"].startswith("fleet setup probe: KÉSZ — doctor: healthy"), r["summary"])
        self.assertTrue((self.work / ".claude/fleet.json").exists())   # a join valóban lefutott
        self.assertEqual(self._deploy("pending")["status"], "pending")

    def test_failed_install_stops_the_chain(self):
        r = self._deploy("healthy", install_status="failed")
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["steps"][-1][0], "install")
        self.assertIn("NEM KÉSZ (install) — p", r["summary"])

    def test_unknown_agent_is_one_clear_line(self):
        from fleet.setup import setup
        r = setup("nincs-ilyen", check=True, home=self.home, claude_bin=self.fb.claude)
        self.assertEqual(r["status"], "failed")
        self.assertIn("nincs ilyen ágens", r["summary"])


if __name__ == "__main__":
    unittest.main()
