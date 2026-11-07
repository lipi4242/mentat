"""A kimerült restart-keret látszik: `fleet doctor` (nem healthy), `fleet status`
és az ágens session-indítása (bin/capture-session-id.sh). 2. kör, 06-flotta: a
keret 10:07-kor elfogyott, és ezt csak a journal mondta ki. A TERMELŐ
doctor.assess()-t, status.status()-t és a hook-szkriptet hívják; minden
állapot temp-ben (HOME, FLEET_MAINTENANCE_DIR, reconcile.STATE_DIR)."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, reconcile, registry, status  # noqa: E402

NOW = 1_800_000_000.0


def _m():
    ok = lambda s: {"state": s, "detail": "", "data": {}}
    return {"pollers": [], "signals": {"process": ok("up"), "schedule": ok("n/a"), "channel": ok("n/a"),
                                       "rc": ok("n/a"), "auth": ok("ok")}}


def _assess(st):
    e = registry.normalize({"agent": "probe-agent", "workdir": "/x"})
    return doctor.assess(e, _m(), st, unit_active="active", unit_enabled="enabled", drop_in=True,
                         bridge_installed=None, bridge_current="x", locked=False, now=NOW)


class TestDoctorShowsBudget(unittest.TestCase):
    def test_exhausted_budget_is_not_healthy_and_says_when_it_frees(self):
        r = _assess({"restarts": [NOW - 1000, NOW - 600, NOW - 300]})
        self.assertFalse(r["ok"])
        line = [p for p in r["problems"] if "restart-keret" in p]
        self.assertEqual(len(line), 1, r["problems"])
        self.assertIn("43 perc múlva", line[0])          # a legrégebbi + 1 óra

    def test_old_or_requested_restarts_do_not_count(self):
        self.assertTrue(_assess({"restarts": [NOW - 4000, NOW - 4100, NOW - 300]})["ok"])
        self.assertTrue(_assess({"restarts": [], "requested_restarts": [NOW - 10, NOW - 20, NOW - 30]})["ok"])


class TestStatusAndSessionStartShowBudget(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="fleet-budget-home-"))
        st = self.home / ".config" / "fleet" / "state"
        st.mkdir(parents=True)
        t = time.time()
        (st / "probe-agent.json").write_text(json.dumps({"restarts": [t - 600, t - 300, t - 60]}))
        self.st = st

    def test_status_has_one_unhealthy_line(self):
        repo = self.home / "repo"; repo.mkdir()
        with mock.patch.object(reconcile, "STATE_DIR", self.st):
            r = status.status("probe-agent", repo=repo, unit_dir=self.home)
        self.assertEqual(r.get("health"), "unhealthy")
        lines = [x for x in status.format_status(r).splitlines() if "restart-keret" in x]
        self.assertEqual(len(lines), 1)

    def test_session_start_hook_prints_the_line(self):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "FLEET_AGENT": "probe-agent",
               "CLAUDE_CODE_SESSION_ID": "s-1"}
        r = subprocess.run(["sh", str(ROOT / "bin" / "capture-session-id.sh")], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("restart-keret kimerült", r.stdout)
        self.assertEqual((self.home / ".config" / "probe-agent" / "session.id").read_text(), "s-1")

    def test_session_start_hook_also_reads_thufir_agent(self):
        """L23: a régebbi unitok THUFIR_AGENT-et exportálnak; a hook nekik is rögzíti a session.id-t."""
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "THUFIR_AGENT": "old-agent",
               "CLAUDE_CODE_SESSION_ID": "s-9"}
        r = subprocess.run(["sh", str(ROOT / "bin" / "capture-session-id.sh")], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / ".config" / "old-agent" / "session.id").read_text(), "s-9")

    def test_session_start_hook_silent_when_budget_ok(self):
        (self.st / "probe-agent.json").write_text(json.dumps({"restarts": []}))
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "FLEET_AGENT": "probe-agent",
               "CLAUDE_CODE_SESSION_ID": "s-2"}
        r = subprocess.run(["sh", str(ROOT / "bin" / "capture-session-id.sh")], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
