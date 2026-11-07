"""`fleet box-upgrade` (PR #20 review SF4, SF5 és apróságok): a hídcsere újraindítás,
dolgozó ágensnél kimarad; a híd-visszaállítás a unit-fájlt is visszahozza, és régebbi
mentést nem hoz vissza; origin-egyezés; az ágra áll vissza; a nyugta privát.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import stat
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet.box_upgrade import run  # noqa: E402
from box_fixture import Box, git  # noqa: E402

BRIDGE_UNIT = "[Unit]\n# régi híd-unit\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.box = b = Box()
        b.symlink_at("v2"); b.unit_as("a", "v2"); b.unit_as("b", "v2"); b.bridge_as("a", "2.0.1")
        (b.units / "a-telegram-bridge.service").write_text(BRIDGE_UNIT)

    def tearDown(self):
        self.box.cleanup()

    def baks(self):
        return sorted(p.name for p in (self.box.home / ".config/a").glob("sub-etha.bak-*"))


class TestBusyBridge(Base):
    def test_busy_agent_skips_bridge_too(self):
        b = self.box
        b.busy("a")
        c = b.ctx()
        self.assertEqual(run(c)["result"], "partial")
        self.assertEqual(c.agents[0]["result"], "skipped-busy")
        self.assertFalse(any("bridge" in x for x in b.calls()), b.calls())

    def test_plan_calls_bridge_drift_a_restart(self):
        b = self.box
        run(b.ctx(dry_run=True))
        self.assertIn("az ágens is újraindulhat", "\n".join(b.out))


class TestBridgeRollback(Base):
    def test_failure_before_backup_does_not_restore_an_older_backup(self):
        b = self.box
        old = b.home / ".config/a/sub-etha.bak-20200101-000000"     # egy régebbi frissítés mentése
        old.mkdir()
        b.fail("v2-bridge-early-a")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        self.assertNotIn("fleet[v2] bridge rollback a", b.calls())   # visszalépés lenne
        self.assertTrue(old.is_dir())
        self.assertEqual((b.units / "a-telegram-bridge.service").read_text(), BRIDGE_UNIT)

    def test_failure_after_backup_rolls_back_and_restores_unit_file(self):
        b = self.box
        b.fail("v2-bridge-half-a")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        self.assertIn("fleet[v2] bridge rollback a", b.calls())
        self.assertEqual((b.units / "a-telegram-bridge.service").read_text(), BRIDGE_UNIT)
        self.assertIn("systemctl --user daemon-reload", b.calls())


class TestNits(unittest.TestCase):
    def setUp(self):
        self.box = Box()

    def tearDown(self):
        self.box.cleanup()

    def test_foreign_origin_is_refused(self):
        b = self.box
        b.symlink_at("v1")
        r = run(_with_url(b.ctx(), "https://example.invalid/other"))
        self.assertEqual(r["result"], "failed-plan")
        self.assertIn("originje", r["error"])

    def test_rollback_returns_to_the_branch(self):
        b = self.box
        b.symlink_at("v1")
        src = b.home / "src/mentat"
        git(src, "checkout", "-q", "-B", "stable", b.sha["v1"])
        b.unit_as("a", "v1"); b.fail("v2-install-a")
        self.assertEqual(run(b.ctx())["result"], "rolled-back")
        self.assertEqual(git(src, "symbolic-ref", "--short", "HEAD"), "stable")

    def test_receipt_is_private(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1")
        c = b.ctx()
        run(c)
        self.assertEqual(stat.S_IMODE(c.receipt_dir.stat().st_mode), 0o700)
        for f in [*c.receipt_dir.iterdir(), b.home / ".config/fleet/upgrades.log"]:
            self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600, f)


def _with_url(ctx, url):
    ctx.url = url
    return ctx


if __name__ == "__main__":
    unittest.main()
