"""Ágens-határ (H5-3, 2026-10-29): a három mérésen ténylegesen lefutott parancsok tiltva, a munka szabad.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import agens_hatar as A  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get("HOME")
        self.h = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.h, True)
        self.addCleanup(lambda: os.environ.__setitem__("HOME", self.old) if self.old else None)
        os.environ["HOME"] = self.h
        self.vilma, self.ops = os.path.join(self.h, "vilma"), os.path.join(self.h, "ops")
        for d in (self.vilma, self.ops, os.path.join(self.h, ".config/systemd/user")):
            os.makedirs(d)
        subprocess.run(["git", "init", "-q", "-b", "main", self.vilma], check=True)
        pathlib.Path(self.vilma, "AGENTS.md").write_text("Kimenő levelet nem küldesz.\n")

    def bash(self, cmd, cwd=None, merge=True):
        """Alapból összeolvasztás-módban (a jelző él); merge=False: alap mód."""
        return A.decide("Bash", {"command": cmd}, cwd or self.ops, merge)


class Tilt(Base):
    def test_masik_agens_szabalya_edittel(self):
        self.assertTrue(A.decide("Edit", {"file_path": self.vilma + "/AGENTS.md"}, self.ops))

    def test_sajat_szabaly_szabad(self):
        self.assertIsNone(A.decide("Edit", {"file_path": self.vilma + "/AGENTS.md"}, self.vilma))

    def test_pr_agon_szabad(self):
        subprocess.run(["git", "-C", self.vilma, "checkout", "-q", "-b", "felhatalmazas"], check=True)
        self.assertIsNone(A.decide("Edit", {"file_path": self.vilma + "/AGENTS.md"}, self.ops))

    def test_sed_i_masik_szabalyara(self):
        self.assertTrue(self.bash(f"sed -i 's/nem küldesz/küldhetsz/' {self.vilma}/AGENTS.md"))

    def test_systemd_unit_kezzel(self):
        p = self.h + "/.config/systemd/user/vilma-osszefoglalo.timer"
        self.assertTrue(A.decide("Write", {"file_path": p}, self.ops))
        self.assertTrue(self.bash("sed -i 's/^OnCalendar=.*/OnCalendar=08:30/' ~/.config/systemd/user/fleet-tick-vilma.timer"))

    def test_tmux_gepeles(self):
        self.assertTrue(self.bash('tmux send-keys -t vilma -l "szia" && tmux send-keys -t vilma Enter'))

    def test_proba_level_a_fogado_kodjaval(self):
        self.assertTrue(self.bash(f"cd {self.vilma} && ./bin/meeting email-teszt marton@partfal.example"))
        self.assertTrue(self.bash(f'cd {self.vilma} && python3 -c "from vilma import meeting; meeting.send_email([])"'))


class Szabad(Base):
    def test_tesztek_futnak(self):
        self.assertIsNone(self.bash(f"cd {self.vilma} && python3 -m unittest discover -s tests"))

    def test_kod_irasa_a_fogadoban(self):
        self.assertIsNone(A.decide("Write", {"file_path": self.vilma + "/vilma/meeting.py"}, self.ops))

    def test_fleet_ask(self):
        self.assertIsNone(self.bash("fleet ask vilma --file ~/ops/proba-level.md --wait 300"))

    def test_olvasas(self):
        self.assertIsNone(self.bash(f"cat {self.vilma}/AGENTS.md; git -C {self.vilma} log --oneline -3 2>&1"))

    def test_fogado_sajat_kuldese(self):
        self.assertIsNone(self.bash("./bin/meeting email-teszt marton@partfal.example", cwd=self.vilma))

    def test_kereses_a_fogado_kodjaban(self):
        self.assertIsNone(self.bash(f'grep -rn "LEVELKULDO" {self.vilma}/vilma 2>/dev/null | head -20; echo "done"'))

    def test_tobbsoros_git_commit(self):
        subprocess.run(["git", "-C", self.vilma, "checkout", "-q", "-b", "ag2"], check=True)
        cmd = f"cd {self.vilma}\ngit add x.py\ngit -c user.email=m@p.example commit -m 'fix: e-mail összefoglaló küldése'"
        self.assertIsNone(self.bash(cmd))

    def test_heredoc_python_kuldes_tilos(self):
        cmd = f"cd {self.vilma} && python3 - <<'PY'\nfrom vilma import meeting\nmeeting.send_email([])\nPY"
        self.assertTrue(self.bash(cmd))


class Modszer(Base):
    def setUp(self):
        super().setUp()
        import agens_hatar_mod as Mo
        self.Mo = Mo
        self.reg = os.path.join(self.h, "flotta-registry")
        os.makedirs(self.reg)

    def mod(self, tool, inp, cwd=None, merge=True):
        return self.Mo.decide(tool, inp, cwd or self.ops, merge)

    def test_merge_a_fogado_fo_agara(self):
        self.assertTrue(self.mod("Bash", {"command": f"git -C {self.vilma} merge --ff-only merge/szervezo-vilma"}))
        self.assertTrue(self.mod("Bash", {"command": f"cd {self.vilma} && git commit -am x"}))

    def test_git_config_a_fogadoban(self):
        self.assertTrue(self.mod("Bash", {"command": f"git -C {self.vilma} config user.email a@b"}))
        self.assertTrue(self.mod("Edit", {"file_path": self.vilma + "/.git/config"}))

    def test_agon_szabad(self):
        self.assertIsNone(self.mod("Bash", {"command": f"git -C {self.vilma} checkout -b felhatalmazas"}))
        subprocess.run(["git", "-C", self.vilma, "checkout", "-q", "-b", "felhatalmazas"], check=True)
        self.assertIsNone(self.mod("Bash", {"command": f"cd {self.vilma} && git commit -am x"}))

    def test_registry_kezzel(self):
        os.makedirs(self.h + "/.config/fleet")
        pathlib.Path(self.h, ".config/fleet/registry").write_text(self.reg + "\n")
        self.assertTrue(self.mod("Write", {"file_path": self.reg + "/agents.json"}))
        cmd = "python3 - <<'PY'\nimport json\nd=json.load(open('%s/agents.json'))\njson.dump(d, open('%s/agents.json','w'))\nPY" % (self.reg, self.reg)
        self.assertTrue(self.mod("Bash", {"command": cmd}))
        self.assertIsNone(self.mod("Bash", {"command": "cat %s/agents.json" % self.reg}))

    def test_kapu_kodja_olvashato(self):
        """CISO Q6: nyilvános kiadás után a kód-olvasás tiltása csak rejtegetés; az írása védett marad."""
        p = self.h + "/fleet-ops/security/eszkozok/identitas/agens_hatar.py"
        self.assertIsNone(self.mod("Read", {"file_path": p}))
        self.assertIsNone(self.mod("Bash", {"command": "grep -n OUTWARD " + p}))

    def test_git_email_nem_kuldes(self):
        subprocess.run(["git", "-C", self.vilma, "checkout", "-q", "-b", "ag"], check=True)
        self.assertIsNone(self.bash(f"cd {self.vilma} && git -c user.email=dev@box commit -am x"))


if __name__ == "__main__":
    unittest.main()
