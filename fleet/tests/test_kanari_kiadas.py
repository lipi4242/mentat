"""11-07: a felhasználói Claude-beállítás írói kanárival mennek (kanari.py), a doctor látja a
rögzítés nélküli változást, és a kiadás-lemaradást (release_lag.py)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _essentials_box import entry
from fleet import claude_firstrun, kanari, operator_skills, release_lag


def home_with_roots(case) -> Path:
    home = Path(tempfile.mkdtemp()).resolve()
    case.addCleanup(shutil.rmtree, home, True)
    for r in (".claude", ".claude-vilma"):
        (home / r).mkdir()
        (home / r / "settings.json").write_text(json.dumps({"hooks": {}}))
    return home


class Guarded(unittest.TestCase):
    def setUp(self):
        self.home = home_with_roots(self)
        self.a = entry("vilma", claude_account="vilma")
        self.b = entry("bea")  # shared → ~/.claude
        self.writes = []

    def write(self, root):
        self.writes.append(root.name)
        (root / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"x": 1}]}}))
        return [f"írva: {root.name}"]

    def test_uj_piros_a_kanarin_visszaallit_es_a_tobbi_gyoker_erintetlen(self):
        before = (self.home / ".claude/settings.json").read_text()
        calls = iter([{"bea": set()}, {"bea": {"küldés NEM MENNE"}}])
        with self.assertRaises(kanari.Refused) as cm:
            kanari.guarded("teszt", [self.home / ".claude-vilma", self.home / ".claude"], self.write,
                           home=self.home, agents=[self.b], probe_fn=lambda ag, h: next(calls))
        self.assertIn("küldés NEM MENNE", str(cm.exception))
        self.assertEqual(self.writes, [".claude"])           # a kanári az ágenses gyökér
        self.assertEqual((self.home / ".claude/settings.json").read_text(), before)
        self.assertEqual(json.loads((self.home / ".claude-vilma/settings.json").read_text()), {"hooks": {}})

    def test_mar_elotte_is_piros_nem_akasztja_meg_es_rogzit(self):
        same = {"bea": {"régi hiba"}}
        notes = kanari.guarded("teszt", [self.home / ".claude", self.home / ".claude-vilma"], self.write,
                               home=self.home, agents=[self.b], probe_fn=lambda ag, h: same)
        self.assertEqual(sorted(self.writes), [".claude", ".claude-vilma"])
        self.assertTrue(any("kanári: .claude" in n for n in notes), notes)
        self.assertEqual(kanari.drift(self.home), [])

    def test_drift_rogzites_nelkuli_valtozas_es_soha_nem_rogzitett(self):
        self.assertEqual(len(kanari.drift(self.home)), 2)    # soha nem rögzített
        kanari.record(self.home, [self.home / ".claude", self.home / ".claude-vilma"], "teszt")
        self.assertEqual(kanari.drift(self.home), [])
        (self.home / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": []}, "theme": "x"}))
        d = kanari.drift(self.home)
        self.assertEqual(len(d), 1)
        self.assertIn("rögzített kanári-futás nélkül", d[0])
        # ami nem hook/plugin (pl. téma), az nem drift
        kanari.record(self.home, [self.home / ".claude"], "teszt")
        (self.home / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": []}, "theme": "y"}))
        self.assertEqual(kanari.drift(self.home), [])

    def test_firstrun_settings_irasa_kanarival_es_visszaall(self):
        e = entry("vilma", claude_account="vilma", workdir=str(self.home / "vilma"))
        before = (self.home / ".claude-vilma/settings.json").read_text()
        calls = iter([{"vilma": set()}, {"vilma": {"új hiba"}}])
        with mock.patch.object(kanari, "_local_agents", return_value=[e]), \
                mock.patch.object(kanari, "probe", lambda ag, h: next(calls)):
            out = claude_firstrun.apply(e, home=self.home)
        self.assertTrue(any("új hiba" in p for p in out["problems"]), out)
        self.assertEqual((self.home / ".claude-vilma/settings.json").read_text(), before)
        with mock.patch.object(kanari, "_local_agents", return_value=[e]), \
                mock.patch.object(kanari, "probe", lambda ag, h: {"vilma": set()}):
            out = claude_firstrun.apply(e, home=self.home)
        self.assertEqual(out["problems"], [])
        self.assertIn("capture-session-id", (self.home / ".claude-vilma/settings.json").read_text())
        self.assertEqual([d for d in kanari.drift(self.home) if ".claude-vilma" in d], [])

    def test_operator_skill_link_kanarival_es_visszaall(self):
        target = self.home / ".claude/skills"
        calls = iter([{"bea": set()}, {"bea": {"új hiba"}}])
        with mock.patch.object(kanari, "_local_agents", return_value=[self.b]), \
                mock.patch.object(kanari, "probe", lambda ag, h: next(calls)), \
                mock.patch.object(Path, "home", return_value=self.home):
            notes = operator_skills.link_operator_skills(target=target)
        self.assertTrue(any("NEM linkelve" in n for n in notes), notes)
        self.assertFalse((target / "merge-agents").is_symlink())


class ReleaseLag(unittest.TestCase):
    LS = ("a\trefs/tags/v0.5.0\nb\trefs/tags/v0.5.0^{}\nc\trefs/tags/v0.10.1\nd\trefs/tags/v0.9.9\n"
          "e\trefs/tags/nem-verzio\n")

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)

    def fake(self, describe="v0.5.0-12-gabc", ls=None, fail_net=False):
        def run(cmd, **kw):
            if "describe" in cmd:
                return subprocess.CompletedProcess(cmd, 0 if describe else 128, describe + "\n", "")
            if fail_net:
                raise subprocess.TimeoutExpired(cmd, 15)
            return subprocess.CompletedProcess(cmd, 0, ls if ls is not None else self.LS, "")
        return run

    def test_legnagyobb_tag_szamszeruen(self):
        self.assertEqual(release_lag.latest_tag(self.LS), "v0.10.1")

    def test_lemaradas_figyelmeztetes(self):
        lag, unk, fact = release_lag.check(self.home, run=self.fake(), now=100.0, checkout=self.home)
        self.assertIn("v0.10.1", lag)
        self.assertIsNone(unk)

    def test_naprakesz_teny(self):
        lag, unk, fact = release_lag.check(self.home, run=self.fake("v0.10.1"), now=100.0, checkout=self.home)
        self.assertEqual((lag, unk), (None, None))
        self.assertIn("v0.10.1", fact)

    def test_halozati_hiba_nem_piros_csak_nem_merheto(self):
        lag, unk, _ = release_lag.check(self.home, run=self.fake(fail_net=True), now=100.0, checkout=self.home)
        self.assertIsNone(lag)
        self.assertIn("nem mérhető", unk)

    def test_cache_a_halozatot_kimeli(self):
        release_lag.check(self.home, run=self.fake(), now=100.0, checkout=self.home)
        lag, unk, _ = release_lag.check(self.home, run=self.fake(fail_net=True), now=200.0, checkout=self.home)
        self.assertIn("v0.10.1", lag)

    def test_tag_nelkuli_checkout_nem_merheto(self):
        lag, unk, _ = release_lag.check(self.home, run=self.fake(""), now=100.0, checkout=self.home)
        self.assertIsNone(lag)
        self.assertIn("nincs v* tagje", unk)


if __name__ == "__main__":
    unittest.main()
