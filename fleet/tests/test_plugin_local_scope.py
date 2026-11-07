"""A /fleet:* plugin a box-oldalon, `--scope local`-lal, az ágens repójában települ.

2026-10-31, egy élő ágens repója a boxán: a `fleet upgrade` után (fleet@fleet-ops: false,
fleet@fleet-leader: true, 0.5.0 óta fleet@mentat) a headless claude a deklarált plugint NEM telepítette, így az
ágensnek egyetlen /fleet:* skillje sem maradt. A user scope pedig közös fiókon minden
ágensnek bekapcsolja.
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fleet import cli, join, plugin_install, registry


class Run:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, cmd, env, cwd=None):
        self.calls.append((cmd[1:], cwd))
        return subprocess.CompletedProcess(cmd, 1 if self.fail else 0, "", "boom" if self.fail else "")


class LocalScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.repo = self.home / "kata"
        (self.repo / ".claude").mkdir(parents=True)
        (self.repo / ".claude" / "settings.json").write_text(json.dumps(
            {"enabledPlugins": {"fleet@fleet-ops": True, "mas@valahol": True}}))
        self.e = registry.normalize({"agent": "kata", "workdir": "%h/kata", "host": "box1"})

    def install(self, run):
        return plugin_install.install_plugin(self.e, claude_bin=Path("claude"), home=self.home, run=run)

    def local(self):
        return json.loads((self.repo / ".claude" / "settings.local.json").read_text())

    def test_local_scope_az_agens_repojaban(self):
        run = Run()
        r = self.install(run)
        self.assertTrue(r["ok"], r)
        self.assertIn((["plugin", "install", "fleet@mentat", "--scope", "local"], self.repo), run.calls)

    def test_a_regi_fleet_plugin_a_local_fajlban_kikapcsolva(self):
        self.install(Run())
        first = (self.repo / ".claude" / "settings.local.json").read_text()
        self.assertEqual(self.local()["enabledPlugins"], {"fleet@fleet-ops": False, "fleet@mentat": True})
        r = self.install(Run())  # idempotens
        self.assertEqual((self.repo / ".claude" / "settings.local.json").read_text(), first)
        self.assertIn("fleet@mentat", r["note"])

    def test_bukott_telepitesnel_a_regi_marad(self):
        r = self.install(Run(fail=True))
        self.assertFalse(r["ok"])
        self.assertFalse((self.repo / ".claude" / "settings.local.json").exists())

    def test_hianyzo_repo_nem_dob(self):
        e = registry.normalize({"agent": "nincs", "workdir": "%h/nincs", "host": "box1"})
        r = plugin_install.install_plugin(e, claude_bin=Path("claude"), home=self.home, run=Run())
        self.assertFalse(r["ok"])
        self.assertIn("nincs", r["note"])

    def test_cli_parancs(self):
        a = cli.build_parser().parse_args(["plugin", "install", "kata"])
        self.assertEqual(a.agent, "kata")


class UpgradeHint(unittest.TestCase):
    def test_upgrade_megmondja_a_box_oldali_parancsot(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            join.join(repo, agent="kata")
            sp = repo / ".claude" / "settings.json"
            s = json.loads(sp.read_text())
            s["enabledPlugins"] = {"fleet@fleet-ops": True}
            sp.write_text(json.dumps(s))
            r = join.upgrade(repo)
        self.assertEqual(r["plugin_migration"]["run_on_box_before_merge"], "fleet plugin install kata")


if __name__ == "__main__":
    unittest.main()
