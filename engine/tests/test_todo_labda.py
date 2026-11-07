#!/usr/bin/env python3
"""Concern `todo_labda`: planned only when there are events for me after my
cursor, or an item was issued to me; otherwise silence. Off when not configured,
quiet on errors, and no API call while the todo API is in backoff.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import os
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
from anytime_engine import clock  # noqa: E402
from anytime_engine.prompts import get_prompt  # noqa: E402
from anytime_engine.reducer import reduce  # noqa: E402
from anytime_engine.state import State  # noqa: E402


class LabdaCase(WorkCase):
    def plan(self, state: State | None = None):
        acts = reduce("hourly", state or State())["actions"]
        return next((a for a in acts if a["concern"] == "todo_labda"), None)


class TestWhen(LabdaCase):
    def test_nothing_for_me_is_silence(self):
        self.srv.review_due = [{"id": "C1", "title": "Ügy", "rev": 1}]   # alone: not a reason
        self.assertIsNone(self.plan())

    def test_an_unacked_event_plans_it(self):
        self.srv.events = [{"seq": 4, "event": "mentioned"}]
        a = self.plan()
        self.assertIsNotNone(a)
        self.assertTrue(a["context"]["todo.labda"]["pending"])
        self.assertIn("changes --ack", get_prompt(a["action"], a["context"]))

    def test_acked_events_are_silence_again(self):
        self.srv.events = [{"seq": 4}]
        self.cli("changes")
        self.cli("changes", "--ack", "4")
        self.assertIsNone(self.plan())

    def test_an_issued_item_plans_it_and_rides_with_review_due(self):
        self.srv.items["I1"] = item(stage="issued")
        self.srv.review_due = [{"id": "C1", "title": "Ügy", "rev": 1}]
        ctx = self.plan()["context"]["todo.labda"]
        self.assertEqual([i["key"] for i in ctx["issued"]], ["WEB-7"])
        self.assertEqual([c["id"] for c in ctx["review_due"]], ["C1"])

    def test_a_taken_item_is_not_a_reason(self):
        self.srv.items["I1"] = item(stage="taken")
        self.assertIsNone(self.plan())


class TestQuiet(LabdaCase):
    def test_not_configured_is_off(self):
        for k in ("TODO_API", "TODO_HANDLE"):
            os.environ.pop(k)
        self.srv.events = [{"seq": 1}]
        self.assertIsNone(self.plan())
        self.assertEqual(self.srv.calls, [])

    def test_api_down_is_quiet(self):
        self.srv.down = True
        self.srv.events = [{"seq": 1}]
        self.assertIsNone(self.plan())

    def test_no_call_while_the_todo_api_is_in_backoff(self):
        st = State()
        st.set_cache("anytime_todo.api", {"failures": 1, "since": clock.stamp(st.now()),
                                          "retry_at": clock.stamp(st.now() + timedelta(minutes=5))})
        self.srv.events = [{"seq": 1}]
        self.assertIsNone(self.plan(st))
        self.assertEqual([p for m, p in self.srv.calls if "/changes" in p or "/items" in p], [])


if __name__ == "__main__":
    unittest.main()
