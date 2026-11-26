"""Types evolve: rename, merge, split, collect, field rename, suggest - notes and links stay intact,
every change leaves a decision note, and --dry-run touches nothing."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"


class Life(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                        "--repo", str(self.root), "--base", "https://x/"], capture_output=True)
        self.ok("type", "add", "bor", "--name", "Bor", "--dir", "borok", "--field", "nev:text:required",
                "--field", "szin:enum=voros|feher")
        self.ok("type", "add", "pezsgo", "--name", "Pezsgő", "--dir", "pezsgok", "--field", "nev:text",
                "--field", "erjesztes:text")
        self.ok("new", "bor", "Furmint", "--set", "szin=feher")
        self.ok("new", "bor", "Kadarka", "--set", "szin=voros", "--body", "Lásd: [Furmint](furmint.md)")
        self.ok("new", "pezsgo", "Brut", "--body", "Alapbor: [Furmint](../borok/furmint.md)")
        self.ok("new", "todo", "Rendelés", "--body", "[Kadarka](../borok/kadarka.md) kell")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True)

    def ok(self, *args):
        r = self.run_tool(*args)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r.stdout

    def read(self, rel):
        return (self.root / "agy" / rel).read_text(encoding="utf-8")

    def decisions(self):
        return [p.read_text(encoding="utf-8") for p in (self.root / "agy/decisions").glob("*.md") if p.name != "_meta.md"]

    def test_dry_run_changes_nothing(self):
        before = sorted(p.as_posix() for p in (self.root / "agy").rglob("*"))
        out = self.ok("type", "rename", "bor", "vin", "--dir", "vinok", "--dry-run")
        self.assertIn("mv agy/borok/furmint.md -> agy/vinok/furmint.md", out)
        self.assertEqual(sorted(p.as_posix() for p in (self.root / "agy").rglob("*")), before)
        self.assertEqual(self.decisions(), [])

    def test_rename_moves_the_folder_and_keeps_every_link(self):
        self.ok("type", "rename", "bor", "vin", "--dir", "vinok", "--why", "a tulaj így hívja")
        self.assertIn("type: vin\n", self.read("vinok/furmint.md"))
        self.assertIn("[Furmint](furmint.md)", self.read("vinok/kadarka.md"))
        self.assertIn("../vinok/furmint.md", self.read("pezsgok/brut.md"))
        self.assertIn("../vinok/kadarka.md", self.read("todos/rendeles.md"))
        self.assertIn("(furmint.md) - vin", self.read("vinok/_meta.md"))
        self.assertFalse((self.root / "agy/borok").exists())
        self.assertTrue((self.root / "agy/types/vin.md").exists())
        self.assertFalse((self.root / "agy/types/bor.md").exists())
        self.assertTrue(any("bor" in d and "vin" in d and "a tulaj így hívja" in d for d in self.decisions()))

    def test_merge_unions_fields_and_moves_notes(self):
        self.ok("type", "merge", "bor", "pezsgo", "--into", "bor")
        show = self.ok("type", "show", "bor")
        self.assertIn("erjesztes: text", show)
        self.assertIn("type: bor\n", self.read("borok/brut.md"))
        self.assertIn("Alapbor: [Furmint](../borok/furmint.md)", self.read("borok/brut.md"))
        self.assertIn("(brut.md) - bor", self.read("borok/_meta.md"))
        self.assertFalse((self.root / "agy/types/pezsgo.md").exists())
        self.assertFalse((self.root / "agy/pezsgok").exists())
        self.assertEqual(len(self.decisions()), 1)

    def test_split_by_field_value(self):
        self.ok("type", "split", "bor", "--rule", "voros=szin:voros", "--dir", "voros=vorosborok")
        self.assertIn("type: voros\n", self.read("vorosborok/kadarka.md"))
        self.assertIn("[Furmint](../borok/furmint.md)", self.read("vorosborok/kadarka.md"))
        self.assertIn("../vorosborok/kadarka.md", self.read("todos/rendeles.md"))
        self.assertIn("type: bor\n", self.read("borok/furmint.md"))
        self.assertIn("szin: enum", self.ok("type", "show", "voros"))

    def test_collect_scattered_notes_and_rename_a_field(self):
        p = self.root / "agy/explorations/tokaji.md"
        p.write_text("---\ntype: exploration\nnev: Tokaji\n---\n\nRégi jegyzet.\n", encoding="utf-8")
        self.ok("type", "collect", "bor", "agy/explorations/tokaji.md")
        self.assertIn("Régi jegyzet.", self.read("borok/tokaji.md"))
        self.assertIn("type: bor\n", self.read("borok/tokaji.md"))
        self.ok("type", "edit", "bor", "--rename-field", "szin=szine")
        self.assertIn("szine: feher", self.read("borok/furmint.md"))
        self.assertIn("szine: enum", self.ok("type", "show", "bor"))

    def test_suggest_finds_recurring_untyped_things(self):
        for i, t in enumerate(("Sajt: Trappista", "Sajt: Pálpusztai", "Sajt: Camembert")):
            (self.root / ("agy/explorations/s%d.md" % i)).write_text(
                "---\ntype: exploration\nerleles: 3 het\ntags: [sajt]\n---\n\n# %s\n" % t, encoding="utf-8")
        (self.root / "agy/sajtok").mkdir()
        for i in range(2):
            (self.root / ("agy/sajtok/k%d.md" % i)).write_text("---\ntags: [x]\nzsir: 45\n---\n\nx\n", encoding="utf-8")
            (self.root / ("agy/k%d.md" % i)).write_text("---\ntype: sajt\n---\n\nx\n", encoding="utf-8")
        out = self.ok("type", "suggest", "--min", "2")
        self.assertNotIn("zsir", out)  # a candidate folder's own fields are adopt's business
        for want in ("folder agy/sajtok/", "type: sajt", "tag #sajt", "field erleles", "title 'sajt'"):
            self.assertIn(want, out)
        self.assertNotIn("borok", out)


if __name__ == "__main__":
    unittest.main()
