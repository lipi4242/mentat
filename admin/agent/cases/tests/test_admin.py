"""cases.backend: admin — the admin API is the record; the same commands give
the same output as in markdown mode, and a missing admin is an error."""
import socket
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import GAZ_ID, Repo

IDS = {"gazszamla.md": GAZ_ID, "ado.md": "01JAB6Z9Q3M8K7T2V5W4X1Y0RT",
       "karigeny.md": "01JAB6Z9Q3M8K7T2V5W4X1Y0RV", "lakber.md": "01JAB6Z9Q3M8K7T2V5W4X1Y0RW"}
SEED = {
    "gazszamla.md": {"title": "Gázszámla", "next_action": "Átutalni, amint megjön a számla",
                     "recurrence": "monthly:10", "anchor_at": "2026-09-10", "extra": {"category": "háztartás"},
                     "occurrences": [{"due_at": "2026-09-10", "status": "done", "done_at": "2026-09-08",
                                      "note": "átutalva"}]},
    "ado.md": {"title": "Adóbevallás", "next_action": "Beküldeni", "due_at": "2027-05-20"},
    "karigeny.md": {"title": "Kárigény", "status": "waiting", "extra": {"waiting_on": "a biztosító"},
                    "next_action": "Rákérdezni", "due_at": "2026-10-20"},
    "lakber.md": {"title": "Lakbér", "recurrence": "monthly:31", "anchor_at": "2026-08-31"},
}


def body_of(text):
    return text.split("\n---\n", 1)[1]


class AdminRepo(Repo):
    backend = "admin"
    with_admin = True

    def seed(self):
        """The state after a migration: cases in the admin, files keep case_id + context."""
        for name, fields in SEED.items():
            self.store.put(IDS[name], {**fields, "brain_ref": "agy/cases/" + name})
            body = body_of(self.files[name])
            (self.root / "agy" / "cases" / name).write_text(
                "---\ntype: case\ncase_id: %s\nmigration: done\n---\n%s" % (IDS[name], body))


class TestParity(AdminRepo):
    def test_same_output_as_markdown(self):
        md = Repo(methodName="setUp")
        md.setUp()
        try:
            want = {c: md.cli(*c).stdout for c in (("list",), ("due", "--days", "30"), ("show", GAZ_ID),
                                                   ("--json", "list"), ("--json", "due"), ("--json", "show", GAZ_ID))}
        finally:
            md.tearDown()
        self.seed()
        for c, out in want.items():
            self.assertEqual(self.cli(*c).stdout, out, c)

    def test_close_goes_through_the_api(self):
        self.seed()
        self.cli("close", GAZ_ID)
        self.assertEqual(self.store.cases[GAZ_ID]["due_at"], "2026-11-10")
        p = self.cli("close", IDS["lakber.md"], "--occurrence", "2026-09-30", ok=False)
        self.assertIn("2026-08-31", p.stderr)

    def test_create_writes_the_admin_and_a_brain_file(self):
        new = self.js("create", "--title", "Gázszámla 2", "--recurrence", "monthly:10", "--anchor", "2026-10-10")
        row = self.store.cases[new["id"]]
        self.assertEqual((row["due_at"], row["brain_ref"]), ("2026-10-10", new["brain_ref"]))
        text = (self.root / new["brain_ref"]).read_text()
        self.assertIn("case_id: " + new["id"], text)
        self.assertNotIn("recurrence:", text)


class TestUnavailable(Repo):
    backend = "admin"

    def test_not_connected_is_an_error_not_markdown(self):
        before = self.text("gazszamla.md")
        p = self.cli("close", GAZ_ID, ok=False)
        self.assertEqual(p.returncode, 3)
        self.assertIn("not connected", p.stderr)
        self.assertEqual(self.text("gazszamla.md"), before)

    def test_unreachable_is_an_error(self):
        with socket.socket() as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
        (self.root / ".mentat" / "local.json").write_text(
            '{"schema": 1, "admin": {"url": "http://localhost:%d", "token_env": "CASES_T"}}' % port)
        (self.root / ".env").write_text("CASES_T=x\n")
        p = self.cli("list", ok=False)
        self.assertEqual(p.returncode, 3)
        self.assertIn("unavailable", p.stderr)


class TestUnknownSchema(Repo):
    def test_newer_schema_is_diagnostics_only(self):
        (self.root / "mentat.json").write_text('{"schema": 2, "cases": {"backend": "markdown"}}')
        before = self.text("gazszamla.md")
        p = self.cli("close", GAZ_ID, ok=False)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(self.text("gazszamla.md"), before)


if __name__ == "__main__":
    unittest.main()
