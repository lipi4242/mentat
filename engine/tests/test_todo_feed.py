#!/usr/bin/env python3
"""anytime_todo `changes [--ack]`: the cursor is the server's seq, it moves only
with an ack, never past what was shown, and every write is locked and atomic.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _work_fixture import WorkCase  # noqa: E402


class FeedCase(WorkCase):
    def setUp(self):
        super().setUp()
        self.srv.events = [{"seq": n, "event": "commented", "task_id": "T1"} for n in (3, 5, 9)]

    def changes(self) -> dict:
        rc, out = self.cli("changes")
        self.assertEqual(rc, 0, out)
        return json.loads(out)

    def cursor(self) -> dict:
        return json.loads(self.mod("feed").path().read_text())["handles"][self.key()]

    def key(self, api: str | None = None) -> str:
        return self.mod("feed").key(api or os.environ["TODO_API"], "rocky")


class TestCursor(FeedCase):
    def test_reading_does_not_move_the_cursor(self):
        first = self.changes()
        self.assertEqual([e["seq"] for e in first["events"]], [3, 5, 9])
        self.assertEqual(first["last_seq"], 9)
        self.assertEqual([e["seq"] for e in self.changes()["events"]], [3, 5, 9])  # crash = reread
        self.assertEqual(self.cursor()["acked"], 0)

    def test_ack_moves_it_and_the_next_read_starts_after(self):
        self.changes()
        self.assertEqual(self.cli("changes", "--ack", "5")[0], 0)
        self.assertEqual([e["seq"] for e in self.changes()["events"]], [9])
        q = [p for m, p in self.srv.calls if "/changes" in p][-1]
        self.assertIn("since=5", q)
        self.assertIn("for=rocky", q)

    def test_ack_past_what_was_shown_is_refused(self):
        self.changes()
        rc, out = self.cli("changes", "--ack", "10")
        self.assertEqual(rc, 1)
        self.assertIn("past the last event shown", out)
        self.assertEqual(self.cursor()["acked"], 0)

    def test_ack_before_any_read_is_refused(self):
        rc, _ = self.cli("changes", "--ack", "3")
        self.assertEqual(rc, 1)

    def test_ack_backwards_is_refused(self):
        self.changes()
        self.cli("changes", "--ack", "9")
        rc, out = self.cli("changes", "--ack", "3")
        self.assertEqual(rc, 1)
        self.assertIn("behind the cursor", out)
        self.assertEqual(self.cursor()["acked"], 9)

    def test_pages_are_followed(self):
        self.srv.events = [{"seq": n} for n in range(1, 251)]
        got = self.changes()
        self.assertEqual(len(got["events"]), 250)
        self.assertFalse(got["more"])
        self.assertEqual(len([p for m, p in self.srv.calls if "/changes" in p]), 3)

    def test_a_long_backlog_is_capped_and_says_more(self):
        self.srv.events = [{"seq": n} for n in range(1, 701)]
        got = self.changes()
        self.assertEqual((len(got["events"]), got["last_seq"], got["more"]), (500, 500, True))


class TestOwnWrites(FeedCase):
    """11-08 terep: a `changes` a saját írásaimat ne adja vissza hírként (két ágens kézzel szűrt)."""
    def setUp(self):
        super().setUp()
        self.srv.events = [{"seq": 3, "actor_id": "P-OTHER"}, {"seq": 5, "actor_id": "P-ROCKY"},
                           {"seq": 9, "actor_id": "P-ROCKY"}]

    def test_own_writes_are_left_out_but_the_cursor_steps_over_them(self):
        got = self.changes()
        self.assertEqual(([e["seq"] for e in got["events"]], got["own_skipped"], got["last_seq"]), ([3], 2, 9))
        self.assertEqual(got["ack_with"], "changes --ack 9")
        self.assertEqual(self.cli("changes", "--ack", "9")[0], 0)
        self.assertEqual(self.changes()["events"], [])

    def test_all_shows_them(self):
        rc, out = self.cli("changes", "--all")
        self.assertEqual([e["seq"] for e in json.loads(out)["events"]], [3, 5, 9])

    def test_ack_answers_json(self):
        self.changes()
        rc, out = self.cli("changes", "--ack", "5")
        self.assertEqual((rc, json.loads(out)), (0, {"handle": "rocky", "acked": 5}))

    def test_pending_ignores_own_writes(self):
        feed = self.mod("feed")
        from anytime_todo.api import Client
        c = Client(os.environ["TODO_API"], "test-token-not-a-secret")
        self.assertTrue(feed.pending(c, "rocky"))
        self.srv.events = [{"seq": n, "actor_id": "P-ROCKY"} for n in range(1, 160)]
        self.assertFalse(feed.pending(c, "rocky"))           # 159 saját esemény, két lapon át
        self.srv.events.append({"seq": 170, "actor_id": "P-OTHER"})
        self.assertTrue(feed.pending(c, "rocky"))
        self.srv.events = [{"seq": n, "actor_id": "P-ROCKY"} for n in range(1, 700)]
        self.assertTrue(feed.pending(c, "rocky"))            # a sapkán túl: kétség esetén ébreszt
        self.srv.events = []
        self.assertFalse(feed.pending(c, "rocky"))


class TestFile(FeedCase):
    def test_unreadable_cursor_is_never_overwritten(self):
        p = self.mod("feed").path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{torn")
        rc, out = self.cli("changes")
        self.assertEqual(rc, 1)
        self.assertIn("unreadable", out)
        self.assertEqual(p.read_text(), "{torn")

    def test_no_tmp_file_is_left_behind(self):
        self.changes()
        self.cli("changes", "--ack", "9")
        left = [f.name for f in self.mod("feed").path().parent.iterdir() if f.suffix == ".tmp"]
        self.assertEqual(left, [])

    def test_concurrent_acks_lose_nothing(self):
        """Two processes ack different handles 60 times each: the lock keeps both."""
        p = self.mod("feed").path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"schema": 1, "handles": {
            f"http://x {h}": {"acked": 0, "seen": 1000} for h in ("a", "b")}}))
        code = ("import sys; from anytime_todo import feed\n"
                "for n in range(1, 61): feed.ack('http://x', sys.argv[1], n)\n")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(self.root), *sys.path]))
        procs = [subprocess.Popen([sys.executable, "-c", code, h], env=env, cwd=self.root)
                 for h in ("a", "b")]
        self.assertEqual([pr.wait(timeout=60) for pr in procs], [0, 0])
        handles = json.loads(p.read_text())["handles"]
        self.assertEqual((handles["http://x a"]["acked"], handles["http://x b"]["acked"]), (60, 60))


class TestInstance(FeedCase):
    def test_another_api_starts_at_zero_and_reads_everything(self):
        self.changes()
        self.cli("changes", "--ack", "9")
        self.assertEqual(self.changes()["events"], [])
        os.environ["TODO_API"] = os.environ["TODO_API"].replace("localhost", "127.0.0.1")
        self.assertEqual([e["seq"] for e in self.changes()["events"]], [3, 5, 9])
        q = [p for m, p in self.srv.calls if "/changes" in p][-1]
        self.assertIn("since=0", q)

    def test_an_ack_is_for_this_api_only(self):
        self.changes()
        os.environ["TODO_API"] = os.environ["TODO_API"].replace("localhost", "127.0.0.1")
        rc, out = self.cli("changes", "--ack", "9")          # nothing shown on this instance yet
        self.assertEqual(rc, 1)
        self.assertIn("past the last event shown", out)

    def test_the_key_ignores_case_and_a_trailing_slash(self):
        self.assertEqual(self.key("HTTP://Admin.Example/api/todo/v1/"),
                         self.key("http://admin.example/api/todo/v1"))


if __name__ == "__main__":
    unittest.main()
