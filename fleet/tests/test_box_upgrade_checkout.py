"""`fleet box-upgrade`: checkout-csere (legacy → symlink, tag → tag), dry-run,
visszaállítás a kanári vagy az ellenőrzés bukásakor, nyugta.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet.box_upgrade import run  # noqa: E402
from box_fixture import Box  # noqa: E402


def tree(root: Path) -> dict:
    """Útvonal → (mtime_ns, symlink-cél) — a dry-run összevetéséhez."""
    out = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        out[str(p)] = (st.st_mtime_ns, os.readlink(p) if p.is_symlink() else None)
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Box()

    def tearDown(self):
        self.box.cleanup()


class TestLegacySwitch(Base):
    def test_legacy_becomes_symlink_and_agents_run_new_code(self):
        b = self.box
        b.legacy()
        b.unit_as("a", "v1"); b.unit_as("b", "v1")
        r = run(b.ctx())
        self.assertEqual(r["result"], "ok", b.out)
        link = b.home / "fleet-leader"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (b.home / "src/mentat/fleet").resolve())
        self.assertTrue((b.home / "fleet-leader.pre-mentat/.git").is_dir())
        self.assertEqual(b.head(), b.sha["v2"])
        calls = b.calls()
        stop = calls.index("systemctl --user stop fleet-reconcile.timer fleet-reconcile-fast.timer")
        start = calls.index("systemctl --user start fleet-reconcile.timer fleet-reconcile-fast.timer")
        self.assertLess(stop, start)
        self.assertIn("fleet[legacy] doctor", calls)          # pillanatkép a RÉGI kóddal
        self.assertIn("fleet[v2] install a", calls)           # az ágenst az ÚJ kód telepíti
        self.assertIn("fleet[v2] install b", calls)

    def test_receipt_and_log_line(self):
        b = self.box
        b.legacy(); b.unit_as("a", "v1"); b.unit_as("b", "v2")
        c = b.ctx()
        run(c)
        lines = (b.home / ".config/fleet/upgrades.log").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual((rec["result"], rec["layout"], rec["to"]), ("ok", "legacy", "v2"))
        self.assertEqual({a["agent"]: a["result"] for a in rec["agents"]}, {"a": "ok", "b": "noop"})
        for f in ("pre-state.json", "doctor.pre.txt", "fleet-leader-refs.pre.txt", "plan.txt", "result.json"):
            self.assertTrue((c.receipt_dir / f).is_file(), f)
        self.assertEqual(json.loads((c.receipt_dir / "pre-state.json").read_text())["layout"], "legacy")

    def test_legacy_canary_failure_restores_the_old_dir(self):
        b = self.box
        b.legacy(); b.unit_as("a", "v1"); b.unit_as("b", "v1")
        b.fail("v2-install-a")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        link = b.home / "fleet-leader"
        self.assertFalse(link.is_symlink())
        self.assertTrue((link / ".git").is_dir())
        self.assertFalse((b.home / "fleet-leader.pre-mentat").exists())
        self.assertIn("fleet[legacy] release", b.calls())
        self.assertNotIn("fleet[v2] install b", b.calls())
        self.assertIn("systemctl --user start fleet-reconcile.timer fleet-reconcile-fast.timer", b.calls()[-3:])


class TestTagSwitch(Base):
    def test_symlink_layout_switches_tag(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1")
        r = run(b.ctx())
        self.assertEqual(r["result"], "ok", b.out)
        self.assertEqual(b.head(), b.sha["v2"])
        self.assertIn("fleet[v1] reconcile --observe", b.calls())
        self.assertIn("fleet[v2] reconcile --observe", b.calls())

    def test_canary_failure_rolls_checkout_back(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1"); b.unit_as("b", "v1")
        b.fail("v2-install-a")
        c = b.ctx()
        r = run(c)
        self.assertEqual(r["result"], "rolled-back")
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertNotIn("fleet[v2] install b", b.calls())
        self.assertEqual([a["result"] for a in c.agents], ["failed"])
        self.assertTrue(any("checkout visszaállítva" in n for n in c.rolled_back), c.rolled_back)
        self.assertEqual(b.calls()[-1], "fleet[v1] release")      # a release-tuple megint a régié
        self.assertEqual(json.loads((b.home / ".config/fleet/upgrades.log").read_text())["result"], "rolled-back")

    def test_bad_release_tuple_rolls_back(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1")
        b.fail("v2-release")
        self.assertEqual(run(b.ctx())["result"], "rolled-back")
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertFalse(any(c.startswith("fleet[v2] install") for c in b.calls()))

    def test_new_reconcile_action_rolls_back(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1")
        (b.fb.dir / "observe-v2").write_text("a: restart — leállt (nem hajtom végre)\n")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        self.assertIn("beavatkozna", r["error"])
        self.assertEqual(b.head(), b.sha["v1"])

    def test_dirty_checkout_is_refused_untouched(self):
        b = self.box
        b.symlink_at("v1"); b.unit_as("a", "v1")
        (b.home / "src/mentat/fleet/FAKEVER").write_text("kézzel\n")
        r = run(b.ctx())
        self.assertEqual(r["result"], "rolled-back")
        self.assertEqual(b.head(), b.sha["v1"])
        self.assertNotIn("systemctl --user stop fleet-reconcile.timer fleet-reconcile-fast.timer", b.calls())


class TestDryRun(Base):
    def test_dry_run_touches_nothing(self):
        for layout in ("legacy", "symlink"):
            with self.subTest(layout=layout):
                b = self.box = (self.box.cleanup() or Box())
                b.legacy() if layout == "legacy" else b.symlink_at("v1")
                b.unit_as("a", "v1"); b.busy("b")
                before = tree(b.home)
                r = run(b.ctx(dry_run=True))
                self.assertEqual(r["result"], "dry-run")
                self.assertEqual(tree(b.home), before)
                self.assertFalse(any(c.startswith("systemctl") for c in b.calls()), b.calls())
                self.assertFalse(any(" install " in c or c.endswith(" release") for c in b.calls()))
                text = "\n".join(b.out)
                self.assertIn("DRY RUN", text)
                self.assertIn("DOLGOZIK", text)          # a terv mutatja a dolgozó ágenst


if __name__ == "__main__":
    unittest.main()
