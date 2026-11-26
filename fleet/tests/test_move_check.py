"""`fleet map move-check`: az átrendezés csak mozgatás volt-e."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import cli, move_check as mc  # noqa: E402

OLD = """# Ágens

Első szabály.
- Második   szabály.
* Harmadik szabály.

## Hátul
1. Negyedik szabály.
<!-- mentat:managed:start blokk -->
generált sor
<!-- mentat:managed:end blokk -->
"""
REORDERED = """# Ágens
## Hátul
Negyedik szabály.
## Új cím
Harmadik szabály.
Második szabály.
Első szabály.
<!-- mentat:managed:start blokk -->
MÁS generált sor
<!-- mentat:managed:end blokk -->
"""


def codes(old, new, dups=None):
    return sorted(f.code for f in mc.check(old, new, dups))


class Pure(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(mc.normalize("  - a   b  \t"), "a b")
        self.assertEqual(mc.normalize("12. x"), "x")

    def test_clean_reorder_with_new_heading_is_green(self):
        self.assertEqual(codes(OLD, REORDERED), [])

    def test_lost_line_is_named_with_number(self):
        fs = mc.check(OLD, REORDERED.replace("Harmadik szabály.\n", ""))
        self.assertEqual([(f.code, f.subject) for f in fs], [("line-lost", "old:5")])
        self.assertIn("Harmadik szabály.", fs[0].message)

    def test_dups_list_covers_lost_line(self):
        new = REORDERED.replace("Harmadik szabály.\n", "")
        self.assertEqual(codes(OLD, new, Counter({"Harmadik szabály.": 1})), [])

    def test_duplicate_occurrence_removal_needs_list_entry(self):
        old = "Szabály.\nMás.\nSzabály.\n"
        new = "Más.\nSzabály.\n"
        fs = mc.check(old, new)
        self.assertEqual([(f.code, f.subject) for f in fs], [("line-lost", "old:3")])
        self.assertEqual(mc.check(old, new, Counter({"Szabály.": 1})), [])
        # két előfordulás hiányzik, egy lista-sor csak egyet fed le
        fs = mc.check("a\na\na\n", "a\n", Counter({"a": 1}))
        self.assertEqual([f.subject for f in fs], ["old:3"])
        self.assertEqual(mc.check("a\na\na\n", "a\n", Counter({"a": 2})), [])

    def test_new_text_is_red_heading_is_not(self):
        fs = mc.check(OLD, REORDERED + "Átfogalmazott szabály.\n")
        self.assertEqual([(f.code, f.subject) for f in fs], [("text-new", "new:11")])
        self.assertEqual(codes(OLD, REORDERED + "### Még egy cím\n"), [])

    def test_managed_content_ignored_both_sides(self):
        self.assertEqual(codes(OLD + "x\n".replace("x", ""), REORDERED), [])
        # a managed blokkon belüli változás nem lelet, a blokk elvesztése sem a blokk-sorokat jelzi
        self.assertEqual(codes("a\n<!-- mentat:managed:start b -->\nq\n<!-- mentat:managed:end b -->\n", "a\n"), [])


class Cli(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_cli(self, old, new, *extra):
        (self.d / "old.md").write_text(old)
        (self.d / "new.md").write_text(new)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["map", "move-check", str(self.d / "old.md"), str(self.d / "new.md"), *extra])
        return rc, out.getvalue()

    def test_exit_codes(self):
        self.assertEqual(self.run_cli(OLD, REORDERED)[0], 0)
        rc, out = self.run_cli(OLD, REORDERED.replace("Első szabály.\n", ""))
        self.assertEqual(rc, 1)
        self.assertIn("régi 3. sor", out)
        self.assertEqual(cli.main(["map", "move-check", str(self.d / "nincs"), str(self.d / "new.md")]), 2)

    def test_dups_list_accepted_with_valid_place(self):
        new = REORDERED.replace("Első szabály.\n", "")
        (self.d / "mas.md").write_text("x\nElső szabály.\n")
        dups = self.d / "dups.md"
        dups.write_text("- törölve, mert duplikált: Első szabály. → itt maradt meg: mas.md:2\n")
        self.assertEqual(self.run_cli(OLD, new, "--dups", str(dups))[0], 0)
        dups.write_text("törölve, mert duplikált: Első szabály. → itt maradt meg: mas.md:1\n")
        rc, out = self.run_cli(OLD, new, "--dups", str(dups))
        self.assertEqual(rc, 1)
        self.assertIn("dups-bad-place", out)
        dups.write_text("töröltem\n")
        self.assertIn("dups-bad-row", self.run_cli(OLD, new, "--dups", str(dups), "--json")[1])

    def test_dups_row_covers_one_occurrence_cli(self):
        old, new = "Szabály.\nSzabály.\nMás.\n", "Szabály.\nMás.\n"
        (self.d / "mas.md").write_text("Szabály.\n")
        dups = self.d / "dups.md"
        self.assertEqual(self.run_cli(old, new, "--dups", str(dups))[0], 2)
        dups.write_text("")
        rc, out = self.run_cli(old, new, "--dups", str(dups))
        self.assertEqual((rc, "régi 2. sor" in out), (1, True))
        dups.write_text("törölve, mert duplikált: Szabály. → itt maradt meg: mas.md:1\n")
        self.assertEqual(self.run_cli(old, new, "--dups", str(dups))[0], 0)

    def test_dups_place_can_be_section_of_new_file(self):
        new = REORDERED.replace("Első szabály.\n", "")
        dups = self.d / "dups.md"
        dups.write_text("törölve, mert duplikált: Első szabály. → itt maradt meg: #Hátul\n")
        self.assertEqual(self.run_cli(OLD, new, "--dups", str(dups))[0], 0)
        dups.write_text("törölve, mert duplikált: Első szabály. → itt maradt meg: #Nincs ilyen\n")
        self.assertEqual(self.run_cli(OLD, new, "--dups", str(dups))[0], 1)

    def test_json(self):
        rc, out = self.run_cli(OLD, REORDERED + "új\n", "--json")
        self.assertEqual((rc, json.loads(out)["findings"][0]["code"]), (1, "text-new"))


if __name__ == "__main__":
    unittest.main()
