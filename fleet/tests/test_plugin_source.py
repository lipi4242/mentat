"""A plugin-forrás: egyetlen konstans, a commitolt settings sosem kap gépfüggő
útvonalat, a helyi forrás csak a nem commitolt settings.local.json-ba kerül."""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fleet import join, plugin_source  # noqa: E402


class TestSingleConstant(unittest.TestCase):
    def test_repo_slug_literal_lives_only_in_plugin_source(self):
        pat = re.compile(r"lipi4242/mentat\b(?!-)")
        hits = [str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")
                if p.name != "plugin_source.py" and pat.search(p.read_text())]
        self.assertEqual(hits, [], "a repó neve csak a plugin_source.PUBLIC_REPO-ban lehet")

    def test_join_reads_the_constant(self):
        self.assertEqual(join.DEFAULT_MARKETPLACE["repo"], plugin_source.PUBLIC_REPO)


class TestJoinSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "r"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.local = Path(self.tmp.name) / "checkout"
        (self.local / ".claude-plugin").mkdir(parents=True)
        (self.local / ".claude-plugin" / "marketplace.json").write_text("{}")
        self.s = self.repo / ".claude" / "settings.json"
        self.sl = self.repo / ".claude" / "settings.local.json"

    def test_default_committed_settings_use_public_repo_and_no_abs_path(self):
        join.join(self.repo, agent="probe")
        text = self.s.read_text()
        self.assertEqual(json.loads(text)["extraKnownMarketplaces"][join.MARKETPLACE_NAME]["source"]["repo"],
                         plugin_source.PUBLIC_REPO)
        self.assertNotIn(self.tmp.name, text)
        self.assertNotRegex(text, r'"/')
        self.assertFalse(self.sl.exists())

    def test_local_source_writes_only_local_file(self):
        join.join(self.repo, agent="probe", plugin_source=f"local:{self.local}")
        committed = self.s.read_text()
        self.assertNotIn(str(self.local), committed)
        self.assertEqual(json.loads(committed)["extraKnownMarketplaces"][join.MARKETPLACE_NAME]["source"]["repo"],
                         plugin_source.PUBLIC_REPO)
        loc = json.loads(self.sl.read_text())
        src = loc["extraKnownMarketplaces"][join.MARKETPLACE_NAME]["source"]
        self.assertEqual(src, {"source": "directory", "path": str(self.local.resolve())})

    def test_local_source_keeps_users_existing_local_settings(self):
        (self.repo / ".claude").mkdir()
        mine = {"permissions": {"allow": ["Bash(ls)"]},
                "extraKnownMarketplaces": {join.MARKETPLACE_NAME: {"source": {"source": "directory", "path": "/mine"}}}}
        self.sl.write_text(json.dumps(mine))
        join.join(self.repo, agent="probe", plugin_source=f"local:{self.local}")
        self.assertEqual(json.loads(self.sl.read_text()), mine)

    def test_bad_local_source_is_refused_before_writing(self):
        with self.assertRaises(ValueError):
            join.join(self.repo, agent="probe", plugin_source=f"local:{self.local}/nincs")
        with self.assertRaises(ValueError):
            join.join(self.repo, agent="probe", plugin_source="ftp://x")
        self.assertFalse(self.s.exists())


class TestParse(unittest.TestCase):
    def test_d6_public_repo_and_marketplace_name(self):
        self.assertEqual(plugin_source.PUBLIC_REPO, "lipi4242/mentat")
        self.assertEqual(plugin_source.MARKETPLACE_NAME, "mentat")
        self.assertEqual(plugin_source.PLUGIN_KEY, "fleet@mentat")

    def test_the_old_marketplace_plugin_is_legacy_after_0_5(self):
        s = {"enabledPlugins": {"fleet@fleet-leader": True, "fleet@mentat": True, "mas@x": True}}
        self.assertEqual(plugin_source.legacy_plugins(s), ["fleet@fleet-leader"])

    def test_the_root_marketplace_names_this_plugin(self):
        m = json.loads((ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(m["name"], plugin_source.MARKETPLACE_NAME)
        plugin = next(p for p in m["plugins"] if p["name"] == "fleet")
        self.assertEqual(plugin["source"], "./fleet/plugin")
        own = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin["version"], own["version"], "bump both together")

    def test_none_is_public(self):
        self.assertEqual(plugin_source.parse(None).add_arg, plugin_source.PUBLIC_REPO)
        self.assertFalse(plugin_source.parse(None).local)

    def test_env_override_only_accepts_owner_repo(self):
        self.assertEqual(plugin_source.public_repo({"FLEET_MARKETPLACE_REPO": "me/fork"}), "me/fork")
        self.assertEqual(plugin_source.public_repo({"FLEET_MARKETPLACE_REPO": "/abs/path"}), plugin_source.PUBLIC_REPO)


if __name__ == "__main__":
    unittest.main()
