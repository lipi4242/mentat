"""Role self-image: the upgrade decision (SZ-X3), the agy/szerep-onkep.md blocks, the szerepek step."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import shutil
import tempfile
import unittest

import szerep_onkep as so
from _bekotes_repo import BIZ, bk, leltar, make_agent, szerepek, write

OLD = "Úgy gondolj magadra, mint egy gondos kertész.\nFő célod: semmi ne hervadjon el."
NEW = "Úgy gondolj magadra, mint egy gondos kertész.\nFő célod: semmi ne hervadjon el, és minden nőjön."
MINE = "Úgy gondolj magadra, mint a gazda saját kertésze, aki a rózsákat szereti."


class Decide(unittest.TestCase):
    """The five cases of the upgrade table, plus the custom role and an already-current block."""

    def test_no_block_is_written(self):
        self.assertEqual(so.decide(None, None, NEW), so.BEIR)

    def test_untouched_and_same_default_is_left_alone(self):
        self.assertEqual(so.decide(OLD, so.digest(OLD), OLD), so.SEMMI)

    def test_untouched_and_new_default_is_replaced(self):
        self.assertEqual(so.decide(OLD, so.digest(OLD), NEW), so.CSERE)

    def test_owner_changed_and_same_default_is_kept(self):
        self.assertEqual(so.decide(MINE, so.digest(OLD), OLD), so.MARAD)

    def test_owner_changed_and_new_default_is_offered_with_a_diff(self):
        self.assertEqual(so.decide(MINE, so.digest(OLD), NEW), so.FELAJANL)
        d = so.diff(MINE, NEW, "kiado")
        self.assertIn("-" + MINE, d)
        self.assertIn("+Fő célod: semmi ne hervadjon el, és minden nőjön.", d)

    def test_a_custom_role_is_never_replaced(self):
        for default in (None, OLD, NEW):
            self.assertEqual(so.decide(MINE, so.CUSTOM, default), so.MARAD)
        self.assertEqual(so.decide(MINE, so.digest(OLD), None), so.MARAD)

    def test_a_block_already_equal_to_the_new_default_needs_nothing(self):
        self.assertEqual(so.decide(NEW, so.digest(OLD), NEW), so.SEMMI)

    def test_the_hash_ignores_trailing_spaces_and_line_endings_only(self):
        self.assertEqual(so.digest(OLD), so.digest("\n" + OLD.replace("\n", "  \r\n") + "\n\n"))
        self.assertNotEqual(so.digest(OLD), so.digest(OLD + "."))


class Blocks(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.path = self.repo / "agy" / so.FILE

    def test_writes_every_template_role_with_its_default_hash(self):
        self.assertTrue(so.write(self.repo, "agy", ["asszisztens", "kiado"], "hu"))
        got = so.parse(self.path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(got), ["asszisztens", "kiado"])
        default = so.template("kiado", "hu")
        self.assertIn("a kódbázis gazdája és senior mérnöke", default)
        self.assertEqual(got["kiado"]["text"], default)
        self.assertEqual(got["kiado"]["alap"], so.digest(default))

    def test_an_existing_block_is_never_overwritten_and_a_rerun_is_byte_identical(self):
        so.write(self.repo, "agy", ["asszisztens"], "hu")
        text = self.path.read_text(encoding="utf-8")
        old = so.parse(text)["asszisztens"]["text"]
        self.path.write_text(text.replace(old, MINE), encoding="utf-8")
        before = self.path.read_bytes()
        self.assertFalse(so.write(self.repo, "agy", ["asszisztens"], "hu"))
        self.assertEqual(self.path.read_bytes(), before)
        so.write(self.repo, "agy", ["asszisztens", "fejleszto"], "hu")
        got = so.parse(self.path.read_text(encoding="utf-8"))
        self.assertEqual(got["asszisztens"]["text"], MINE)
        self.assertIn("fejleszto", got)

    def test_a_custom_role_starts_from_its_own_file_with_alap_custom(self):
        write(self.repo, "agy/szerepek/penzugy.md", "---\nname: penzugy\ndeny: []\n---\n\n# penzugy\n\n"
              "## Szerep önkép\n\n%s\n\n## Korlátok\n\n- semmi\n" % MINE)
        so.write(self.repo, "agy", ["penzugy", "nincs-fajlja"], "hu")
        got = so.parse(self.path.read_text(encoding="utf-8"))
        self.assertEqual(got["penzugy"], {"alap": so.CUSTOM, "verzio": so.version(), "text": MINE})
        self.assertNotIn("nincs-fajlja", got)
        self.assertEqual(so.plan(self.repo, "agy", ["penzugy"], "hu"), [("penzugy", so.MARAD, None)])

    def test_the_installed_role_file_points_at_the_block(self):
        tpl = (so.HERE / "szerepek" / "kiado.en.md").read_text(encoding="utf-8")
        out = so.pointer(tpl, "kiado", "en")
        self.assertEqual(so.section(out, "en"), so.POINTER["en"] % "kiado")
        self.assertIn("`szerep=kiado` block of `agy/szerep-onkep.md`", out)
        self.assertNotIn("owner and senior engineer of the codebase", out)
        self.assertIn("## Limits", out)


class Step(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.assertEqual(leltar(self.root).returncode, 0)

    def onkep(self):
        r = bk(self.root, "onkep", "--repo", ".")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_the_step_writes_the_blocks_keeps_the_owners_and_the_upgrade_plan_reads_them(self):
        r = szerepek(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        path = self.root / "agy/szerep-onkep.md"
        got = so.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(got), ["asszisztens", "backlog-manager", "fejleszto"])
        role = (self.root / "agy/szerepek/asszisztens.md").read_text(encoding="utf-8")
        self.assertIn("`agy/szerep-onkep.md` `szerep=asszisztens` blokkjában", role)
        self.assertNotIn("kabinetfőnöke", role)
        self.assertIn("kabinetfőnöke", got["asszisztens"]["text"])
        self.assertEqual(self.onkep(), "asszisztens: semmi\nbacklog-manager: semmi\nfejleszto: semmi\n")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(got["fejleszto"]["text"], MINE), encoding="utf-8")
        self.assertEqual(szerepek(self.root).returncode, 0)
        self.assertEqual(so.parse(path.read_text(encoding="utf-8"))["fejleszto"]["text"], MINE)
        tpl = self.root / ".mentat/bin/bekotes/szerepek/fejleszto.hu.md"  # a new release's default
        tpl.write_text(tpl.read_text(encoding="utf-8").replace("Úgy gondolj magadra", "Mindig úgy gondolj magadra"),
                       encoding="utf-8")
        out = self.onkep()
        self.assertIn("fejleszto: felajanl\n", out)
        self.assertIn("+Mindig úgy gondolj magadra", out)
        self.assertIn("asszisztens: semmi\n", out)
        tpl = self.root / ".mentat/bin/bekotes/szerepek/asszisztens.hu.md"
        tpl.write_text(tpl.read_text(encoding="utf-8").replace("kabinetfőnöke", "jobbkeze"), encoding="utf-8")
        r = bk(self.root, "onkep", "--repo", ".", "--alkalmaz")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("asszisztens: csere\n", r.stdout)
        after = so.parse(path.read_text(encoding="utf-8"))
        self.assertIn("jobbkeze", after["asszisztens"]["text"])
        self.assertEqual(after["asszisztens"]["alap"], so.digest(after["asszisztens"]["text"]))
        self.assertEqual(after["fejleszto"], so.parse(text.replace(got["fejleszto"]["text"], MINE))["fejleszto"])
        self.assertEqual(self.onkep(), "asszisztens: semmi\nbacklog-manager: semmi\nfejleszto: felajanl\n"
                         + so.diff(MINE, so.section(
                             (self.root / ".mentat/bin/bekotes/szerepek/fejleszto.hu.md").read_text(encoding="utf-8"), "hu"),
                             "fejleszto"))
        r = bk(self.root, "blokk", "--repo", ".", "--business", "zoldag")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("@agy/szerep-onkep.md", (self.root / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertTrue((self.root / BIZ).is_dir())
        self.assertEqual(json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))["roles"]["default"], "asszisztens")

    def test_a_custom_role_gets_its_block_from_onkep_alkalmaz_and_keeps_it(self):
        self.assertEqual(szerepek(self.root).returncode, 0)
        write(self.root, "agy/szerepek/penzugy.md", "---\nname: penzugy\ndeny: []\n---\n\n# penzugy\n\n"
              "## Szerep önkép\n\n%s\n\n## Korlátok\n\n- semmi\n" % MINE)
        m = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
        m["roles"]["installed"].append("penzugy")
        (self.root / "mentat.json").write_text(json.dumps(m), encoding="utf-8")
        r = bk(self.root, "onkep", "--repo", ".", "--alkalmaz")
        self.assertIn("penzugy: beir\n", r.stdout)
        got = so.parse((self.root / "agy/szerep-onkep.md").read_text(encoding="utf-8"))
        self.assertEqual((got["penzugy"]["alap"], got["penzugy"]["text"]), (so.CUSTOM, MINE))
        self.assertIn("penzugy: marad\n", self.onkep())
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(agents.startswith("<!-- mentat:managed:start self-image -->"))
        self.assertIn("- penzugy: a gazda saját kertésze, aki a rózsákat szereti", agents)


if __name__ == "__main__":
    unittest.main()
