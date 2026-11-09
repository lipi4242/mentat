"""11-07: az essentials-próba, és hogy a `hook install` piros ágensnél semmit nem ír.

11-07: a kapu egy lépésben ment ki a box minden Claude-gyökerébe; két ágens (agent.env-es unit,
a token csak a telegram.env-ben) némán nem tudott írni a tulajdonosnak, a todo_poll tiltva lett."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import os
import unittest
from unittest import mock

from _essentials_box import FAKE, entry, leltar, make_box, ours
from fleet import essentials as E, essentials_env as EE, titok_kanari as K, titok_telepit as T


class Probe(unittest.TestCase):
    def setUp(self):
        self.home = make_box(self)
        self.vilma, self.szervezo = entry("vilma"), entry("szervezo", env_file="agent.env")

    def test_zold_agens(self):
        T.install(self.home, agents=[])
        res = E.probe([self.vilma], self.home)
        self.assertEqual(res["vilma"]["red"], [], res)
        labels = [c[0] for c in E.commands(self.vilma, self.home)]
        for want in ("Telegram-küldés", "Telegram-küldés stdinről", "todo: ki vagyok", "todo: változások (poll)",
                     "git status a repóban", "job: todo_poll.py"):
            self.assertIn(want, labels)

    def test_token_nelkuli_unit_piros_ertek_nelkul(self):
        res = E.probe([self.szervezo], self.home, gate=False)
        red = " ".join(res["szervezo"]["red"])
        self.assertIn("TELEGRAM_BOT_TOKEN", red)
        self.assertIn("fleet install szervezo", red)
        self.assertNotIn(FAKE, E.format_probe(res))

    def test_nem_telepitett_unit_nem_merheto_nem_piros(self):
        os.remove(self.home / ".config/systemd/user/vilma.service")
        res = E.probe([self.vilma], self.home, gate=False)
        self.assertEqual(res["vilma"]["red"], [])
        self.assertTrue(res["vilma"]["unknown"])

    def test_regi_leltar_a_job_szkriptet_tiltja_es_a_proba_latja(self):
        T.install(self.home, agents=[])
        leltar(self.home, self.home / ".config/vilma/jobs/todo_poll.py")
        red = E.probe([self.vilma], self.home)["vilma"]["red"]
        self.assertTrue(any("job: todo_poll.py TILTVA" in r for r in red), red)

    def test_leltarfajlt_betolto_szkript_figyelmeztetes(self):
        (self.home / "vilma/bin/kuld.sh").write_text('set -a; . "$HOME/.config/vilma/telegram.env"; set +a\n')
        leltar(self.home, self.home / ".config/vilma/telegram.env")
        warn = EE.sourcing_warnings(self.vilma, self.home)
        self.assertTrue(warn and "kuld.sh" in warn[0] and "env-ből" in warn[0], warn)


class Install(unittest.TestCase):
    def setUp(self):
        self.home = make_box(self)
        self.vilma, self.szervezo = entry("vilma"), entry("szervezo", env_file="agent.env")

    def test_piros_agensnel_semmit_nem_ir(self):
        with self.assertRaises(T.SelfTestFailed) as cm:
            T.install(self.home, agents=[self.vilma, self.szervezo])
        self.assertIn("szervezo", str(cm.exception))
        self.assertEqual((ours(self.home, ".claude"), ours(self.home, ".claude-vilma")), ([], []))
        self.assertFalse((T.code_dir(self.home) / "current").exists())

    def test_force_telepit_de_hangosan(self):
        notes = T.install(self.home, agents=[self.vilma, self.szervezo], force=True)
        self.assertTrue(any(n.startswith("!!! --force") and "szervezo" in n for n in notes), notes)
        self.assertEqual(len(ours(self.home, ".claude-vilma")), 1)

    def test_dry_run_nem_ir(self):
        notes = T.install(self.home, agents=[self.vilma], dry_run=True)
        self.assertTrue(any("--dry-run" in n for n in notes), notes)
        self.assertEqual(ours(self.home, ".claude"), [])
        self.assertFalse((T.code_dir(self.home) / "current").exists())

    def test_kanari_bukasnal_visszaall_a_tobbi_erintetlen(self):
        real, calls = E.probe, []

        def probe(*a, **kw):
            calls.append(kw)
            res = real(*a, **kw)
            if "command" in kw:  # a kanári-próba: a beírt parancssor „bukik"
                res["vilma"]["red"].append("kanári-hiba (teszt)")
            return res
        with mock.patch.object(E, "probe", side_effect=probe), self.assertRaises(T.SelfTestFailed):
            T.install(self.home, agents=[self.vilma])
        self.assertEqual(len(calls), 2)
        self.assertEqual((ours(self.home, ".claude"), ours(self.home, ".claude-vilma")), ([], []))

    def test_zold_boxon_minden_gyokerbe(self):
        notes = T.install(self.home, agents=[self.vilma])
        self.assertTrue(any("(kanári)" in n for n in notes), notes)
        self.assertEqual((len(ours(self.home, ".claude")), len(ours(self.home, ".claude-vilma"))), (1, 1))

    def test_refused_tipus(self):
        self.assertTrue(issubclass(K.Refused, RuntimeError))


if __name__ == "__main__":
    unittest.main()
