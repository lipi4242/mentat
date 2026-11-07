#!/usr/bin/env python3
"""anytime_todo `me | ball | task … | case …`: the request each command sends,
and the usage guards that send nothing.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _todo_fixture import task  # noqa: E402
from _work_fixture import WorkCase  # noqa: E402


class TaskCase(WorkCase):
    def setUp(self):
        super().setUp()
        self.srv.tasks["T1"] = task("T1", "2026-11-06", rev=2, repeat=None)

    def gets(self) -> list[str]:
        return [p for m, p in self.srv.calls if m == "GET"]


class TestReads(TaskCase):
    def test_me_and_ball(self):
        self.assertEqual(self.cli("me")[0], 0)
        self.assertEqual(self.cli("ball")[0], 0)
        self.assertTrue(self.gets()[0].endswith("/me"))
        self.assertIn("ball=rocky", self.gets()[1])
        self.assertIn("kind=all", self.gets()[1])

    def test_review_due_is_for_me(self):
        self.assertEqual(self.cli("case", "review-due")[0], 0)
        self.assertTrue(self.gets()[0].endswith("/cases/review-due?for=rocky"))


class TestModuleEntry(TaskCase):
    def test_python_m_anytime_todo_is_the_cli(self):
        import os
        import subprocess
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(self.root), *sys.path]))
        r = subprocess.run([sys.executable, "-m", "anytime_todo", "me"], cwd=self.root, env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"handle": "rocky"', r.stdout)


class TestTask(TaskCase):
    def test_new_is_a_todo_and_a_rerun_is_the_same_request(self):
        for _ in range(2):
            self.assertEqual(self.cli("task", "new", "--title", "Számla", "--due", "2026-11-10")[0], 0)
        (_, path, a), (_, _, b) = self.sent()
        self.assertEqual((path, a["kind"], a["due_date"]), ("/tasks", "todo", "2026-11-10"))
        self.assertEqual(a["idem_key"], b["idem_key"])
        self.assertEqual(len(self.srv.idem), 1)

    def test_explicit_idem_wins(self):
        self.cli("task", "new", "--title", "x", "--idem", "meeting:2026-11-06:anna")
        self.assertEqual(self.sent()[0][2]["idem_key"], "meeting:2026-11-06:anna")

    def test_update_needs_a_field_and_sends_set(self):
        self.assertEqual(self.cli("task", "update", "T1")[0], 2)
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.cli("task", "update", "T1", "--title", "Új cím")[0], 0)
        self.assertEqual(self.sent()[0][2], {"set": {"title": "Új cím"}, "expected_rev": 2})

    def test_done_passes_the_children_choice(self):
        self.assertEqual(self.cli("task", "done", "T1", "--children", "keep")[0], 0)
        self.assertEqual(self.sent("complete")[0][2], {"expected_rev": 2, "children": "keep"})

    def test_comment_retries_once_when_the_rev_moved(self):
        self.srv.race = True
        rc, out = self.cli("task", "comment", "T1", "--text", "kész a terv")
        self.assertEqual(rc, 0, out)
        self.assertEqual([b["expected_rev"] for _, _, b in self.sent("comments")], [2, 3])

    def test_a_given_rev_is_never_retried(self):
        self.srv.race = True
        self.assertEqual(self.cli("task", "comment", "T1", "--text", "x", "--rev", "2")[0], 1)
        self.assertEqual(len(self.sent("comments")), 1)

    def test_blank_text_is_refused(self):
        self.assertEqual(self.cli("task", "comment", "T1", "--text", "  ")[0], 2)
        self.assertEqual(self.sent(), [])


class TestCaseCommands(TaskCase):
    def test_new_case_sends_its_fields_under_case(self):
        rc, out = self.cli("case", "new", "--title", "Járatkésés", "--goal", "kártérítés megjön",
                           "--next-action", "igazolás pótlása", "--waiting-on", "légitársaság",
                           "--review-every", "7", "--brain-ref", "data/cases/jarat.md")
        self.assertEqual(rc, 0, out)
        (_, path, body), = self.sent()
        self.assertEqual((path, body["kind"]), ("/tasks", "case"))
        self.assertEqual(body["case"], {"goal": "kártérítés megjön", "next_action": "igazolás pótlása",
                                        "waiting_on": "légitársaság", "review_every": 7,
                                        "brain_ref": "data/cases/jarat.md"})
        self.assertNotIn("repeat_rule", body)

    def test_a_case_needs_a_goal_and_cannot_repeat(self):
        self.assertEqual(self.cli("case", "new", "--title", "x")[0], 2)
        self.assertEqual(self.cli("case", "new", "--title", "x", "--goal", "g", "--repeat", "weekly")[0], 2)
        self.assertEqual(self.cli("case", "new", "--title", "x", "--goal", "g", "--review-every", "0")[0], 2)
        self.assertEqual(self.sent(), [])

    def test_update_review_confirm(self):
        self.assertEqual(self.cli("case", "update", "T1", "--next-action", "telefon")[0], 0)
        self.assertEqual(self.sent()[0][2], {"case": {"next_action": "telefon"}, "expected_rev": 2})
        self.assertEqual(self.cli("case", "review", "T1", "--note", "nincs változás")[0], 0)
        self.assertEqual(self.sent("review")[0][2], {"note": "nincs változás", "expected_rev": 3})
        self.assertEqual(self.cli("case", "confirm", "T1")[0], 0)
        self.assertEqual(self.sent("confirm")[0][2], {"expected_rev": 4})


if __name__ == "__main__":
    unittest.main()
