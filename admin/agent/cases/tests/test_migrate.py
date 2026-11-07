"""cases migrate / export — a backend switch is all or nothing."""
import json
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import GAZ_ID, Repo
from test_admin import IDS

NO_ID = "---\ntype: case\ntitle: Biztosítás\nstatus: open\ndue_at: 2026-11-30\n---\n\nKGFB.\n"


class Migrating(Repo):
    with_admin = True
    files = {**Repo.files, "biztositas.md": NO_ID}

    def backend_now(self):
        return self.manifest()["cases"]["backend"]


class TestToAdmin(Migrating):
    def test_moves_every_case_and_strips_the_tracked_fields(self):
        want = self.cli("--json", "list", "--status", "all").stdout
        self.cli("migrate", "--to", "admin")
        self.assertEqual(self.backend_now(), "admin")
        self.assertEqual(len(self.store.cases), 5)
        gaz = self.store.cases[GAZ_ID]
        self.assertEqual((gaz["due_at"], gaz["brain_ref"]), ("2026-10-10", "agy/cases/gazszamla.md"))
        self.assertEqual([o["due_at"] for o in self.store.occ[GAZ_ID]], ["2026-09-10"])
        text = self.text("gazszamla.md")
        for gone in ("title:", "status:", "recurrence:", "occurrences:"):
            self.assertNotIn(gone, text)
        self.assertIn("migration: done", text)
        self.assertIn("tags: [háztartás, pénzügy]", text)
        self.assertIn("12 400 Ft", text)
        self.assertRegex(self.text("biztositas.md"), r"case_id: [0-7][0-9A-HJKMNP-TV-Z]{25}")
        # The base model dropped waiting_on and category: the value moves into extra, the key leaves the file.
        self.assertEqual(self.store.cases[IDS["karigeny.md"]]["extra"], {"waiting_on": "a biztosító"})
        self.assertEqual(gaz["extra"], {"category": "háztartás"})
        self.assertNotIn("waiting_on:", self.text("karigeny.md"))
        self.assertNotIn("category:", text)
        self.assertEqual(self.cli("--json", "list", "--status", "all").stdout,
                         want.replace('"agy/cases/biztositas.md"', '"%s"' % self._id("biztositas.md"), 1))

    def _id(self, name):
        return next(c for c, r in self.store.cases.items() if r["brain_ref"] == "agy/cases/" + name)

    def test_dry_run_writes_nothing(self):
        before = {n: self.text(n) for n in self.files}
        p = self.cli("migrate", "--to", "admin", "--dry-run")
        self.assertIn("Gázszámla", p.stdout)
        self.assertEqual({n: self.text(n) for n in self.files}, before)
        self.assertEqual((self.store.cases, self.backend_now()), ({}, "markdown"))

    def test_interrupted_stays_markdown_and_a_rerun_does_not_duplicate(self):
        self.store.faults.append(("PUT", "/api/cases/" + IDS["karigeny.md"], "500"))
        p = self.cli("migrate", "--to", "admin", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.backend_now(), "markdown")
        self.assertIn("title: Gázszámla", self.text("gazszamla.md"))
        self.assertEqual(self.js("show", GAZ_ID)["due_at"], "2026-10-10")
        self.cli("migrate", "--to", "admin")
        self.assertEqual((len(self.store.cases), self.backend_now()), (5, "admin"))

    def test_lost_response_then_rerun_does_not_duplicate(self):
        self.store.faults.append(("PUT", "/api/cases/", "lost"))
        self.cli("migrate", "--to", "admin", ok=False)
        self.assertEqual(self.backend_now(), "markdown")
        self.cli("migrate", "--to", "admin")
        self.assertEqual(len(self.store.cases), 5)


class TestToMarkdown(Migrating):
    def setUp(self):
        super().setUp()
        self.cli("migrate", "--to", "admin")
        self.store.close(GAZ_ID, {"due_at": "2026-10-10", "note": "az adminban zárva"})

    def test_back_to_markdown_with_the_admins_history(self):
        want = self.cli("--json", "list", "--status", "all").stdout
        self.cli("migrate", "--to", "markdown")
        self.assertEqual(self.backend_now(), "markdown")
        self.assertEqual(self.cli("--json", "list", "--status", "all").stdout, want)
        text = self.text("gazszamla.md")
        self.assertIn("az adminban zárva", text)
        self.assertIn("due_at: 2026-11-10", text)
        self.assertNotIn("migration:", text)

    def test_failure_restores_every_file(self):
        before = {n: self.text(n) for n in self.files}
        self.store.faults.append(("GET", "/api/cases/" + IDS["lakber.md"], "500"))
        self.cli("migrate", "--to", "markdown", ok=False)
        self.assertEqual(self.backend_now(), "admin")
        self.assertEqual({n: self.text(n) for n in self.files}, before)

    def test_export_writes_elsewhere_and_leaves_the_brain(self):
        before = {n: self.text(n) for n in self.files}
        out = self.root / "export"
        self.cli("export", "--out", str(out))
        self.assertEqual(len(list(out.glob("*.md"))), 5)
        self.assertIn("recurrence: monthly:10", (out / "gazszamla.md").read_text())
        self.assertEqual({n: self.text(n) for n in self.files}, before)
        self.assertEqual(json.loads((self.root / "mentat.json").read_text())["cases"]["backend"], "admin")


if __name__ == "__main__":
    unittest.main()
