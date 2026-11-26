"""A riasztás-dedup nem nyelheti el a következő epizódot: karantén, keret, 409 — és az unquarantine sérült állapotra."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import alerts, cli, reconcile, registry  # noqa: E402


def entry(**kw):
    b = {"agent": "probe-agent", "rc_name": "probe", "workdir": "/x", "proactive": True,
         "tick_period_s": 1800, "loop_cmd": "/x:startup", "host": "h"}
    b.update(kw)
    return registry.normalize(b)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.clock = [1_000_000.0]
        self.patches = [
            mock.patch.object(alerts, "ALERTS_PATH", self.d / "alerts.json"),
            mock.patch.object(alerts, "UNDELIVERED", self.d / "undelivered.jsonl"),
            mock.patch.object(reconcile, "STATE_DIR", self.d / "state"),
            mock.patch("time.time", lambda: self.clock[0]),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def undelivered(self):
        p = self.d / "undelivered.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def quarantine(self):
        st = reconcile.load_state("probe-agent")
        st["failed_postchecks"] = reconcile.QUARANTINE_AFTER - 1
        with redirect_stderr(io.StringIO()):
            reconcile._record_postcheck(entry(), st, {"status": reconcile.FAILED, "problems": ["valami"]}, log=lambda m: None)

    def unquarantine(self):
        with redirect_stdout(io.StringIO()):
            return cli.cmd_unquarantine(type("A", (), {"agent": "probe-agent"})())


class Episodes(Base):
    def test_second_quarantine_alerts_again(self):
        self.quarantine()
        self.assertEqual(len(self.undelivered()), 1)
        self.assertEqual(self.unquarantine(), 0)
        self.clock[0] += 5000
        self.quarantine()
        self.assertEqual(len(self.undelivered()), 2)   # ma: dup, a második karantén néma

    def test_second_quarantine_alerts_even_if_nobody_cleared_the_key(self):
        self.quarantine()
        st = reconcile.load_state("probe-agent")
        st["quarantined"] = False
        reconcile.save_state("probe-agent", st)   # kézzel feloldva, a kulcs ott maradt
        self.clock[0] += 5000
        self.quarantine()
        self.assertEqual(len(self.undelivered()), 2)

    def test_budget_alert_repeats_after_n_hours_while_it_persists(self):
        now = self.clock[0]
        st = reconcile.empty_state()
        st["restarts"] = [now - 300, now - 200, now - 100]
        acts = reconcile.decide(entry(), {"signals": {"process": {"state": "down", "data": {}}}, "pollers": []},
                                st, unit_active=False, locked=False, now=now)
        key, reason = acts[0]
        self.assertTrue(key.startswith("alert:budget:probe-agent:"))
        self.assertTrue(key.endswith(str(int(now - 300))))   # az epizód: a legrégebbi restart
        k = key[len("alert:"):]
        self.assertEqual(alerts.alert(k, reason, now=now), "stderr")
        self.assertEqual(alerts.alert(k, reason, now=now + 600), "dup")
        self.assertEqual(alerts.alert(k, reason, now=now + alerts.REPEAT_S + 1), "stderr")
        self.assertEqual(len(self.undelivered()), 2)

    def test_recovery_clears_keys(self):
        alerts.alert("budget:probe-agent:1", "x")
        alerts.alert("bridge-budget:probe-agent", "y")
        alerts.alert("bridge-budget:probe-agent-2", "z")
        alerts.clear("budget:probe-agent:")
        alerts.clear("bridge-budget:probe-agent", exact=True)
        self.assertEqual(sorted(json.loads((self.d / "alerts.json").read_text())), ["bridge-budget:probe-agent-2"])

    def test_postcheck_ok_clears_episode_keys(self):
        self.quarantine()
        st = reconcile.load_state("probe-agent")
        alerts.alert("budget:probe-agent:5", "x")
        reconcile._record_postcheck(entry(), st, {"status": reconcile.OK}, log=lambda m: None)
        self.assertEqual(json.loads((self.d / "alerts.json").read_text()), {})

    def test_legacy_true_counts_from_first_read(self):
        (self.d / "alerts.json").write_text(json.dumps({"rc:probe-agent:1": True}))
        self.assertEqual(alerts.alert("rc:probe-agent:1", "x"), "dup")
        self.assertIsInstance(json.loads((self.d / "alerts.json").read_text())["rc:probe-agent:1"], float)
        self.clock[0] += alerts.REPEAT_S + 1
        self.assertEqual(alerts.alert("rc:probe-agent:1", "x"), "stderr")


class Unquarantine(Base):
    def test_corrupt_state_file_gives_message_and_nonzero_exit(self):
        (self.d / "state").mkdir()
        (self.d / "state" / "probe-agent.json").write_text("{nem json")
        err = io.StringIO()
        with redirect_stderr(err):
            rc = self.unquarantine()
        self.assertEqual(rc, 1)
        self.assertIn("sérült", err.getvalue())
        self.assertEqual((self.d / "state" / "probe-agent.json").read_text(), "{nem json")   # nem írta felül


if __name__ == "__main__":
    unittest.main()
