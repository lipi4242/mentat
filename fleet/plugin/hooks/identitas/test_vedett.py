"""F-41 kapu, védett fájlok: csak a kapu saját fájljainak ÍRÁSA akad meg (a Macen talált hamis tiltások).

Élesben a régi szabály minden olyan Bash-hívást megfogott, amiben a `.mentat/bin` és egy
`python3` szerepelt: egy repón belüli eszköz futtatását, egy `ssh host '…'` távoli parancsot, egy
commit-üzenetet, és a repó saját `.claude/settings.json`-ját is kérdezte. Mostantól csak a feloldott
abszolút védett utak írása számít. Minden teszt ideiglenes HOME alatt fut.
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vedett  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.old = {k: os.environ.get(k) for k in ("HOME", "CLAUDE_CONFIG_DIR")}
        self.home = os.path.realpath(tempfile.mkdtemp())
        os.environ["HOME"] = self.home
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.repo = os.path.join(self.home, "code", "repo")
        os.makedirs(os.path.join(self.repo, ".mentat", "bin"))

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def w(self, tool, **inp):
        return vedett.protected_write(tool, inp, self.repo)


class Atmegy(Base):
    def test_repon_beluli_mentat_bin_futtatasa(self):
        for cmd in ("python3 -I .mentat/bin/mentat_brain.py due",
                    "cd %s && python3 .mentat/bin/mentat_web.py check https://x.example" % self.repo,
                    "python3 -I ~/.mentat/bin/identitas-kapu/current/kapu.py --hook < /dev/null"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_ssh_belso_parancsa_tavoli(self):
        for cmd in ("ssh host 'cd repo && python3 -I .mentat/bin/x.py'",
                    "ssh box 'rm -rf ~/.mentat/bin/identitas-kapu; echo x > ~/.mentat/identitas.txt'"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_commit_uzenet_es_heredoc_szoveg(self):
        for cmd in ('git commit -m "fix: a ~/.mentat/identitas.txt írása > tiltott"',
                    "git commit -q -F - <<'EOF'\nrm -rf ~/.mentat/bin/identitas-kapu\nEOF",
                    "cat <<EOF\necho x > ~/.mentat/elsofel.txt\nEOF"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_vedett_fajl_olvasasa(self):
        p = os.path.join(self.home, ".mentat", "identitas.txt")
        self.assertIsNone(self.w("Read", file_path=p))
        for cmd in ("cat ~/.mentat/identitas.txt", "grep -c @ $HOME/.mentat/elsofel.txt | head",
                    "python3 -c \"print(open('%s').read())\"" % p):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_a_repo_sajat_beallitasa_es_mentat_bin_irasa(self):
        self.assertIsNone(self.w("Write", file_path=os.path.join(self.repo, ".claude", "settings.json")))
        self.assertIsNone(self.w("Write", file_path=".mentat/bin/uj.py"))
        self.assertIsNone(self.w("Bash", command="echo {} > .claude/settings.json"))


class Tilt(Base):
    def test_identitas_txt_irasa_write_eszkozzel_es_atiranyitassal(self):
        p = os.path.join(self.home, ".mentat", "identitas.txt")
        self.assertEqual(self.w("Write", file_path="~/.mentat/identitas.txt"), p)
        for cmd in ("echo x > ~/.mentat/identitas.txt", "echo x >> $HOME/.mentat/identitas.txt",
                    "printf x | tee -a ${HOME}/.mentat/identitas.txt", "cp /tmp/x ~/.mentat/identitas.txt",
                    "sed -i '' 's/a/b/' ~/.mentat/identitas.txt"):
            self.assertEqual(self.w("Bash", command=cmd), p, cmd)

    def test_a_kapu_kodjanak_torlese(self):
        for cmd in ("rm -rf ~/.mentat/bin/identitas-kapu", "rm -rf ~/.mentat", "mv ~/.mentat/bin /tmp/x",
                    "bash -c 'rm -rf ~/.mentat/bin/identitas-kapu/current'", "rm ~/.mentat/*.txt"):
            self.assertTrue(self.w("Bash", command=cmd), cmd)

    def test_interpreter_kodban_iras(self):
        cache = os.path.join(self.home, ".mentat", "identitas-cache.json")
        for cmd in ("python3 -c \"open('%s','w').write('{}')\"" % cache,
                    "python3 - <<'X'\nimport os\nos.remove(os.path.expanduser('~/.mentat/identitas-cache.json'))\nX"):
            self.assertTrue(self.w("Bash", command=cmd), cmd)

    def test_felhasznaloi_claude_beallitas_kerdez(self):
        for p in ("~/.claude/settings.json", "~/.claude-personal/settings.local.json"):
            self.assertTrue(str(self.w("Edit", file_path=p)).startswith("beallitas:"), p)
        cfg = tempfile.mkdtemp()
        os.environ["CLAUDE_CONFIG_DIR"] = cfg
        self.assertTrue(str(self.w("Bash", command="echo {} > %s/settings.json" % cfg)).startswith("beallitas:"))


class SajatMappa(Base):
    """A kapu kódja ott védett, ahonnan valóban fut; egy ugyanilyen nevű másik mappa szabad."""

    def test_a_futo_kod_mappaja_vedett_a_masolat_nem(self):
        import vedett_ut
        own = os.path.join(vedett_ut.OWN, "kapu.py")
        self.assertEqual(self.w("Write", file_path=own), own)
        self.assertTrue(self.w("Bash", command="echo x >> '%s'" % own))
        self.assertIsNone(self.w("Bash", command="python3 -I '%s' --hook < /dev/null" % own))  # futtatás
        self.assertIsNone(self.w("Read", file_path=own))
        other = os.path.join(self.repo, "plugin", "hooks", "identitas", "kapu.py")
        self.assertIsNone(self.w("Write", file_path=other))
        self.assertIsNone(self.w("Bash", command="sed -i '' s/a/b/ plugin/hooks/identitas/kapu.py"))


class DuplaKapu(Base):
    """A plugin-példány csak akkor lép hátrébb, ha a felhasználói kapu ténylegesen fut; a felhasználói soha."""

    def hook_out(self, *flags):
        import json
        import subprocess
        call = {"tool_name": "Write", "tool_input": {"file_path": "~/.mentat/identitas.txt"}, "cwd": self.repo}
        r = subprocess.run([sys.executable, "-I", str(pathlib.Path(__file__).with_name("kapu.py")), "--hook", *flags],
                           input=json.dumps(call), capture_output=True, text=True, env=dict(os.environ))
        return r.stdout.strip()

    def test_plugin_peldany_atadja_a_felhasznaloi_kapunak(self):
        import json
        conf = os.path.join(self.home, ".claude")
        code = os.path.join(self.home, ".mentat", "bin", "identitas-kapu", "current")
        os.makedirs(conf)
        os.makedirs(code)
        open(os.path.join(code, "kapu.py"), "w").close()
        self.assertIn("deny", self.hook_out("--instance", "plugin"))  # nincs felhasználói kapu: a plugin véd
        with open(os.path.join(conf, "settings.json"), "w") as f:
            json.dump({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "onFailure": "block",
                       "command": "/usr/bin/python3 -I %s/kapu.py --hook" % code}]}]}}, f)
        self.assertEqual(self.hook_out("--instance", "plugin"), "")      # a felhasználói kapu dönt
        self.assertIn("deny", self.hook_out())                            # a felhasználói példány soha nem lép hátrébb


if __name__ == "__main__":
    unittest.main()
