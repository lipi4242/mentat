"""`type adopt`: a hand-made folder becomes a type; the notes stay byte-identical."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"
NOTE = "---\ntype: recept\ncim: %s\nfogas: %s\nido_perc: %s\nkeszult: %s\nhozzavalok: [liszt, tojas]\n%stags: []\n---\n\n# %s\n"


class Adopt(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                        "--repo", str(self.root), "--base", "https://x/"], capture_output=True)
        self.dir = self.root / "agy/receptek"
        self.dir.mkdir()
        rows = [("Palacsinta", "desszert", "30", "2026-01-02", "forras: nagymama\n"),
                ("Gulyás", "leves", "120", "2026-02-03", ""), ("Lecsó", "fo", "45", "2026-03-04", ""),
                ("Pogácsa", "desszert", "60", "2026-04-05", ""), ("Halászlé", "leves", "90", "2026-05-06", "")]
        for cim, fogas, ido, kesz, extra in rows:
            (self.dir / (cim.lower() + ".md")).write_text(NOTE % (cim, fogas, ido, kesz, extra, cim), encoding="utf-8")
        (self.dir / "_meta.md").write_text("# kézi index\n\nSaját szöveg marad.\n- [Lecsó](lecsó.md) - recept\n",
                                           encoding="utf-8")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True)

    def sums(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.dir.glob("*.md") if p.name != "_meta.md"}

    def test_adopt_infers_conservatively_and_never_touches_the_notes(self):
        before = self.sums()
        r = self.run_tool("type", "adopt", "receptek")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.sums(), before)
        show = self.run_tool("type", "show", "recept").stdout
        for want in ("dir: agy/receptek/", "title field: cim", "cim: text, required", "ido_perc: number, required",
                     "keszult: date, required", "hozzavalok: list, required", "forras: text\n",
                     "fogas: enum (desszert|fo|leves), required"):
            self.assertIn(want, show)
        meta = (self.dir / "_meta.md").read_text(encoding="utf-8")
        self.assertTrue(meta.startswith("# kézi index\n\nSaját szöveg marad.\n"))
        self.assertEqual(meta.count("lecsó.md"), 1)
        self.assertIn("- [Gulyás](gulyás.md) - recept", meta)
        self.assertEqual(self.run_tool("check").returncode, 0)
        self.assertIn("agy/receptek/palacsinta.md [recept]", self.run_tool("find", "palacsinta").stdout)

    def test_adopt_again_or_a_builtin_folder_is_refused(self):
        self.assertEqual(self.run_tool("type", "adopt", "agy/receptek").returncode, 0)
        self.assertTrue(self.run_tool("type", "adopt", "receptek").stdout.startswith("STOP"))
        self.assertTrue(self.run_tool("type", "adopt", "cases").stdout.startswith("STOP"))
        self.assertTrue(self.run_tool("type", "adopt", "nincsilyen").stdout.startswith("STOP"))


if __name__ == "__main__":
    unittest.main()
