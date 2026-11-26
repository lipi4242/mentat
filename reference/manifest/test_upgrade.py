"""mentat_upgrade.py on each install kind, run as UPGRADE.md runs it: from .mentat/bin/, after
the step-2 download (the real curl list) with a sha256 list. Plan first, apply only with --yes
and a current plan, a backup branch, the USER's files never deleted or overwritten."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE))
import _upgrade_fixture as fx  # noqa: E402
import mentat_upgrade_inv as inv  # noqa: E402
import mentat_verify as mv  # noqa: E402


def install(tree, lang="hu"):
    """The step-2 download of UPGRADE.hu.md (the same curl list as initialization.hu.md)."""
    root = pathlib.Path(tempfile.mkdtemp())
    doc = "initialization.hu.md" if lang == "hu" else "initialization.md"
    for dest, src in mv.listing((tree / "reference" / doc).read_text(encoding="utf-8")):
        (root / ".mentat/bin" / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tree / src, root / ".mentat/bin" / dest)
    return root

VERSION = json.loads((TREE / "release.json").read_text(encoding="utf-8"))["version"]


class Base(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.env = fx.isolated_env(self.home)
        self.root = install(TREE)
        meta = json.loads((TREE / "release.json").read_text(encoding="utf-8"))
        meta.update(files=mv.generate(TREE), files_known=mv.known(TREE))
        (self.root / ".mentat/bin/release.json").write_text(json.dumps(meta), encoding="utf-8")

    def up(self, *args):
        return subprocess.run([sys.executable, "-I", str(self.root / ".mentat/bin/mentat_upgrade.py"), *args,
                               "--repo", str(self.root)], capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")

    def snapshot(self):
        return {rel: (self.root / rel).read_text(encoding="utf-8") for rel in fx.FILES
                if not rel.startswith(("anytime_engine/", "AGENTS.md", ".gitignore", ".claude/settings.json"))}


class Kinds(Base):
    def test_the_kinds(self):
        self.assertEqual(inv.inventory(self.root)["kind"], "none")
        fx.pre05(self.root, self.env)
        got = inv.inventory(self.root)
        self.assertEqual((got["kind"], got["lang"], got["engine"]["version"]), ("pre-0.5", "hu", "0.2.2"))
        self.assertEqual(got["knowledge"], ["docs"])
        self.assertEqual(got["git"]["dirty"], [], "the download in .mentat/ is not the USER's change")
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": {"brain": {"root": "agy"}}}), encoding="utf-8")
        self.assertEqual(inv.inventory(self.root)["kind"], "brain")
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": {
            "brain": {"root": "agy"}, "engine": {"path": "anytime_engine"}}}), encoding="utf-8")
        self.assertEqual(inv.inventory(self.root)["kind"], "brain+engine")
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": {
            "brain": {"root": "agy"}, "fleet": {}}}), encoding="utf-8")
        self.assertEqual(inv.inventory(self.root)["kind"], "box")

    def test_a_box_agent_is_sent_to_box_upgrade(self):
        fx.pre05(self.root, self.env)
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": {"brain": {}, "fleet": {}}}), encoding="utf-8")
        r = self.up("plan")
        self.assertIn("fleet box-upgrade --to v%s" % VERSION, r.stdout)
        self.assertNotEqual(r.returncode, 0)

    def test_nothing_to_upgrade_points_to_first_install(self):
        self.assertIn("FIRST-INSTALL.md", self.up("plan").stdout)


class Guards(Base):
    def setUp(self):
        super().setUp()
        fx.pre05(self.root, self.env)

    def test_plan_writes_nothing_in_the_users_files(self):
        before = fx.git(self.root, "status", "--porcelain", env=self.env).stdout
        r = self.up("plan", "--agent", "Terem")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PLAN backup", r.stdout)
        self.assertIn("docs", r.stdout, "the plan says the notes stay where they are")
        self.assertEqual(fx.git(self.root, "status", "--porcelain", env=self.env).stdout, before)

    def test_apply_needs_yes_and_a_current_plan(self):
        self.assertIn("--yes", self.up("apply", "--agent", "Terem").stdout)
        self.assertIn("no current plan", self.up("apply", "--yes", "--agent", "Terem").stdout)
        self.up("plan", "--agent", "Terem")
        (self.root / "docs" / "uj.md").write_text("új\n", encoding="utf-8")
        fx.commit(self.root, "moved on", self.env)
        self.assertIn("no current plan", self.up("apply", "--yes", "--agent", "Terem").stdout)

    def test_uncommitted_changes_stop_it(self):
        (self.root / "docs" / "business" / "szobak.md").write_text("félkész\n", encoding="utf-8")
        r = self.up("plan", "--agent", "Terem")
        self.assertIn("uncommitted", r.stdout)
        self.assertEqual((self.root / "docs" / "business" / "szobak.md").read_text(encoding="utf-8"), "félkész\n")

    def test_a_symlinked_part_is_not_written_through(self):
        (self.root / "AGENTS.md").rename(self.root / "elsewhere.md")
        (self.root / "AGENTS.md").symlink_to(self.root / "elsewhere.md")
        fx.commit(self.root, "link", self.env)
        self.assertIn("symbolic links", self.up("plan", "--agent", "Terem").stdout)

    def test_a_change_that_is_not_the_upgrades_is_not_committed(self):
        import mentat_upgrade_steps as st
        with open(self.root / ".gitignore", "a", encoding="utf-8") as f:
            f.write(".mentat/\n")  # as the skeleton step leaves it
        fx.commit(self.root, "ignore", self.env)
        (self.root / "data" / "rules.yaml").write_text("lemondas_ora: 24\n", encoding="utf-8")
        staged, problem = st.commit(self.root, "old", VERSION, "agy", "hu")
        self.assertIsNone(staged)
        self.assertIn("data/rules.yaml", problem)
        self.assertEqual((self.root / "data" / "rules.yaml").read_text(encoding="utf-8"), "lemondas_ora: 24\n", "left in place")

    def test_a_pre05_brain_needs_its_name(self):
        self.assertIn("--agent", self.up("plan").stdout)

    def test_a_changed_download_stops_before_anything_runs(self):
        p = self.root / ".mentat/bin/mentat_upgrade_steps.py"
        p.write_text(p.read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8")
        r = self.up("plan", "--agent", "Terem")
        self.assertIn("MENTAT-UPGRADE HIBA", r.stdout)
        self.assertIn("mentat_upgrade_steps.py", r.stdout)
        self.assertFalse((self.root / ".mentat/state/upgrade-plan.json").exists())


if __name__ == "__main__":
    unittest.main()
