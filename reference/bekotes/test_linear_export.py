"""linear_export.py: key check, pagination, errors (no network)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import subprocess
import sys
import unittest

from test_leltar import HERE


class LinearExportTest(unittest.TestCase):
    def test_no_key_exit_2(self):
        env = {k: v for k, v in os.environ.items() if k != "LINEAR_API_KEY"}
        r = subprocess.run([sys.executable, str(HERE / "linear_export.py"), "--team", "ZOL",
                            "--out", "/nonexistent/x.json"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_pagination_complete(self):
        import linear_export as le
        pages = [{"nodes": [{"id": "1", "identifier": "Z-1", "title": "a",
                             "state": {"name": "Todo"}, "updatedAt": "t"}],
                  "pageInfo": {"hasNextPage": True, "endCursor": "c1"}},
                 {"nodes": [{"id": "2", "identifier": "Z-2", "title": "b",
                             "state": {"name": "Done"}, "updatedAt": "t"}],
                  "pageInfo": {"hasNextPage": False, "endCursor": None}}]
        calls = []

        def fetch(query, variables):
            calls.append(variables)
            return {"data": {"issues": pages[len(calls) - 1]}}
        d = le.export("ZOL", fetch, now="2026-01-01T00:00:00Z")
        self.assertTrue(d["complete"])
        self.assertEqual([i["state"] for i in d["issues"]], ["Todo", "Done"])
        self.assertEqual(calls[1]["after"], "c1")
        self.assertEqual(calls[0]["team"], "ZOL")

    def test_error_incomplete(self):
        import linear_export as le

        def fetch(query, variables):
            raise OSError("boom")
        d = le.export("ZOL", fetch, now="x")
        self.assertFalse(d["complete"])


class LinearRichFields(unittest.TestCase):
    def test_rich_row(self):
        import linear_export as le
        node = {"id": "1", "identifier": "Z-1", "number": 1, "title": "a", "updatedAt": "t",
                "description": "d", "priority": 2, "estimate": 3, "createdAt": "c",
                "completedAt": "x", "canceledAt": None, "state": {"name": "Done", "type": "completed"},
                "assignee": {"name": "Ann"}, "creator": None, "parent": {"id": "p"},
                "labels": {"nodes": [{"name": "web"}]},
                "attachments": {"nodes": [{"url": "https://u", "title": "T"}]},
                "comments": {"nodes": [{"id": "c1", "body": "b", "createdAt": "t", "user": {"name": "Bob"}}],
                             "pageInfo": {"hasNextPage": True}}}
        page = {"nodes": [node], "pageInfo": {"hasNextPage": False, "endCursor": None}}
        row = le.export("Z", lambda q, v: {"data": {"issues": page}}, now="t")["issues"][0]
        self.assertEqual((row["assignee"], row["parent"], row["labels"], row["state_type"]),
                         ("Ann", "p", ["web"], "completed"))
        self.assertEqual(row["comments"][0]["author"], "Bob")
        self.assertTrue(row["comments_truncated"])
        self.assertEqual(row["attachments"][0]["url"], "https://u")


class LinearFix(unittest.TestCase):
    def test_null_cursor_stops(self):
        import linear_export as le
        page = {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}
        d = le.export("Z", lambda q, v: {"data": {"issues": page}}, now="t")
        self.assertFalse(d["complete"])

    def test_graphql_error_message(self):
        import io
        import contextlib
        import linear_export as le
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            d = le.export("Z", lambda q, v: {"errors": [{"message": "nope"}]}, now="t")
        self.assertFalse(d["complete"])
        self.assertIn("nope", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
