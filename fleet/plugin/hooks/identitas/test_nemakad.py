"""nemakad: felügyelet nélkül deny + javaslat, felügyelettel csend; allow soha; a napló titok-mentes.

Sima unittest (pytest alatt is fut); pytest-import nincs, mert a kapu-Python csupasz.
"""
import contextlib
import datetime
import io
import json
import os
import pathlib
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nemakad  # noqa: E402
import nemakad_allapot as allapot  # noqa: E402


class Alap(unittest.TestCase):
    def setUp(self):
        self.old_env = dict(os.environ)
        self.home = tempfile.mkdtemp()
        os.environ["HOME"] = self.home
        for k in allapot.ENV_JELEK:
            os.environ.pop(k, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def flag(self, text):
        os.makedirs(os.path.join(self.home, ".mentat"), exist_ok=True)
        with open(allapot.jelzo(), "w") as f:
            f.write(text)

    def call(self, cmd, tool="Bash"):
        return nemakad.hook(json.dumps({"tool_name": tool, "tool_input": {"command": cmd}, "cwd": "/tmp"}))


class Mod(Alap):
    def test_felugyelettel_csend(self):
        self.assertIsNone(self.call("D=; rm -rf $D/x"))

    def test_env_jelek(self):
        for k in allapot.ENV_JELEK:
            os.environ[k] = "valaki"
            self.assertEqual(self.call("ls")["hookSpecificOutput"]["decision"]["behavior"], "deny", k)
            del os.environ[k]

    def test_jelzo_el_lejart_hibas(self):
        self.flag("%d\n" % (time.time() + 600))
        self.assertIsNotNone(self.call("ls"))
        self.flag("%d\n" % (time.time() - 1))
        self.assertIsNone(self.call("ls"))
        for garbled in ("", "holnap reggel", "nan", "\x00\xff", "inf"):
            self.flag(garbled)
            self.assertIsNotNone(self.call("ls"), repr(garbled))
        self.flag("-inf")
        self.assertIsNone(self.call("ls"))

    def test_flotta_repo_cwd(self):
        repo = tempfile.mkdtemp()
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": repo})
        self.assertIsNone(nemakad.hook(raw))
        os.makedirs(os.path.join(repo, ".claude"))
        with open(os.path.join(repo, ".claude", "fleet.json"), "w") as f:
            f.write("{}")
        self.assertIsNotNone(nemakad.hook(raw))
        for cwd in (None, 7, ["x"], "\x00", "/" * 9000):
            nemakad.hook(json.dumps({"tool_name": "Bash", "cwd": cwd}))  # nem dob

    def test_olvashatatlan_jelzo_deny(self):
        os.makedirs(allapot.jelzo())  # mappa a fájl helyén
        self.assertIsNotNone(self.call("ls"))

    def test_alszom_ebren(self):
        now = datetime.datetime(2026, 10, 24, 23, 30)
        self.assertEqual(allapot.alszom("08:00", now), datetime.datetime(2026, 10, 25, 8, 0))
        self.assertTrue(allapot.mod(now.timestamp())[0])
        self.assertFalse(allapot.mod(now.timestamp() + 10 * 3600)[0])  # 10-25 óraátállítás: 9,5 óra
        self.assertEqual(allapot.alszom("23:45", now), datetime.datetime(2026, 10, 24, 23, 45))
        with contextlib.redirect_stdout(io.StringIO()):
            nemakad.main(["ebren"])
        self.assertFalse(allapot.mod()[0])


if __name__ == "__main__":
    unittest.main()
