#!/usr/bin/env python3
"""Ágens-interjú (11-09): a `ball` jelöli a lejártat (`overdue`, és elöl áll), a `changes`
kimenete és súgója megmondja, MIKOR és PONTOSAN milyen paranccsal kell nyugtázni. Csak új mezők:
a régi kulcsok változatlanok.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _todo_fixture import task  # noqa: E402
from _work_fixture import WorkCase  # noqa: E402

# 2026-11-09 10:00 Budapest (CET, UTC+1)
NOW = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)


class TestBallOverdue(WorkCase):
    def setUp(self):
        super().setUp()
        self.srv.tasks.clear()
        for t in (task("FUTURE", "2026-11-12"), task("TODAY", "2026-11-09"),
                  task("LATE", "2026-11-02"), task("TODAY_TIME", "2026-11-09", time="09:30"),
                  task("TODAY_LATER", "2026-11-09", time="18:00"),
                  {"id": "CASE", "title": "ügy határidő nélkül", "status": "open", "due_date": None}):
            self.srv.tasks[t["id"]] = t

    def ball(self) -> list[dict]:
        with mock.patch("anytime_engine.clock._utcnow", return_value=NOW):
            rc, out = self.cli("ball")
        self.assertEqual(rc, 0, out)
        return json.loads(out)

    def test_every_row_says_overdue_and_overdue_comes_first(self):
        rows = self.ball()
        self.assertEqual({r["id"]: r["overdue"] for r in rows},
                         {"FUTURE": False, "TODAY": False, "LATE": True, "TODAY_TIME": True,
                          "TODAY_LATER": False, "CASE": False})
        self.assertEqual([r["id"] for r in rows][:2], ["LATE", "TODAY_TIME"])
        self.assertEqual([r["id"] for r in rows][2:], ["FUTURE", "TODAY", "TODAY_LATER", "CASE"])  # server order

    def test_old_fields_are_kept(self):
        late = next(r for r in self.ball() if r["id"] == "LATE")
        self.assertEqual({k: v for k, v in late.items() if k != "overdue"}, self.srv.tasks["LATE"])


class TestChangesSaysHowToAck(WorkCase):
    def setUp(self):
        super().setUp()
        self.srv.events = [{"seq": n, "event": "commented", "task_id": "T1"} for n in (3, 5, 9)]

    def test_output_names_the_exact_ack_command_and_when(self):
        rc, out = self.cli("changes")
        self.assertEqual(rc, 0, out)
        d = json.loads(out)
        self.assertEqual(d["ack_with"], "changes --ack 9")            # unchanged
        self.assertEqual(d["ack_command"], "python3 -m anytime_todo.cli changes --ack 9")
        self.assertIn("after you handled", d["ack_when"])
        self.assertEqual(self.cli("changes", "--ack", "9")[0], 0)
        d = json.loads(self.cli("changes")[1])
        self.assertIsNone(d["ack_command"])                           # nothing left to ack

    def test_help_says_when_and_how(self):
        _, top = self.cli("--help")
        self.assertIn("changes --ack <last_seq>", " ".join(top.split()))
        _, sub = self.cli("changes", "--help")
        for part in ("WHEN: after you handled", "python3 -m anytime_todo.cli changes --ack <last_seq>",
                     "ack <id|KEY>"):
            self.assertIn(part, " ".join(sub.split()))


if __name__ == "__main__":
    unittest.main()
