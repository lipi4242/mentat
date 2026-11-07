"""The post-install proposal: `proposal check` validates .mentat/cases-proposal.json,
`import` turns only the approved items into cases, idempotently, with a brain_ref
back from the source note. Recognising cases is the agent's job, not the CLI's."""
import json
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import Repo
from test_admin import AdminRepo

REKA = "---\ntype: person\nname: Szabó Réka\n---\n\nPróbaidő november 30-ig.\n"
DUMP = "Bérleti díj minden hónap 15-éig. A Fénytár ajánlata október 31-ig él.\n"
ITEMS = [
    {"id": "p1", "source": "agy/people/szabo-reka.md", "title": "Réka próbaideje",
     "description": "A próbaidő november 30-án lejár.", "next_action": "Leülni Rékával",
     "kind": "one-off", "due_at": "2026-11-30", "reason": "Dátumhoz kötött döntés."},
    {"id": "p2", "source": "agy/brain-dumps/penzugyek.md", "title": "Bérleti díj",
     "description": "285 ezer az önkormányzatnak.", "next_action": "Átutalni",
     "kind": "recurring", "recurrence": "monthly:15", "anchor_at": "2026-10-15", "reason": "Havi fizetés."},
    {"id": "p3", "source": "agy/brain-dumps/penzugyek.md", "title": "Fénytár ajánlat",
     "description": "A napelem-ajánlat október 31-ig él.", "next_action": "Dönteni",
     "kind": "one-off", "due_at": "2026-10-31", "reason": "Lejáró ajánlat."},
]


class Proposal(Repo):
    def setUp(self):
        super().setUp()
        for rel, text in (("people/szabo-reka.md", REKA), ("brain-dumps/penzugyek.md", DUMP)):
            (self.root / "agy" / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / "agy" / rel).write_text(text)
        self.write(ITEMS)

    def write(self, items, **top):
        doc = {"schema": 1, "items": items, **top}
        (self.root / ".mentat" / "cases-proposal.json").write_text(json.dumps(doc, ensure_ascii=False))

    def src(self, rel):
        return (self.root / "agy" / rel).read_text()

    def titles(self):
        return sorted(r["title"] for r in self.js("list", "--status", "all"))


class TestCheck(Proposal):
    def test_a_valid_proposal_passes(self):
        self.assertIn("3 items", self.cli("proposal", "check").stdout)

    def test_each_broken_item_is_named_and_the_exit_is_1(self):
        bad = [dict(ITEMS[0], waiting_on="Réka"), {k: v for k, v in ITEMS[1].items() if k != "anchor_at"},
               dict(ITEMS[2], recurrence="monthly:31"), dict(ITEMS[0], id="p4", source="agy/nincs.md"),
               dict(ITEMS[0], id="p1", kind="soon"), dict(ITEMS[2], id="p5", own={"amount": [1]})]
        self.write(bad)
        p = self.cli("proposal", "check", ok=False)
        self.assertEqual(p.returncode, 1)
        for want in ("p1: unknown key waiting_on", "p2: anchor_at", "p3: a one-off", "p4: source",
                     "duplicate id p1", "kind must be", "p5: own must map"):
            self.assertIn(want, p.stderr)

    def test_a_missing_proposal_is_refused(self):
        (self.root / ".mentat" / "cases-proposal.json").unlink()
        self.assertIn("cases-proposal.json", self.cli("proposal", "check", ok=False).stderr)


