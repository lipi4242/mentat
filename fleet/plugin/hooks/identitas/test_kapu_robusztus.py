"""F-41 kapu: az elemző nem omlik össze, és ha mégis, soha nem enged át.

Élesben (2026-10-24, Mac): teljesen helyi parancsokon „identitás-kapu hiba (error)” lett a
döntés, és az onFailure: block miatt tiltás. Az ok: egy `sed -i` szkriptje (`s#…#…#`) és egy kódbeli
szöveg glob-mintaként került az fnmatch-be, és egy fordított tartomány (`[z-a]`) re.error-t dobott.
A 2026-10-24-i helyi korpuszon (53 920 egyedi Bash-parancs) 179 omlott össze; a javítás után 0.

A szabály: az elemző kivétele interaktívan kérdés (a szöveg kimondja, hogy a kapu nem tudta
elemezni), headless módban tiltás, és napló (a parancs szövege nélkül). Valódi kapu-hiba (hiányzó
modul, olvashatatlan konfig) továbbra is tiltás. Opcionális éles korpusz:
MENTAT_ID_KORPUSZ='~/.claude*/projects' (csak darabszámot ír ki, parancsot nem).
"""
import contextlib
import glob
import io
import json
import os
import pathlib
import random
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kapu  # noqa: E402
import tarolo  # noqa: E402
import vedett  # noqa: E402
from test_kapu import ALLOW, IDS  # noqa: E402

HOLDOUT2 = [  # a négy élesben elakadt alak, kitalált értékekkel
    "cd /tmp/repo; cat > bin/sz <<'EOF'\ngpg --batch --passphrase-file \"$key\" -d x.gpg\nEOF\npython3 - <<'EOF'\n"
    "p='bin/sz2'; t=open(p).read(); t=t.replace('a','b'); open(p,'w').write(t)\nEOF\n"
    "cat bin/sz2; bash -n bin/sz2 && bash -n bin/sz",
    "cd /tmp/repo; python3 - <<'EOF'\nt=open('x').read().replace('[z-a]','b')\nEOF\necho \"a b\" >> insight/allow.txt; "
    "python3 -m unittest discover -s tests; S=/tmp/s; sed -i '' 's#[z-a]*#/Users/user/code/repo/docs#' $S/dev/p.py; "
    "python3 $S/dev/p.py; python3 - <<EOF\nimport json\nprint(json.loads(open('/tmp/a.jsonl').readline()))\nEOF",
    "S=/tmp/s; cd $S/dev; sed -i '' \"s#[z-a]#/Users/user/code/repo/docs#\" p.py; grep -c \"repo/docs\" p.py; python3 p.py",
    "S=/tmp/s; cd $S/dev && python3 -c \"p='p.py'; t=open(p).read(); t=t.replace('[z-a]', "
    "'pathlib.Path.home()/\\\"code\\\"'); open(p,'w').write(t)\" && grep -c 'home()' p.py && python3 p.py",
]
BASE = HOLDOUT2 + [
    "rm ~/x[z-a]*", "ls ~/.mentat/*[", "find ~ -name '[z-a]' -print", "cp a[z-a] ~/.mentat/",
    "git commit -m \"[z-a] ~/.mentat/identitas.txt\"", "ssh h 'echo [z-a] > ~/.mentat/identitas.txt'",
    "python3 -c \"open('/tmp/[z-a]','w').write('x')\"", "echo $(cat ~/.mentat/elsofel.txt) | tr a b",
    "for f in ~/.mentat/*; do echo \"$f\"; done", "cat <<-EOF\n\tx > ~/.mentat/identitas.txt\n\tEOF",
    "bash -c 'sed -i \"s/[z-a]//\" ~/notes.md'", "curl -s https://api.example.org/x?m=teszt.elek@csalad.example",
]
NOISE = ["[z-a]", "\"", "'", "\\", "<<EOF\n", "\nEOF\n", "$(", "`", "{", "}", "*", "?", "~", " -i ", " > ", " | ",
         ";", "\n", "é", "&&", "#", "[", "]", "${HOME}", " -exec rm {} \\; ", " -delete "]


