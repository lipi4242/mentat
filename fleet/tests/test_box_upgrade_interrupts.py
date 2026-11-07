"""`fleet box-upgrade` megszakítva és félúton (PR #20 review B1, B2, SF1–SF3):
bármilyen kivétel az első frissített ágens után megállás, előtte teljes visszaállítás a
piszkos unitok újratelepítésével; a timerek csak az ellenőrzés után indulnak; a
bukott visszaállítás nem „rolled-back"; a SIGHUP is visszaállít.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import signal
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet.box_signals import interruptible  # noqa: E402
from fleet.box_upgrade import run  # noqa: E402
from box_fixture import Box  # noqa: E402

START = "systemctl --user start fleet-reconcile.timer fleet-reconcile-fast.timer"


def is_install(agent):
    return lambda cmd: cmd[0].endswith("bin/fleet") and cmd[1:] == ["install", agent]


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Box()
        b = self.box
        b.unit_as("a", "v1"); b.unit_as("b", "v1")

    def tearDown(self):
        self.box.cleanup()


class TestAfterFirstUpgrade(Base):
    def test_interrupt_after_first_agent_halts_and_repairs_forward(self):
        for exc in (KeyboardInterrupt(), OSError("boom")):
            with self.subTest(exc=type(exc).__name__):
                b = self.box = (self.box.cleanup() or Box())
                b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1")
                c = b.ctx()
                b.raise_once(c, is_install("b"), exc)
                r = run(c)
                self.assertEqual(r["result"], "halted", b.out)
                self.assertEqual(b.head(), b.sha["v2"])                  # a checkout NEM áll vissza
                self.assertIn("fleet[v2] install b", b.calls())          # a félbehagyott b előre javítva
                self.assertNotIn("fleet[v1] install a", b.calls())

    def test_render_failure_on_later_agent_halts(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1")
        b.fail("v2-render-b")
        r = run(b.ctx())
        self.assertEqual(r["result"], "halted")
        self.assertEqual(b.head(), b.sha["v2"])


class TestCanaryInterrupted(Base):
    def test_interrupted_canary_rolls_back_and_reinstalls_with_old_code(self):
        for layout in ("symlink", "legacy"):
            with self.subTest(layout=layout):
                b = self.box = (self.box.cleanup() or Box())
                b.symlink_at("v1") if layout == "symlink" else b.legacy()
                b.unit_as("a", "v1"); b.unit_as("b", "v1")
                c = b.ctx()
                b.raise_once(c, is_install("a"), KeyboardInterrupt())
                r = run(c)
                self.assertEqual(r["result"], "rolled-back", b.out)
                old = "v1" if layout == "symlink" else "legacy"
                self.assertIn(f"fleet[{old}] install a", b.calls())       # unit + felügyelet a régi kóddal
                self.assertFalse((b.home / "fleet-leader").is_symlink() and layout == "legacy")
                self.assertEqual(os.listdir(os.environ["FLEET_MAINTENANCE_DIR"]), [])

    def test_child_install_killed_by_signal_is_reinstalled(self):
        b = self.box
        b.symlink_at("v1")
        b.fail("v2-killed-a")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        self.assertIn("fleet[v1] install a", b.calls())

    def test_sighup_mid_install_rolls_back_and_restarts_timers(self):
        b = self.box
        b.symlink_at("v1")
        b.fail("v2-hup-parent-a")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back", b.out)
        self.assertIn("SIGHUP", r["error"])
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertEqual(b.calls()[-1], "fleet[v1] install a")
        self.assertIn(START, b.calls())
        self.assertIs(signal.getsignal(signal.SIGHUP), signal.SIG_DFL)     # a kezelő visszaállt


class TestCheckout(Base):
    def test_timers_start_only_after_verify(self):
        b = self.box
        b.symlink_at("v1")
        run(b.ctx())
        calls = b.calls()
        self.assertEqual(calls.count(START), 1)
        self.assertLess(calls.index("fleet[v2] reconcile --observe"), calls.index(START))

    def test_interrupted_clone_is_cleaned_up(self):
        b = self.box
        b.legacy()
        c = b.ctx()

        def partial(cmd):
            if cmd[:2] == ["git", "clone"]:
                (b.home / "src/mentat/.git").mkdir(parents=True)   # a félbehagyott klón nyoma
                return True
            return False
        b.raise_once(c, partial, KeyboardInterrupt())
        self.assertEqual(run(c)["result"], "rolled-back")
        self.assertFalse((b.home / "src/mentat").exists())
        self.assertTrue((b.home / "fleet-leader/.git").is_dir())

    def test_interrupted_git_checkout_is_restored(self):
        b = self.box
        b.symlink_at("v1")
        c = b.ctx()
        b.raise_once(c, lambda cmd: "checkout" in cmd and b.sha["v2"] in cmd, KeyboardInterrupt(), after=True)
        self.assertEqual(run(c)["result"], "rolled-back")
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertIn(START, b.calls())

    def test_failed_rollback_is_not_reported_as_rolled_back(self):
        b = self.box
        b.symlink_at("v1")
        b.fail("v2-install-a")
        b.fb.fail_on("start fleet-reconcile.timer")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "rollback-failed")
        self.assertTrue(any("BUKOTT" in n for n in c.not_rolled_back), c.not_rolled_back)
        self.assertIn("RÉSZBEN BUKOTT", "\n".join(b.out))


class TestSignals(unittest.TestCase):
    def test_sighup_and_sigterm_become_keyboard_interrupt(self):
        for sig in (signal.SIGHUP, signal.SIGTERM):
            with self.assertRaises(KeyboardInterrupt), interruptible():
                os.kill(os.getpid(), sig)
                signal.pause() if hasattr(signal, "pause") else None
        self.assertIs(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)


if __name__ == "__main__":
    unittest.main()
