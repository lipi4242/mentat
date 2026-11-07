"""The admin's own case fields (config/models.json fields.cases, GET /api/meta):
the agent lists them, writes them with --set, reads them back — and the base
model's one-off case works end to end on the admin backend."""
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import Repo
from test_admin import IDS, AdminRepo

PRIORITY = {"name": "priority", "label": "Prioritás", "type": "select", "options": ["alacsony", "normál", "magas"]}
ADO = IDS["ado.md"]


class TestOwnFields(AdminRepo):
    def setUp(self):
        super().setUp()
        self.seed()
        self.store.own = [PRIORITY]

    def test_fields_lists_them(self):
        out = self.cli("fields").stdout
        self.assertIn("priority", out)
        self.assertIn("alacsony|normál|magas", out)

    def test_set_writes_and_show_reads_it(self):
        self.cli("update", ADO, "--set", "priority=magas")
        self.assertEqual(self.store.cases[ADO]["priority"], "magas")
        self.assertEqual(self.js("show", ADO)["priority"], "magas")
        self.assertIn("priority: magas", self.cli("show", ADO).stdout)
        self.assertEqual([r["priority"] for r in self.js("list") if r["id"] == ADO], ["magas"])
        new = self.js("create", "--title", "Autó", "--due", "2026-12-01", "--set", "priority=alacsony")
        self.assertEqual(self.store.cases[new["id"]]["priority"], "alacsony")

    def test_bad_value_and_unknown_field_are_refused(self):
        p = self.cli("update", ADO, "--set", "priority=sürgős", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("priority", p.stderr)
        p = self.cli("update", ADO, "--set", "szin=kek", ok=False)
        self.assertIn("not an own case field", p.stderr)

    def test_one_off_case_on_the_admin(self):
        new = self.js("create", "--title", "Útlevél", "--description", "Lejár decemberben", "--due", "2026-11-20")
        self.assertEqual((new["due_at"], new["recurrence"], new["description"]), ("2026-11-20", None, "Lejár decemberben"))
        self.assertIn("Útlevél", self.cli("due", "--until", "2026-11-30").stdout)
        self.cli("close", new["id"])
        self.assertEqual(self.store.cases[new["id"]]["status"], "done")
        self.assertNotIn("Útlevél", self.cli("due", "--until", "2026-11-30").stdout)


class TestMarkdownRefusesSet(Repo):
    def test_set_needs_the_admin(self):
        p = self.cli("update", IDS["ado.md"], "--set", "priority=magas", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("cases.backend is markdown", p.stderr)


if __name__ == "__main__":
    unittest.main()
