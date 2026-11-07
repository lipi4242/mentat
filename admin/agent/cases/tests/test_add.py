"""`cases add`: one new case into the configured backend — no migration, no
architecture question. The due date doubles as a recurring case's anchor."""
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import Repo


class TestAddMarkdown(Repo):
    def test_one_recurring_case_due_is_the_anchor(self):
        out = self.cli("add", "--title", "Vízdíj", "--due", "2026-11-12", "--recurrence", "monthly:12").stdout
        self.assertIn("Vízdíj", out)
        self.assertIn("2026-11-12", out)
        self.assertIn("written to: markdown", out)
        text = self.text("vizdij.md")
        self.assertIn("anchor_at: 2026-11-12", text)
        self.assertIn("recurrence: monthly:12", text)
        # the other cases are untouched: still four, still markdown
        self.assertEqual(len(self.js("list", "--status", "all")), 5)
        self.assertEqual(self.manifest()["cases"]["backend"], "markdown")

    def test_a_case_needs_a_date(self):
        p = self.cli("add", "--title", "Valami", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("--due", p.stderr)


class TestAddAdmin(Repo):
    backend = "admin"
    with_admin = True
    files = {}

    def test_goes_to_the_admin(self):
        out = self.cli("add", "--title", "Gázszámla", "--due", "2026-11-10", "--recurrence", "monthly:10",
                       "--next", "Átutalni").stdout
        self.assertIn("written to: admin", out)
        rows = list(self.store.cases.values())
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["title"], rows[0]["anchor_at"], rows[0]["recurrence"]),
                         ("Gázszámla", "2026-11-10", "monthly:10"))


class TestAddMarkdownWithAdminBound(Repo):
    with_admin = True

    def test_says_how_to_move_cases_to_the_admin(self):
        out = self.cli("add", "--title", "Bérleti díj", "--due", "2026-11-05").stdout
        self.assertIn("written to: markdown", out)
        self.assertIn("migrate --to admin", out)


if __name__ == "__main__":
    unittest.main()
