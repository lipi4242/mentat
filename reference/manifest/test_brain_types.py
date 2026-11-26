"""Owner-domain entity types: `type add/list/show/edit`, `new <custom>`, and find/where/due/mv/check on them."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"
ISO = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()  # noqa: E731


class Base(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                        "--repo", str(self.root), "--base", "https://x/"], capture_output=True)

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True)

    def add_bor(self):
        r = self.run_tool("type", "add", "bor", "--name", "Bor", "--dir", "borok",
                          "--field", "nev:text:required", "--field", "szin:enum=voros|feher|rose:required",
                          "--field", "evjarat:number", "--field", "kostolo:date", "--due-field", "kostolo",
                          "--desc", "Egy bor a kínálatból")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r


class Define(Base):
    def test_add_writes_the_definition_the_folder_and_both_indexes(self):
        self.add_bor()
        d = (self.root / "agy/types/bor.md").read_text(encoding="utf-8")
        for want in ("type: entity-type", "slug: bor", "dir: borok", "due_field: kostolo",
                     "  - szin:enum:required:enum=voros|feher|rose", "  - evjarat:number"):
            self.assertIn(want, d)
        self.assertIn("Egy bor a kínálatból", (self.root / "agy/borok/_meta.md").read_text(encoding="utf-8"))
        self.assertIn("(bor.md)", (self.root / "agy/types/_meta.md").read_text(encoding="utf-8"))

    def test_add_refuses_builtins_existing_types_and_taken_folders(self):
        self.add_bor()
        for args in (("todo", "--dir", "x"), ("bor", "--dir", "x"), ("ital", "--dir", "borok"),
                     ("ital", "--dir", "cases"), ("Rossz Slug", "--dir", "x")):
            r = self.run_tool("type", "add", args[0], "--name", "X", *args[1:])
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stdout.startswith("STOP"), (args, r.stdout))

    def test_list_show_and_edit(self):
        self.add_bor()
        self.assertRegex(self.run_tool("types").stdout, r"bor +agy/borok/ +0 ")
        self.assertIn("szin: enum (voros|feher|rose), required", self.run_tool("type", "show", "bor").stdout)
        r = self.run_tool("type", "edit", "bor", "--add-field", "termelo:link", "--remove-field", "evjarat")
        self.assertEqual(r.returncode, 0, r.stdout)
        show = self.run_tool("type", "show", "bor").stdout
        self.assertIn("termelo: link", show)
        self.assertNotIn("evjarat", show)
        self.assertEqual(self.run_tool("type", "show", "nincs").returncode, 1)


class Notes(Base):
    def setUp(self):
        super().setUp()
        self.add_bor()

    def test_new_custom_note_fills_frontmatter_and_index(self):
        r = self.run_tool("new", "bor", "Kéknyelű 2019", "--set", "szin=feher", "--set", "evjarat=2019",
                          "--tags", "balaton")
        self.assertEqual(r.stdout.strip(), "agy/borok/keknyelu-2019.md", r.stdout + r.stderr)
        text = (self.root / "agy/borok/keknyelu-2019.md").read_text(encoding="utf-8")
        for want in ("type: bor\n", "nev: Kéknyelű 2019\n", "szin: feher\n", "evjarat: 2019\n",
                     "kostolo: \n", "tags: [balaton]\n", "created: "):
            self.assertIn(want, text)
        self.assertIn("- [Kéknyelű 2019](keknyelu-2019.md) - bor", (self.root / "agy/borok/_meta.md").read_text())
        self.assertEqual(self.run_tool("new", "bor", "X", "--set", "nincsilyen=1").returncode, 1)
        self.assertEqual(self.run_tool("new", "nincstipus", "X").returncode, 2)

    def test_find_names_the_type_and_filters(self):
        self.run_tool("new", "bor", "Olaszrizling", "--set", "szin=feher")
        self.run_tool("new", "todo", "Olaszrizling rendelés")
        out = self.run_tool("find", "olaszrizling").stdout
        self.assertIn("agy/borok/olaszrizling.md [bor]:", out)
        self.assertIn("agy/todos/olaszrizling-rendeles.md [todo]:", out)
        only = self.run_tool("find", "olaszrizling", "--type", "bor").stdout
        self.assertNotIn("todos", only)
        self.assertRegex(only, r"1 hit")

    def test_where_counts_and_due_reports_the_due_field(self):
        self.run_tool("new", "bor", "Furmint", "--set", "szin=feher", "--due", ISO(2))
        self.assertRegex(self.run_tool("where").stdout, r"(?m)^típusok: bor \(1\)")
        due = self.run_tool("due").stdout
        self.assertRegex(due, r"%s .*bor +Furmint +agy/borok/furmint.md" % ISO(2))

    def test_mv_retitles_through_the_title_field_and_fixes_the_index(self):
        self.run_tool("new", "bor", "Juhfark", "--set", "szin=feher")
        self.assertEqual(self.run_tool("mv", "juhfark.md", "--title", "Juhfark 2021").returncode, 0)
        self.assertIn("nev: Juhfark 2021", (self.root / "agy/borok/juhfark-2021.md").read_text())
        self.assertIn("(juhfark-2021.md)", (self.root / "agy/borok/_meta.md").read_text())

    def test_check_warns_and_strict_fails(self):
        self.run_tool("new", "bor", "Jó", "--set", "szin=voros", "--set", "kostolo=" + ISO(1))
        self.assertEqual(self.run_tool("check").returncode, 0)
        self.run_tool("new", "bor", "Rossz", "--set", "szin=kek", "--set", "evjarat=sok", "--set", "kostolo=holnap")
        (self.root / "agy/borok/ures.md").write_text("---\ntype: bor\n---\n\nx\n", encoding="utf-8")
        r = self.run_tool("check")
        self.assertEqual(r.returncode, 0)
        for want in ("agy/borok/rossz.md: szin 'kek' not in voros|feher|rose", "evjarat 'sok' is not a number",
                     "kostolo 'holnap' is not a date", "agy/borok/ures.md: missing nev, szin"):
            self.assertIn(want, r.stdout)
        self.assertRegex(r.stdout.splitlines()[-1], r"^check: 2 note\(s\) with warnings")
        self.assertEqual(self.run_tool("check", "--strict").returncode, 1)


if __name__ == "__main__":
    unittest.main()
