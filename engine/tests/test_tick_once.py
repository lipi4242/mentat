#!/usr/bin/env python3
"""tick --once: the session-start fallback where no scheduler ticks. It runs one locked
tick only when no scheduled tick landed in the last hour, uses no recorded executor
(the session is the executor), and prints the work for the session: the todo_labda
items (fake todo API) with their rules.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _work_fixture import WorkCase, item  # noqa: E402
from anytime_engine import clock, tick  # noqa: E402


class TestOnce(WorkCase):
    def setUp(self):
        super().setUp()
        self.state = self.root / "data" / "state"
        self.srv.items["I1"] = item(stage="issued")
        # a recorded executor must NOT run at session start
        (self.root / "mentat.json").write_text(json.dumps({
            "schema": 1, "components": {"engine": {"plugins": ["anytime_todo"],
                                                   "exec": "echo EXEC-RAN > exec.txt"}}}))

    def once(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = tick.main(["hourly", "--once", "--no-discover"])
        return rc, out.getvalue(), err.getvalue()

    def stamp_last_tick(self, minutes_ago, **extra):
        self.state.mkdir(parents=True, exist_ok=True)
        at = clock.stamp(clock.now() - timedelta(minutes=minutes_ago))
        (self.state / "last-tick.json").write_text(json.dumps({"trigger": "hourly", "at": at, **extra}))

    def test_a_scheduled_tick_that_left_work_undone_does_not_stop_it(self):
        # the desktop's timer runs only the cases deliverer: the todo actions it could not
        # hand to anyone must still reach the session at its start
        self.stamp_last_tick(20, handled=0, unhandled=1)
        rc, out, err = self.once()
        self.assertEqual(rc, 0, err)
        self.assertIn("WEB-7", out)

    def test_without_a_scheduler_it_ticks_and_prints_the_ball_items(self):
        rc, out, err = self.once()
        self.assertEqual(rc, 0, err)
        self.assertIn("todo_labda", out)
        self.assertIn("WEB-7", out)                 # the item issued to me
        self.assertIn("item take", out)             # and what to do with it
        self.assertFalse((self.root / "exec.txt").exists())

    def test_it_is_not_a_scheduled_tick_so_it_leaves_that_stamp_alone(self):
        # last-tick.json says a SCHEDULER ticked; a session-start tick must not fake it,
        # or a desktop without a scheduler would look healthy to the done-check
        rc, _, err = self.once()
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.state / "last-tick.json").exists())
        self.assertTrue((self.state / "orchestrator-heartbeat.json").exists())

    def test_a_scheduler_that_ticked_within_the_hour_makes_it_a_no_op(self):
        self.stamp_last_tick(20)
        rc, out, err = self.once()
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("scheduled tick ran", err)
        self.assertEqual(self.srv.calls, [])

    def test_an_old_scheduled_tick_does_not_stop_it(self):
        self.stamp_last_tick(180)
        rc, out, _ = self.once()
        self.assertEqual(rc, 0)
        self.assertIn("WEB-7", out)

    def test_nothing_to_do_prints_nothing(self):
        self.srv.items.clear()
        rc, out, _ = self.once()
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
