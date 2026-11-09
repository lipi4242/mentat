#!/usr/bin/env python3
"""A terepről (ágens-interjúk, 11-07/08) jött CLI-hiányok: mindegyik a pontos kérést
nézi, amit a parancs küld. A teljes úton a tools/test/functional fedi ugyanezeket.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import json
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
from test_todo_item_cli import ItemCase  # noqa: E402


class Terep(ItemCase):
    def setUp(self):
        super().setUp()
        self.srv.tasks["T1"] = task("T1", "2026-11-06", rev=2, repeat=None)

    def gets(self) -> list[str]:
        return [p for m, p in self.srv.calls if m == "GET"]

    def submit_with(self, sha: str = "0123abc", pr: str = "https://github.com/o/r/pull/7"):
        p = self.filled()
        p.write_text(p.read_text().replace("0123abc", sha).replace("https://github.com/o/r/pull/7", pr))
        return self.submit(p)


class TestTaskVerbs(Terep):
    def test_comment_takes_an_item_key(self):
        self.srv.tasks["I1"] = self.srv.items["I1"]       # a valódi /tasks/<id> a tételt is ismeri
        rc, out = self.cli("task", "comment", "WEB-7", "--text", "kulccsal")
        self.assertEqual(rc, 0, out)
        (_, path, body), = self.sent()
        self.assertEqual((path, body["body"]), ("/tasks/I1/comments", "kulccsal"))

    def test_new_parent_by_key_is_sent_as_the_id(self):
        self.assertEqual(self.cli("task", "new", "--title", "alatta", "--parent", "WEB-7")[0], 0)
        self.assertEqual(self.sent()[0][2]["parent_id"], "I1")

    def test_repeat_and_repeat_from(self):
        self.cli("task", "new", "--title", "napi", "--due", "2026-11-08", "--repeat", "every:2:weeks",
                 "--repeat-from", "completion")
        b = self.sent()[0][2]
        self.assertEqual((b["repeat_rule"], b["repeat_from"]), ("every:2:weeks", "completion"))

    def test_repeat_none_clears_the_rule(self):
        self.assertEqual(self.cli("task", "update", "T1", "--repeat", "none")[0], 0)
        self.assertEqual(self.sent()[0][2]["set"], {"repeat_rule": None})

    def test_show_reads_a_task_or_an_item(self):
        self.assertEqual(json.loads(self.cli("task", "show", "T1")[1])["id"], "T1")
        self.assertEqual(json.loads(self.cli("task", "show", "WEB-7")[1])["id"], "I1")
        self.assertEqual(self.sent(), [])

    def test_list_passes_the_filters(self):
        self.assertEqual(self.cli("task", "list", "--ball", "anna", "--status", "open", "--due-before",
                                  "2026-12-01")[0], 0)
        q = self.gets()[-1]
        for part in ("/tasks?", "ball=anna", "status=open", "due_before=2026-12-01"):
            self.assertIn(part, q)

    def test_project_list(self):
        self.assertEqual(self.cli("project", "list")[0], 0)
        self.assertTrue(self.gets()[-1].endswith("/projects"))


class TestItemVerbs(Terep):
    def test_resume_takes_an_optional_note(self):
        self.srv.items["I1"]["stage"] = "hold"
        self.assertEqual(self.cli("item", "resume", "WEB-7", "--note", "megjött a döntés")[0], 0)
        self.assertEqual(self.sent("resume")[0][2]["note"], "megjött a döntés")
        self.srv.items["I1"]["stage"] = "hold"
        self.cli("item", "resume", "WEB-7")
        self.assertNotIn("note", self.sent("resume")[1][2])

    def test_a_non_url_pr_is_refused_before_sending(self):
        for pr in ("#53", "53", "o/r#53"):
            rc, out = self.submit_with(pr=pr)
            self.assertEqual(rc, 1, out)
            self.assertIn("pr must be a full http(s) URL", out)
        self.assertEqual(self.sent("submit"), [])

    def test_the_template_says_what_meta_needs_and_an_uppercase_sha_is_lowered(self):
        self.assertIn("pr: a full http(s) URL", self.form())
        rc, out = self.submit_with(sha="0123ABC")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.sent("submit")[0][2]["head_sha"], "0123abc")

    def test_a_short_sha_names_the_value(self):
        rc, out = self.submit_with(sha="abc12")
        self.assertEqual(rc, 1)
        self.assertIn("'abc12'", out)


class TestBall(Terep):
    def test_ball_leaves_out_my_drafts_unless_asked(self):
        self.srv.items["D1"] = {**self.srv.items["I1"], "id": "D1", "key": "WEB-8", "stage": "draft"}
        self.srv.tasks["D1"] = self.srv.items["D1"]
        ids = {r["id"] for r in json.loads(self.cli("ball")[1])}
        self.assertNotIn("D1", ids)
        self.assertIn("T1", ids)
        self.assertIn("D1", {r["id"] for r in json.loads(self.cli("ball", "--drafts")[1])})
        self.assertTrue(any("stage=draft" in p and "ball=rocky" in p for p in self.gets()))


class TestHelp(Terep):
    def test_top_level_help_points_to_task_done_and_item_lists_its_verbs(self):
        _, top = self.cli("--help")
        self.assertIn("task done", top)
        _, it = self.cli("item", "--help")
        for verb in ("issue", "take", "submit", "accept", "reject", "resume", "drop"):
            self.assertRegex(it, rf"\n\s+{verb}\s+\S")


if __name__ == "__main__":
    unittest.main()
