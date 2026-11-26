#!/usr/bin/env python3
"""tick --render: the work, as the model should read it — each planned action's @action prompt
(its rules plus its data), not the plan JSON with state_summary, context_needs and skip
reasons. Nothing due: exactly one line and exit 4, so a session cron or a wrapper stops
without reading JSON. It hands nothing to an executor (the reader is the executor).

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _bekotes_concern_fixture import DAY, T as BT, ConcernCase  # noqa: E402
from _todo_fixture import task  # noqa: E402
from _work_fixture import WorkCase, item  # noqa: E402
from anytime_engine import tick  # noqa: E402

AT = "2026-10-28T08:30"


def render(*extra):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = tick.main(["hourly", "--render", "--no-discover", *extra])
    return rc, out.getvalue(), err.getvalue()


class TestTodo(WorkCase):
    def setUp(self):
        super().setUp()
        os.environ["ANYTIME_TZ"] = "Europe/Budapest"

    def test_nothing_due_is_one_line_and_exit_4(self):
        rc, out, err = render("--dry-run", "--now", AT)
        self.assertEqual(rc, tick.NOTHING_DUE, err)
        self.assertEqual(rc, 4)
        self.assertEqual(len(out.strip().splitlines()), 1, out)

    def test_due_todo_and_ball_render_their_rules_not_the_plan_json(self):
        self.srv.tasks["A"] = task("A", "2026-10-27", title="Heti emlékeztető")
        self.srv.items["I1"] = item(stage="issued")
        rc, out, err = render("--dry-run", "--now", AT)
        self.assertEqual(rc, 0, err)
        for needle in ("## todo_esedekes", "Heti emlékeztető", "ONLY after it really happened",
                       "## todo_labda", "WEB-7", "changes --ack"):
            self.assertIn(needle, out)
        for gone in ("state_summary", "context_needs", "skip_reasons", '"actions"'):
            self.assertNotIn(gone, out)

    def test_a_recorded_executor_is_not_run(self):
        (self.root / "mentat.json").write_text(
            '{"schema": 1, "components": {"engine": {"plugins": ["anytime_todo"], '
            '"exec": "echo RAN > exec.txt"}}}')
        self.srv.tasks["A"] = task("A", "2026-10-27")
        rc, out, _ = render()
        self.assertEqual(rc, 0)
        self.assertIn("## todo_esedekes", out)
        self.assertFalse((self.root / "exec.txt").exists())


class TestBekotes(ConcernCase):
    def test_the_bekotes_action_renders_its_three_steps(self):
        self.cli("--baseline")
        self.commit("munka/web", "domain váltás")
        rc, out, err = render("--dry-run", "--now", (BT + 2 * DAY).isoformat(timespec="minutes"))
        self.assertEqual(rc, 0, err)
        self.assertIn("## bekotes_frissites", out)
        self.assertNotIn("Unknown action", out)


if __name__ == "__main__":
    unittest.main()
