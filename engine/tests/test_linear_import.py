#!/usr/bin/env python3
"""Linear import: mapping, dry-run, and an idempotent rerun against a fake server.

Fixture data is invented. Compatible with pytest and direct execution.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import _todo_fixture  # noqa: E402,F401  (first: skips when the pack is not vendored)
from anytime_todo import linear_import as li  # noqa: E402
from anytime_todo import linear_parse as lp  # noqa: E402

START = "2026-11-06T00:00:00Z"
DESC = "Why: demo.\n\nKész, ha:\n- the page loads\n- [ ] the form saves\n* errors are shown\n\nNotes below"


def issue(n, state, **kw):
    row = {"id": f"u{n}", "identifier": f"DEMO-{n}", "title": f"item {n}", "state": state,
           "description": "", "priority": 2, "estimate": 3, "createdAt": "2026-01-01T00:00:00Z",
           "completedAt": None, "canceledAt": None, "assignee": "Ann Example", "parent": None,
           "labels": ["web"], "attachments": [], "comments": []}
    row.update(kw)
    return row


EXPORT = {"complete": True, "issues": [
    issue(1, "In Review", description=DESC,
          comments=[{"id": "c1", "body": "hi", "createdAt": "2026-02-01T00:00:00Z", "author": "Bob"}],
          attachments=[{"url": "https://github.com/acme/app/pull/7", "title": "PR"},
                       {"url": "https://example.com/x", "title": "doc"}]),
    issue(2, "Todo", assignee=None, parent="u1"),
    issue(3, "Done", completedAt="2026-01-10T00:00:00Z"),          # older than 90 days
    issue(4, "Canceled", canceledAt="2026-10-20T00:00:00Z"),       # recent
    issue(5, "In Progress", assignee="Nobody Mapped")]}
USERS = {"Ann Example": "ann"}


class FakeServer:
    """The assumed contract: keyed by ext_ref / source ids, fill-only on a rerun."""
    def __init__(self):
        self.projects, self.items, self.acs, self.comments, self.links = {}, {}, set(), set(), set()
        self.calls = []

    def _call(self, method, path, body=None):
        self.calls.append((method, path))
        if (method, path) == ("GET", "/projects"):
            return [{"prefix": p} for p in self.projects]
        if path == "/projects":
            self.projects[body["prefix"]] = body
            return {}
        if path == "/items/import":
            new = body["ext_ref"] not in self.items
            self.items.setdefault(body["ext_ref"], dict(body, parent=None))
            self.acs |= {a["source_id"] for a in body["acs"]}
            self.comments |= {c["source_id"] for c in body["comments"]}
            self.links |= {(body["ext_ref"], l["url"]) for l in body["links"]}
            return {"created": new}
        if path == "/items/import/parent":
            it = self.items[body["ext_ref"]]
            it["parent"] = it["parent"] or body["parent_ext_ref"]
            return {}
        raise AssertionError(path)


def write(d, name, obj):
    p = Path(d) / name
    p.write_text(json.dumps(obj))
    return str(p)


class MappingTest(unittest.TestCase):
    def pay(self, n):
        return lp.item_payload(next(r for r in EXPORT["issues"] if r["id"] == f"u{n}"), USERS, START)

    def test_in_review_is_taken_with_dev(self):
        p = self.pay(1)
        self.assertEqual((p["stage"], p["dev"]), ("taken", "ann"))

    def test_taken_without_mapped_dev_is_draft(self):
        self.assertEqual(self.pay(5)["stage"], "draft")
        self.assertIsNone(self.pay(5)["dev"])

    def test_key_and_acs(self):
        p = self.pay(1)
        self.assertEqual((p["project"], p["number"], p["ext_ref"]), ("DEMO", 1, "linear:u1"))
        self.assertEqual([a["text"] for a in p["acs"]],
                         ["the page loads", "the form saves", "errors are shown"])
        self.assertEqual(p["acs"][1]["source_id"], "linear:u1:ac:2")
        self.assertIn("Kész, ha", p["description"])

    def test_pr_links_only_and_comment_provenance(self):
        p = self.pay(1)
        self.assertEqual([l["url"] for l in p["links"]], ["https://github.com/acme/app/pull/7"])
        c = p["comments"][0]
        self.assertEqual((c["source_system"], c["source_id"], c["source_author"]), ("linear", "c1", "Bob"))

    def test_archive_rule(self):
        self.assertTrue(self.pay(3)["archived"])
        self.assertFalse(self.pay(4)["archived"])
        self.assertFalse(lp.is_archived("done", {}, START))          # no timestamp: not archived

    def test_unknown_state_refused(self):
        with self.assertRaises(lp.ImportError_):
            lp.map_stage("Weird", True)


class ImportRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exp = write(self.tmp.name, "e.json", EXPORT)
        self.map = write(self.tmp.name, "m.json", {"users": USERS})

    def go(self, srv, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = li.main([self.exp, "--map", self.map, "--started-at", START, *extra], client=srv)
        return rc, out.getvalue(), err.getvalue()

    def test_dry_run_calls_nothing_and_writes_nothing(self):
        srv = FakeServer()
        rc, out, _ = self.go(srv, "--dry-run")
        self.assertEqual((rc, srv.calls), (0, []))
        self.assertIn("5 items", out)
        self.assertFalse(Path(self.exp + ".import.json").exists())

    def test_rerun_duplicates_nothing(self):
        srv = FakeServer()
        self.assertEqual(self.go(srv)[0], 0)
        snap = (len(srv.items), len(srv.acs), len(srv.comments), len(srv.links), len(srv.projects))
        self.assertEqual(snap, (5, 3, 1, 1, 1))
        rc, out, _ = self.go(srv)
        self.assertEqual(rc, 0)
        self.assertEqual(snap, (len(srv.items), len(srv.acs), len(srv.comments),
                                len(srv.links), len(srv.projects)))
        self.assertIn('"created": 0', out)
        self.assertEqual(srv.items["linear:u2"]["parent"], "linear:u1")

    def test_import_started_at_recorded_once(self):
        self.go(FakeServer())
        first = json.loads(Path(self.exp + ".import.json").read_text())["import_started_at"]
        self.assertEqual(li.started_at(Path(self.exp + ".import.json"), "2099-01-01T00:00:00Z"), first)

    def test_server_errors_are_explained(self):
        from anytime_todo.api import TodoApiError
        for status, text in ((409, "already taken"), (403, "todo:import"), (404, "not imported")):
            class Boom(FakeServer):
                def _call(self, m, path, body=None, _s=status):
                    if path == "/items/import":
                        raise TodoApiError("x", _s)
                    return super()._call(m, path, body)
            rc, _, err = self.go(Boom())
            self.assertEqual(rc, 1)
            self.assertIn(text, err)

    def test_incomplete_export_refused(self):
        self.exp = write(self.tmp.name, "e2.json", dict(EXPORT, complete=False))
        rc, _, err = self.go(FakeServer())
        self.assertEqual(rc, 1)
        self.assertIn("incomplete", err)


class WorkerFixtureTest(unittest.TestCase):
    """admin/worker/__tests__/fixtures/linear-import-plan.json (posted to the REAL worker route
    by backlog-linear-import.test.ts) must equal what this importer produces. Regenerate with
    `python3 tests/test_linear_import.py --regen`."""
    PATH = Path(__file__).resolve().parents[3] / "admin/worker/__tests__/fixtures/linear-import-plan.json"

    @staticmethod
    def current():
        items = li.plan(EXPORT, {"Ann Example": "b"}, START)
        return [{k: v for k, v in i.items() if not k.startswith("_")} | {"parent": i["_parent"]}
                for i in items]

    def test_fixture_is_current(self):
        if not self.PATH.exists():
            self.skipTest("worker fixture not in this tree")
        self.assertEqual(json.loads(self.PATH.read_text()), json.loads(json.dumps(self.current())))


if __name__ == "__main__":
    if "--regen" in sys.argv:
        WorkerFixtureTest.PATH.parent.mkdir(exist_ok=True)
        WorkerFixtureTest.PATH.write_text(json.dumps(WorkerFixtureTest.current(), indent=1, sort_keys=True) + "\n")
    else:
        unittest.main()