def analyse(cmd):
    vedett.protected_write("Bash", {"command": cmd}, tempfile.gettempdir())
    kapu.decide("Bash", {"command": cmd}, tempfile.gettempdir(), IDS, ALLOW)


class NemOmlikOssze(unittest.TestCase):
    def test_a_holdout2_alakok_helyiek_es_atmennek(self):
        for cmd in HOLDOUT2:
            self.assertIsNone(vedett.protected_write("Bash", {"command": cmd}, "/tmp"), cmd[:40])
            analyse(cmd)

    def test_fuzz_a_mintakon(self):
        rnd = random.Random(20261024)
        for base in BASE:
            analyse(base)
            for _ in range(80):
                cmd = base
                for _ in range(rnd.randint(1, 4)):
                    i = rnd.randint(0, len(cmd))
                    cmd = cmd[:i] + rnd.choice(NOISE) + cmd[i:]
                analyse(cmd)  # any exception fails the test

    @unittest.skipUnless(os.environ.get("MENTAT_ID_KORPUSZ"), "MENTAT_ID_KORPUSZ nincs megadva")
    def test_eles_korpusz(self):
        files = [f for root in glob.glob(os.path.expanduser(os.environ["MENTAT_ID_KORPUSZ"]))
                 for f in glob.glob(root + "/**/*.jsonl", recursive=True)]
        seen, bad = set(), 0
        for f in files:
            for line in open(f, errors="replace"):
                if '"Bash"' not in line:
                    continue
                try:
                    content = (json.loads(line).get("message") or {}).get("content") or []
                except (ValueError, AttributeError):
                    continue
                for c in content if isinstance(content, list) else []:
                    cmd = str((c.get("input") or {}).get("command", "")) if isinstance(c, dict) and c.get("name") == "Bash" else None
                    if cmd is None or cmd in seen:
                        continue
                    seen.add(cmd)
                    try:
                        analyse(cmd)
                    except Exception:  # noqa: BLE001
                        bad += 1
        print("korpusz: %d egyedi parancs, %d kivétel" % (len(seen), bad), file=sys.stderr)
        self.assertEqual(bad, 0)


class HaMegisOsszeomlik(unittest.TestCase):
    def setUp(self):
        self.log = os.path.join(tempfile.mkdtemp(), "hibak.jsonl")
        self.p = mock.patch.object(tarolo, "ERRLOG", self.log)
        self.p.start()
        self.addCleanup(self.p.stop)

    def call(self, mode):
        return kapu.hook({"tool_name": "Bash", "tool_input": {"command": "echo titkos-parancs"},
                          "cwd": tempfile.gettempdir(), "permission_mode": mode}, IDS, ALLOW)

    def test_elemzo_kivetel_kerdes_vagy_tiltas_soha_atengedes(self):
        for target in ((tarolo, "touches_protected"), (kapu, "decide")):
            with mock.patch.object(*target, side_effect=re.error("bad character range z-a")):
                ask, deny = self.call("default"), self.call("bypassPermissions")
            self.assertEqual(ask["hookSpecificOutput"]["permissionDecision"], "ask", target)
            self.assertIn("nem tudta elemezni", ask["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertEqual(deny["hookSpecificOutput"]["permissionDecision"], "deny", target)
        with open(self.log) as f:
            log = f.read()
        self.assertEqual(len(log.splitlines()), 4)
        self.assertIn('"type": "%s"' % type(re.error("x")).__name__, log)  # error (3.9), PatternError (3.13+)
        self.assertNotIn("titkos-parancs", log)  # only a hash of the call

    def test_valodi_kapu_hiba_tovabbra_is_tilt(self):
        out = io.StringIO()
        with mock.patch.object(tarolo, "load", side_effect=OSError("olvashatatlan cache")), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "cwd": "/tmp",
                                                                        "tool_input": {"command": "curl https://x.example"}}))), \
                contextlib.redirect_stdout(out):
            kapu.main(["--hook"])
        d = json.loads(out.getvalue())["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("identitás-kapu hiba", d["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