class TestImport(Proposal):
    def test_only_the_approved_items_become_cases_with_a_brain_ref_back(self):
        before = self.titles()
        out = self.cli("import", "--from", ".mentat/cases-proposal.json", "--only", "p1,p3").stdout
        self.assertEqual(self.titles(), sorted(before + ["Réka próbaideje", "Fénytár ajánlat"]))
        reka = next(r for r in self.js("list") if r["title"] == "Réka próbaideje")
        self.assertEqual(reka["due_at"], "2026-11-30")
        self.assertIn(reka["brain_ref"], self.src("people/szabo-reka.md"))
        self.assertIn(reka["brain_ref"], out)
        shown = self.js("show", reka["id"])
        self.assertEqual(shown["description"], "A próbaidő november 30-án lejár.")
        self.assertIn("agy/people/szabo-reka.md", shown["context"])
        self.assertNotIn("Bérleti díj", self.titles())
        self.assertEqual(self.src("brain-dumps/penzugyek.md").count("agy/cases/"), 1)

    def test_import_twice_does_not_duplicate(self):
        self.cli("import", "--from", ".mentat/cases-proposal.json")
        once, src = self.titles(), self.src("brain-dumps/penzugyek.md")
        p = self.cli("import", "--from", ".mentat/cases-proposal.json")
        self.assertEqual(self.titles(), once)
        self.assertEqual(self.src("brain-dumps/penzugyek.md"), src)
        self.assertEqual(p.stdout.count("already"), 3)
        berlet = next(r for r in self.js("list") if r["title"] == "Bérleti díj")
        self.assertEqual((berlet["recurrence"], berlet["due_at"]), ("monthly:15", "2026-10-15"))

    def test_nothing_is_written_when_the_proposal_or_the_selection_is_wrong(self):
        before, files = self.titles(), sorted(p.name for p in (self.root / "agy" / "cases").iterdir())
        self.cli("import", "--from", ".mentat/cases-proposal.json", "--only", "p1,p9", ok=False)
        self.write([ITEMS[0], dict(ITEMS[1], kind="one-off")])
        self.cli("import", "--from", ".mentat/cases-proposal.json", ok=False)
        self.assertEqual(self.titles(), before)
        self.assertEqual(sorted(p.name for p in (self.root / "agy" / "cases").iterdir()), files)
        self.assertEqual(self.src("people/szabo-reka.md"), REKA)


class TestQuarterly(Proposal):
    def test_a_quarterly_item_is_checked_and_imported(self):
        afa = dict(ITEMS[1], id="q1", title="ÁFA-bevallás", recurrence="quarterly:20", anchor_at="2027-01-20")
        self.write([afa, dict(afa, id="q2", title="Rossz", anchor_at="2027-01-21")])
        p = self.cli("proposal", "check", ok=False)
        self.assertIn("q2: anchor_at", p.stderr)
        self.assertNotIn("q1:", p.stderr)
        self.write([afa])
        self.cli("import", "--from", ".mentat/cases-proposal.json")
        c = next(r for r in self.js("list") if r["title"] == "ÁFA-bevallás")
        self.assertEqual((c["recurrence"], c["due_at"]), ("quarterly:20", "2027-01-20"))

    def test_the_rule_list_names_quarterly(self):
        self.write([dict(ITEMS[1], recurrence="havonta")])
        self.assertIn("quarterly:<1-31>", self.cli("proposal", "check", ok=False).stderr)


class TestOwnFields(Proposal):
    def test_markdown_keeps_own_values_in_extra(self):
        self.write([dict(ITEMS[0], own={"priority": "magas"})])
        self.cli("import", "--from", ".mentat/cases-proposal.json")
        reka = next(r for r in self.js("list") if r["title"] == "Réka próbaideje")
        self.assertEqual(self.js("show", reka["id"])["extra"], {"priority": "magas"})


class TestAdminImport(AdminRepo, Proposal):
    def test_own_fields_go_to_the_admin_and_unknown_ones_stop_everything(self):
        self.store.own = [{"name": "priority", "type": "select", "options": ["normál", "magas"]}]
        self.write([ITEMS[2], dict(ITEMS[0], own={"szin": "kek"})])
        p = self.cli("import", "--from", ".mentat/cases-proposal.json", ok=False)
        self.assertIn("szin", p.stderr)
        self.assertEqual(self.store.cases, {})
        self.write([dict(ITEMS[0], own={"priority": "magas"})])
        self.cli("import", "--from", ".mentat/cases-proposal.json")
        (case,) = self.store.cases.values()
        self.assertEqual((case["priority"], case["description"]), ("magas", ITEMS[0]["description"]))
        self.assertIn(case["brain_ref"], self.src("people/szabo-reka.md"))


if __name__ == "__main__":
    unittest.main()
