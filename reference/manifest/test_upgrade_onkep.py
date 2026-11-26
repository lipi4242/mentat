"""The role self-image at an upgrade: the install's own format and decision (bekotes/szerep_onkep.py),
so a block the install wrote is recognised; the owner's block stays, our untouched default is
refreshed, a changed default is offered (diff) and applied only on --adopt-onkep, never silently;
the rest of szerep-onkep.md is never touched."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_upgrade_onkep as ok  # noqa: E402

so = ok.engine()
ROLE = "asszisztens"
NOW = so.template(ROLE, "hu")          # the shipped default of this release
OLD = "Segítek emlékezni."            # a default of an older release


class Apply(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / "mentat.json").write_text(json.dumps({"roles": {"default": ROLE, "installed": [ROLE]}}), encoding="utf-8")
        self.file = self.root / "agy" / so.FILE
        self.file.parent.mkdir()

    def write(self, block):
        self.file.write_text("# Szerep önkép\n\nA gazda saját sora.\n\n" + block, encoding="utf-8")

    def act(self):
        return [(r, a) for r, a, _, _ in ok.plan(self.root, "agy", "hu")]

    def test_the_install_s_own_block_is_up_to_date(self):
        self.assertTrue(so.write(self.root, "agy", [ROLE], "hu"))
        self.assertEqual(self.act(), [(ROLE, "uptodate")], "the install's format is the upgrade's")
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9"), [])

    def test_an_untouched_old_default_is_refreshed_and_restamped(self):
        self.write(so.render(ROLE, OLD, so.digest(OLD), "0.6.0"))
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9"), [(ROLE, "replace")])
        b = so.parse(self.file.read_text(encoding="utf-8"))[ROLE]
        self.assertEqual((b["text"], b["alap"], b["verzio"]), (NOW, so.digest(NOW), "9.9.9"))
        self.assertIn("A gazda saját sora.", self.file.read_text(encoding="utf-8"))

    def test_the_owner_s_text_is_kept_when_our_default_did_not_change(self):
        self.write(so.render(ROLE, "A tulajdonos zenész.", so.digest(NOW), "0.6.0"))
        before = self.file.read_text(encoding="utf-8")
        self.assertEqual(self.act(), [(ROLE, "keep")])
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9"), [])
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)

    def test_offer_is_shown_and_adopted_only_on_the_flag(self):
        self.write(so.render(ROLE, "A tulajdonos zenész.", so.digest(OLD), "0.6.0"))
        before = self.file.read_text(encoding="utf-8")
        plan = ok.plan(self.root, "agy", "hu")
        self.assertEqual(plan[0][1], "offer")
        self.assertIn("kabinetfőnöke", plan[0][3], "the offer shows the difference")
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9"), [])
        self.assertEqual(self.file.read_text(encoding="utf-8"), before, "not adopted without the flag")
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9", adopt=[ROLE]), [(ROLE, "adopt")])
        text = self.file.read_text(encoding="utf-8")
        self.assertIn("kabinetfőnöke", text)
        self.assertIn("A gazda saját sora.", text, "text outside the block is kept")
        self.assertIn("A tulajdonos zenész.", (self.file.parent / "szerep-onkep.elozo.md").read_text(encoding="utf-8"))

    def test_no_block_gets_the_default_and_no_roles_touches_nothing(self):
        self.assertEqual(ok.apply(self.root, "agy", "hu", "9.9.9"), [(ROLE, "install")])
        self.assertIn("alap=" + so.digest(NOW), self.file.read_text(encoding="utf-8"))
        (self.root / "mentat.json").write_text("{}", encoding="utf-8")
        self.file.unlink()
        self.assertEqual(ok.plan(self.root, "agy", "hu"), [])
        self.assertFalse(self.file.exists())


if __name__ == "__main__":
    unittest.main()
