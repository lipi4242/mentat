"""join/upgrade egy ideiglenes repón: csak a saját kulcsainkhoz nyúlunk, a
helyi szerkesztést nem írjuk felül."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import join, __version__  # noqa: E402


class TestJoin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_join_writes_three_files_and_keeps_other_settings(self):
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}))
        r = join.join(self.repo, agent="probe", brain="0.1.2", reducer="0.2.2")
        s = json.loads((self.repo / ".claude" / "settings.json").read_text())
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls)"])
        self.assertTrue(s["enabledPlugins"]["fleet@mentat"])
        self.assertEqual(s["extraKnownMarketplaces"]["mentat"]["source"]["repo"], join.MARKETPLACE_REPO)
        rules = (self.repo / ".claude" / "rules" / "fleet.md").read_text()
        self.assertIn("`probe`", rules)
        self.assertIn(f"v{__version__}", rules)
        m = r["manifest"]
        self.assertEqual(m["components"], {"fleet": __version__, "brain": "0.1.2", "reducer": "0.2.2"})

    def test_join_rejects_bad_name_and_non_repo(self):
        with self.assertRaises(ValueError):
            join.join(self.repo, agent="Bad Name")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                join.join(Path(d), agent="ok")

    def test_upgrade_preserves_local_edits(self):
        join.join(self.repo, agent="probe")
        rules = self.repo / ".claude" / "rules" / "fleet.md"
        rules.write_text(rules.read_text() + "\n- saját szabály\n")
        r = join.upgrade(self.repo)
        self.assertIn("helyi módosítás", r["rules"])
        self.assertTrue(rules.with_suffix(".md.new").exists())
        self.assertIn("saját szabály", rules.read_text())

    def test_upgrade_replaces_untouched_rules(self):
        join.join(self.repo, agent="probe")
        r = join.upgrade(self.repo)
        self.assertEqual(r["rules"], "frissítve")


    def test_upgrade_regi_fleet_plugint_kikapcsolja(self):
        """2026-10-31, egy élő ágens frissítésénél: a régi pluginnal belépett repóban az upgrade a `fleet@fleet-ops` mellé
        felvette a `fleet@fleet-leader`-t (0.5.0 óta `fleet@mentat`), így két „fleet” plugin futott (dupla /fleet:* és hookok)."""
        join.join(self.repo, agent="probe")
        sp = self.repo / ".claude" / "settings.json"
        s = json.loads(sp.read_text())
        del s["enabledPlugins"]["fleet@mentat"], s["extraKnownMarketplaces"]["mentat"]
        s["enabledPlugins"].update({"fleet@fleet-ops": True, "mas@valahol": True})
        s["extraKnownMarketplaces"]["fleet-ops"] = {"source": {"source": "github", "repo": "lipi4242/fleet-ops"}}
        sp.write_text(json.dumps(s))
        r = join.upgrade(self.repo)
        s = json.loads(sp.read_text())
        self.assertEqual(s["enabledPlugins"], {"fleet@fleet-ops": False, "mas@valahol": True,
                                               "fleet@mentat": True})
        self.assertIn("fleet-ops", s["extraKnownMarketplaces"])  # a felhasználó bejegyzése marad
        self.assertEqual(r["plugin_migration"], {"disabled": ["fleet@fleet-ops"], "enabled": "fleet@mentat",
                                                 "run_on_box_before_merge": "fleet plugin install probe"})
        before = sp.read_text()
        r2 = join.upgrade(self.repo)  # idempotens
        self.assertEqual(sp.read_text(), before)
        self.assertNotIn("plugin_migration", r2)


if __name__ == "__main__":
    unittest.main()
