"""The hermetic guard judges the TEST run, not the live box (Rilí, 2026-10-23: #62 and #66 failed
three times on ~/.config/fleet/state/reconcile.lock, which the box's fleet-reconcile timer
rewrites). Lock files under state/ are ignored; any other change still fails the guard.
"""
from __future__ import annotations
import _hermetic  # noqa: F401
import unittest


class LockIgnored(unittest.TestCase):
    def test_live_locks_are_not_a_test_write(self):
        before = {"state/reconcile.lock": (0, 1), "registry": (10, 1), "state/x/y.lock": (0, 1)}
        after = {"state/reconcile.lock": (0, 2), "registry": (10, 1), "state/x/y.lock": (0, 9)}
        self.assertEqual(_hermetic.changed(before, after), [])

    def test_any_other_change_is_still_reported(self):
        before = {"state/reconcile.lock": (0, 1), "registry": (10, 1)}
        after = {"state/reconcile.lock": (0, 1), "registry": (11, 2), "state/agent.json": (5, 3),
                 "lock": (1, 1)}
        self.assertEqual(_hermetic.changed(before, after), ["lock", "registry", "state/agent.json"])


if __name__ == "__main__":
    unittest.main()
