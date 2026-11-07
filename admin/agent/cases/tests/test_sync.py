"""cases sync (admin mode): context up, the human's changes down as events,
and a frontmatter that disagrees with the admin is reported, never written."""
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import GAZ_ID
from test_admin import AdminRepo


class TestSync(AdminRepo):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_context_goes_up_once(self):
        p = self.cli("sync")
        self.assertIn("context: 4 uploaded", p.stdout)
        self.assertIn("12 400 Ft", self.store.cases[GAZ_ID]["context"])
        self.assertIn("context: 0 uploaded", self.cli("sync").stdout)

    def test_the_humans_changes_come_down_once(self):
        self.cli("sync")
        self.store.event(GAZ_ID, "case.updated", {"fields": ["next_action"]}, actor="user")
        p = self.cli("sync")
        self.assertIn("user case.updated Gázszámla", p.stdout)
        self.assertIn("next_action", p.stdout)
        self.assertNotIn("user case.updated", self.cli("sync").stdout)

    def test_conflicting_frontmatter_is_reported_not_overwritten(self):
        path = self.root / "agy" / "cases" / "gazszamla.md"
        path.write_text(path.read_text().replace("migration: done\n", "migration: done\nstatus: done\n"))
        before = path.read_text()
        version = self.store.cases[GAZ_ID]["version"]
        p = self.cli("sync", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("conflict", p.stdout)
        self.assertIn("status", p.stdout)
        self.assertEqual(path.read_text(), before)
        self.assertEqual(self.store.cases[GAZ_ID]["status"], "open")
        self.assertLessEqual(self.store.cases[GAZ_ID]["version"], version + 1)   # only the context upload

    def test_a_case_file_missing_from_the_admin_is_reported(self):
        (self.root / "agy" / "cases" / "uj.md").write_text(
            "---\ntype: case\ncase_id: 01JAB6Z9Q3M8K7T2V5W4X1Y0RX\n---\n")
        p = self.cli("sync", ok=False)
        self.assertIn("not in the admin", p.stdout)


if __name__ == "__main__":
    unittest.main()
