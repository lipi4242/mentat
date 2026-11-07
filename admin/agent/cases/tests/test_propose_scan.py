"""`propose-scan`: the brain condensed to what carries a date or a rhythm, so the
agent does not `cat` every note after install (mérés 12). It must still show
every note that hides a deadline — the proposal's recall depends on it."""
import json
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import Repo

NOTES = {
    "people/szabo-reka.md": "---\ntype: person\nname: Szabó Réka\n---\n\nPróbaidő november 30-ig. Kedves, szereti a kávét.\n",
    "people/horvath-zsolt.md": "---\ntype: person\nname: Horváth Zsolt\n---\n## Ki ő\nÜzletkötő.\n\n- A heti lisztrendelést **minden hétfőn délig**\n  le kell adni neki.\n",
    "todos/kesz.md": "---\ntype: todo\nstatus: done\ndue: 2026-09-30\n---\n# Őszi kirakat\n\n- [x] Kész, szeptember 28-án feldíszítettük.\n",
    "ideas/ötlet.md": "# Webshop\n\nGondolkodom rajta, nincs rá idő.\n",
    "brain-dumps/penz.md": "Pénzügyek.\n\nA bérleti díj minden hónap 15-éig esedékes. " + "Hosszú mondat. " * 30 + "\n",
}


class Scan(Repo):
    def setUp(self):
        super().setUp()
        for rel, text in NOTES.items():
            f = self.root / "agy" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)

    def scan(self, *a):
        return self.cli("propose-scan", *a).stdout


class TestScan(Scan):
    def test_every_note_with_a_deadline_or_rhythm_shows_its_dated_sentence(self):
        out = self.scan()
        self.assertIn("agy/people/szabo-reka.md | Szabó Réka", out)
        self.assertIn("Próbaidő november 30-ig.", out)
        self.assertIn("minden hétfőn délig", out)
        self.assertIn("minden hónap 15-éig", out)

    def test_frontmatter_dates_show_and_done_checkboxes_are_not_evidence(self):
        out = self.scan()
        self.assertIn("agy/todos/kesz.md | Őszi kirakat | status=done, due=2026-09-30", out)
        self.assertNotIn("feldíszítettük", out)

    def test_a_note_without_signal_is_still_listed_by_title_and_the_cases_folder_is_skipped(self):
        out = self.scan()
        self.assertIn("agy/ideas/ötlet.md | Webshop", out)
        self.assertNotIn("Gondolkodom rajta", out)
        self.assertNotIn("Gázszámla", out)
        self.assertIn("without a date or rhythm signal", out)

    def test_it_is_much_shorter_than_the_notes_and_keeps_the_date_of_a_long_sentence(self):
        out = self.scan()
        self.assertLess(len(out), sum(len(t) for t in NOTES.values()))
        self.assertIn("15-éig", [l for l in out.splitlines() if "bérleti" in l][0])

    def test_lines_limits_the_sentences_and_json_is_structured(self):
        rows = json.loads(self.cli("--json", "propose-scan", "--lines", "1").stdout)
        reka = next(r for r in rows if r["note"].endswith("szabo-reka.md"))
        self.assertEqual(reka["lines"], ["Próbaidő november 30-ig."])
        self.assertEqual(reka["title"], "Szabó Réka")

    def test_nothing_is_written(self):
        before = sorted(p.name for p in (self.root / "agy" / "cases").iterdir())
        self.scan("--full")
        self.assertEqual(before, sorted(p.name for p in (self.root / "agy" / "cases").iterdir()))
        self.assertFalse((self.root / ".mentat" / "cases-proposal.json").exists())


if __name__ == "__main__":
    unittest.main()
