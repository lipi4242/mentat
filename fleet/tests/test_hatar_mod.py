"""`fleet secrets merge-mode`: az ágens-határ összeolvasztás-módjának jelzője (CISO Q2, PR #112).

Jelző nélkül a git-írás, a tmux-gépelés és a kifelé ható parancs szabad (Rilí minden tickben
`git reset --hard`-ot futtat); a jelzőt a plan-merge, a hold-outward és a két- vagy többágenses
secrets scan kapcsolja be. A hook oldala (hatar_jel.py) ugyanazt a fájlt olvassa.
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from fleet import REPO_ROOT, cli, hatar_mod as HM, outward_hold_cli, plan_merge, titok_cli

# the shipped copy (plugin/hooks): security/ is internal and does not reach the public repo
sys.path.insert(0, str(REPO_ROOT / "plugin" / "hooks" / "identitas"))
import hatar_jel  # noqa: E402


class Marker(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        p = mock.patch.object(Path, "home", return_value=self.home)
        p.start()
        self.addCleanup(p.stop)
        e = mock.patch.dict("os.environ", {"HOME": str(self.home)})
        e.start()
        self.addCleanup(e.stop)

    def test_be_ki_es_a_hook_ugyanazt_latja(self):
        self.assertFalse(hatar_jel.aktiv())
        HM.on("teszt", "kézi")
        self.assertTrue(hatar_jel.aktiv())
        self.assertIn("ÖSSZEOLVASZTÁS-MÓD", HM.status())
        HM.off()
        self.assertFalse(hatar_jel.aktiv())

    def test_legfeljebb_7_nap(self):
        d = HM.on("teszt", "kézi", until=time.time() + 30 * 86400)
        self.assertLessEqual(d["until"] - d["since"], 7 * 86400)

    def test_release_outward_csak_a_sajat_okat_veszi_le(self):
        HM.on("plan-merge a→b", "plan-merge")
        HM.on("hold-outward b", "hold-outward")
        self.assertIn("marad", HM.off("hold-outward"))
        self.assertTrue(hatar_jel.aktiv())
        HM.on("hold-outward b", "hold-outward")
        HM.off("plan-merge")
        self.assertIn("kikapcsolva", HM.off("hold-outward"))
        self.assertFalse(hatar_jel.aktiv())

    def test_plan_merge_bekapcsolja(self):
        with mock.patch.object(plan_merge, "plan", return_value=[]):
            plan_merge.cmd_plan_merge(NS(donor="a", recipient="b", repo=[], json=True))
        self.assertEqual(HM.read()["set_by"], ["plan-merge"])

    def test_a_scan_sosem_kapcsolja_az_osszeolvasztas_modot(self):
        """11-07: a többágenses scan sem (11-07: 7 napra bekapcsolta, Rilí gitje bukott volna)."""
        from fleet import titok_leltar as L
        with mock.patch.object(L, "scan", return_value={"files": []}), \
                mock.patch.object(L, "save", return_value=self.home / "x"), mock.patch.object(L, "table", return_value=""):
            titok_cli.cmd_scan(NS(agent=["a"], repo=None, json=False, no_hook=True))
            self.assertIsNone(HM.read())
            titok_cli.cmd_scan(NS(agent=["a", "b"], repo=None, json=False, no_hook=True))
        self.assertIsNone(HM.read())
        self.assertFalse(HM.path().exists())

    def test_hold_es_release_outward(self):
        ok = {"ok": True, "target": "box", "engine_knows": True, "removed": True,
              "hold": {"path": "/x", "until": "+4h", "reason": "r"}}
        a = NS(agent="b", until="+4h", reason="r", ssh=None, workdir=None, json=True)
        with mock.patch.object(outward_hold_cli.oh, "hold", return_value=ok):
            outward_hold_cli.cmd_hold(a)
        self.assertEqual(HM.read()["set_by"], ["hold-outward"])
        with mock.patch.object(outward_hold_cli.oh, "release", return_value=ok):
            outward_hold_cli.cmd_release(a)
        self.assertIsNone(HM.read())

    def test_cli(self):
        a = cli.build_parser().parse_args(["secrets", "merge-mode", "on", "--reason", "x"])
        self.assertEqual((a.fn.__name__, a.state), ("cmd", "on"))


if __name__ == "__main__":
    unittest.main()
