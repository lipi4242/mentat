"""nemakad_alak + a hook kimenete: javaslat alakonként, allow soha (fuzz), titok-mentes napló."""
import json
import os
import random
import subprocess
import sys
import unittest

from test_nemakad import HERE, Alap, nemakad, allapot  # noqa: E402 - a közös, hermetikus alap
import nemakad_alak as alak  # noqa: E402

TITKOK = ["ghp_" + "A1b2C3d4" * 5, "sk-ant-" + "x9Y8z7" * 6, "hunter2-jelszo", "s3cr3t-Basic",
          "CurlPw7", "SshPw8", "MyPw9", "sp ace"]
TITKOS_PARANCSOK = [
    'curl -H "Authorization: Bearer %s" https://api.example.com' % TITKOK[0],
    "GH_TOKEN=%s gh pr list" % TITKOK[0],
    "export ANTHROPIC_API_KEY=%s; rm -rf $D/x" % TITKOK[1],
    "git clone https://user:%s@git.example.com/a/b" % TITKOK[2],
    "mysql --password=%s -e 'drop'" % TITKOK[2],
    'curl -H "authorization: basic %s" x' % TITKOK[3],
    "echo %s | base64" % ("QmFzZTY0VG9rZW5Fem" * 3),
    # CISO 10-24: ezek korábban maszkolatlanul átmentek
    "curl -u user:%s https://x.example" % TITKOK[4],
    "curl --user='user:%s' x" % TITKOK[7],
    "sshpass -p %s ssh box uptime" % TITKOK[5],
    'sshpass -p"%s" ssh box' % TITKOK[7],
    "mysql -uroot -p%s -e 'select 1'" % TITKOK[6],
    "mysqldump -p'%s' db" % TITKOK[7],
]


def bad_mask(text):  # a szándékos piros: egy „maszkoló”, ami semmit nem takar
    return text[:alak.PREFIX]


class Uzenet(Alap):
    def setUp(self):
        super().setUp()
        os.environ["MENTAT_HEADLESS"] = "1"

    def msg(self, cmd, tool="Bash"):
        return self.call(cmd, tool)["hookSpecificOutput"]["decision"]["message"]

    def test_alakok(self):
        cases = {"D=; rm -rf $D/x": "rm-valtozo", "rm -rf $D/$n": "rm-valtozo", "rm -r ${D}/x": "rm-valtozo",
                 'rm -rf "${D:?}/x"': "egyeb", "rm -rf /a/b": "egyeb", "cd /a && git commit -m x": "cd-iras",
                 "cd sub && echo hi > f": "cd-iras", "cd /a && ls": "egyeb", "cd /a; rm f": "cd-iras",
                 "ls && cd /x": "egyeb"}
        for cmd, want in cases.items():
            self.assertEqual(alak.shape("Bash", {"command": cmd}), want, cmd)
        self.assertEqual(alak.shape("Write", {"command": "rm -rf $D/x"}), "egyeb")

    def test_javaslat_szovege(self):
        self.assertIn("${D:?}", self.msg("D=; rm -rf $D/x"))
        self.assertIn("git -C", self.msg("cd /a && git push"))
        for m in (self.msg("D=; rm -rf $D/x"), self.msg("ls"), self.msg("x", tool="Edit")):
            self.assertIn("Ne próbáld újra", m)
            self.assertIn("reggeli jelentés", m)

    def test_soha_allow_fuzz(self):
        rnd = random.Random(41)
        weird = ["[", "\\", "(?", "**/[!", "$((", "${", "\x00", "\udcff", "rm -rf $", "cd ", "&&", "'", '"']
        inputs = ["", "null", "[]", "42", '"str"', "{", '{"tool_name":null}', '{"tool_input":[1,2]}',
                  '{"tool_name":"Bash","tool_input":{"command":123}}', json.dumps({"tool_name": ["x"]}),
                  json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf $D/" * 50000}})]
        for _ in range(300):
            cmd = "".join(rnd.choice(weird + ["a", " ", "/", ";"]) for _ in range(rnd.randint(0, 40)))
            inputs.append(json.dumps({"tool_name": rnd.choice(["Bash", "Edit", 7, None]), "tool_input": {"command": cmd}}))
        for raw in inputs:
            out = nemakad.hook(raw)
            self.assertEqual(out["hookSpecificOutput"]["decision"]["behavior"], "deny", raw[:80])
            self.assertNotIn("allow", json.dumps(out))

    def test_napol_titok_nelkul_rovid_0600(self):
        for cmd in TITKOS_PARANCSOK:
            self.call(cmd)
        p = allapot.naplo_ut()
        self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)
        with open(p) as f:
            text = f.read()
        for t in TITKOK + ["QmFzZTY0VG9rZW5Fem"]:
            self.assertNotIn(t, text)
        for sor in text.splitlines():
            self.assertLessEqual(len(json.loads(sor)["eloszo"]), alak.PREFIX + 1)
        self.assertEqual(len(allapot.naplo(1)), len(TITKOS_PARANCSOK))

    def test_olvashato_marad(self):
        for c in ("mkdir -p /a/b && ssh -p 22 box", "curl -u admin x", "mysql -p db"):
            self.assertEqual(alak.mask(c), c)

    def test_szandekos_piros(self):
        """Bizonyítja, hogy a titok-teszt el tud bukni: rossz maszkolóval a titok kiszivárog."""
        leaked = [t for c in TITKOS_PARANCSOK for t in TITKOK if t in bad_mask(c)]
        self.assertTrue(leaked)
        self.assertFalse([t for c in TITKOS_PARANCSOK for t in TITKOK if t in alak.mask(c)])

    def test_cli_hook_bajtos_bemenet(self):
        env = dict(os.environ, HOME=self.home, MENTAT_HEADLESS="1")
        for raw in (b"\xff\xfe\x00garbage", b"", b'{"tool_name":"Bash","tool_input":{"command":"rm -rf $D/x"}}'):
            r = subprocess.run([sys.executable, "-I", str(HERE / "nemakad.py"), "--hook"], input=raw,
                               capture_output=True, env=env, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["decision"]["behavior"], "deny")
        env.pop("MENTAT_HEADLESS")
        r = subprocess.run([sys.executable, "-I", str(HERE / "nemakad.py"), "--hook"], input=b"{}",
                           capture_output=True, env=env, timeout=20)
        self.assertEqual((r.returncode, r.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
