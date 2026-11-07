"""Egy ágens egy helyen: a más gépre rendelt ágens itteni
processze riasztást ad; a saját és a host nélküli ágens nem."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import dup, reconcile, registry  # noqa: E402

CLAUDE = "/home/t/.local/bin/claude"


def _e(agent, rc, host):
    return registry.normalize({"agent": agent, "rc_name": rc, "workdir": "/x", "host": host})


def _procs(*rcs):
    return [{"pid": 100 + i, "ppid": 1, "rss_mb": 1, "started_s": 0,
             "argv": [CLAUDE, "--dangerously-skip-permissions", "--remote-control", rc]}
            for i, rc in enumerate(rcs)]


class TestForeignHere(unittest.TestCase):
    def test_agent_of_other_host_running_here_is_found(self):
        agents = [_e("mine", "mine", "box1"), _e("theirs", "theirs", "mac"), _e("any", "any", None)]
        got = dup.foreign_here(agents, "box1", _procs("mine", "theirs", "any"))
        self.assertEqual([(e["agent"], pid) for e, pid in got], [("theirs", 101)])

    def test_unknown_host_or_no_procs_is_not_judged(self):
        agents = [_e("theirs", "theirs", "mac")]
        self.assertEqual(dup.foreign_here(agents, None, _procs("theirs")), [])
        self.assertEqual(dup.foreign_here(agents, "box1", []), [])


class TestReconcileAlertsDup(unittest.TestCase):
    def test_reconcile_alerts_once_per_dup_when_acting(self):
        sent = []
        with tempfile.TemporaryDirectory() as d:
            orig = (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us,
                    reconcile.local_host, reconcile.alerts.alert)
            reconcile.STATE_DIR = Path(d); reconcile.LOCK_PATH = Path(d) / "lock"
            reconcile.controller_is_us = lambda: True
            reconcile.local_host = lambda: "box1"
            reconcile.alerts.alert = lambda key, text, **k: sent.append(key) or "sent"
            try:
                r = reconcile.reconcile(agents=[_e("theirs", "theirs", "mac")],
                                        procs=lambda: _procs("theirs"), oom_sweep=lambda: {"protected": 0, "oom_failed": 0},
                                        unit_active=lambda u: True, execute_fn=lambda *a, **k: None)
            finally:
                (reconcile.STATE_DIR, reconcile.LOCK_PATH, reconcile.controller_is_us,
                 reconcile.local_host, reconcile.alerts.alert) = orig
        self.assertEqual(sent, ["dup:theirs:box1"])
        self.assertTrue(any("két helyen" in line for line in r["lines"]))


if __name__ == "__main__":
    unittest.main()
