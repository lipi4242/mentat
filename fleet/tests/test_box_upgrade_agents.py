"""`fleet box-upgrade` ágensenként: dolgozó ágens kihagyva, csak-híd drift
újraindítás nélkül, semmi-változás = semmi-restart, sorrend, megállás.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet import registry  # noqa: E402
from fleet.box_agent_plan import ordered  # noqa: E402
from fleet.box_upgrade import run  # noqa: E402
from box_fixture import Box  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Box()

    def tearDown(self):
        self.box.cleanup()

    def results(self, ctx):
        return {a["agent"]: a["result"] for a in ctx.agents}


class TestBusy(Base):
    def test_busy_agent_with_unit_change_is_skipped(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1"); b.busy("a")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "partial")
        self.assertEqual(self.results(c), {"a": "skipped-busy", "b": "ok"})
        self.assertNotIn("fleet[v2] install a", b.calls())
        self.assertIn("fleet[v2] install b", b.calls())


class TestCheap(Base):
    def test_bridge_only_drift_reinstalls_bridge_without_agent_restart(self):
        b = self.box
        b.symlink_at("v2"); b.unit_as("a", "v2"); b.unit_as("b", "v2"); b.bridge_as("a", "2.0.1")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "ok", b.out)
        calls = b.calls()
        self.assertIn("fleet[v2] bridge install a", calls)
        self.assertIn("systemctl --user restart a-telegram-bridge.service", calls)
        self.assertIn("fleet[v2] postcheck a --wait 30", calls)
        self.assertFalse(any(x.startswith("fleet[v2] install") for x in calls), calls)
        self.assertNotIn("systemctl --user restart a.service", calls)
        self.assertFalse(any("stop fleet-reconcile" in x for x in calls))   # a checkout nem mozdult
        self.assertEqual(self.results(c), {"a": "ok", "b": "noop"})
        self.assertEqual(os.listdir(os.environ["FLEET_MAINTENANCE_DIR"]), [])   # a zár feloldva

    def test_nothing_changed_means_no_restart_at_all(self):
        b = self.box
        b.symlink_at("v2"); b.unit_as("a", "v2"); b.unit_as("b", "v2"); b.bridge_as("a", "2.1.0")
        c = b.ctx()
        self.assertEqual(run(c)["result"], "ok")
        self.assertFalse(any(" restart" in x or " install" in x for x in b.calls()), b.calls())
        self.assertEqual(self.results(c), {"a": "noop", "b": "noop"})


class TestFailures(Base):
    def test_later_agent_failure_halts_and_keeps_checkout(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1")
        b.fail("v2-install-b")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "halted")
        self.assertEqual(b.head(), b.sha["v2"])
        self.assertEqual(self.results(c), {"a": "ok", "b": "failed"})
        self.assertTrue(any("frissítve marad: a" in n for n in c.not_rolled_back))

    def test_canary_bridge_failure_rolls_back_bridge_checkout_and_unit(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1"); b.bridge_as("a", "2.0.1")
        b.fb.fail_on("restart a-telegram-bridge.service")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "rolled-back")
        calls = b.calls()
        self.assertIn("fleet[v2] bridge rollback a", calls)
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertIn("fleet[v1] install a", calls)        # a unit a régi kóddal újra
        self.assertNotIn("fleet[v2] install b", calls)

    def test_pending_postcheck_is_not_a_failure_but_failed_is(self):
        b = self.box
        b.symlink_at("v2"); b.unit_as("a", "v1"); b.unit_as("b", "v2"); b.bridge_as("b", "2.0.1")
        b.fail("v2-ipending-a"); b.fail("v2-pending-b")
        c = b.ctx()
        self.assertEqual(run(c)["result"], "ok", b.out)
        self.assertEqual(self.results(c), {"a": "ok", "b": "ok"})
        self.assertIn("függő", " ".join(c.agents[1]["did"]))

    def test_failed_postcheck_after_bridge_rolls_the_bridge_back(self):
        b = self.box
        b.symlink_at("v2"); b.unit_as("a", "v2"); b.bridge_as("a", "2.0.1")
        b.fail("v2-postcheck-a")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "rolled-back")
        self.assertIn("FAILED", r["error"])
        self.assertIn("fleet[v2] bridge rollback a", b.calls())

    def test_unknown_agent_fails_before_anything(self):
        b = self.box
        b.symlink_at("v1")
        r = run(b.ctx(canary="nincs"))
        self.assertEqual(r["result"], "failed-plan")
        self.assertEqual(b.calls(), [])
        self.assertFalse((b.home / ".config/fleet/upgrades.log").exists())


class TestOrder(Base):
    def test_dormant_agents_are_left_out_unless_named(self):
        b = self.box
        b.entries = [registry.normalize({"agent": n, "workdir": f"/w/{n}", "host": "box1", **kw})
                     for n, kw in (("anna", {}), ("bela", {"status": "dormant"}))]
        self.assertEqual([e["agent"] for e in ordered(b.ctx())], ["anna"])
        self.assertEqual([e["agent"] for e in ordered(b.ctx(only=["bela"]))], ["bela"])

    def test_canary_first_proactive_late_last_list_at_the_end(self):
        b = self.box
        b.entries = [registry.normalize({"agent": n, "workdir": f"/w/{n}", "host": "box1", "proactive": p})
                     for n, p in (("anna", True), ("bela", False), ("cecil", True), ("dora", False),
                                  ("emil", False))]
        c = b.ctx(canary="emil", last=["bela", "anna"])
        self.assertEqual([e["agent"] for e in ordered(c)], ["emil", "dora", "cecil", "bela", "anna"])


if __name__ == "__main__":
    unittest.main()
