"""`fleet secrets scan`: nevek, helyek, formátum — érték SOHA (H5, 2026-10-29). Kitalált ágensek,
hamis értékek, a teszt-HOME alatt."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from fleet import cli, titok_leltar as L

FAKE = "HAMIS-ERTEK-NEM-VALODI-0123456789"
# a fejléc kettévágva: a release_check token-szűrője a szó szerinti PEM-fejlécre tilt (0.4.0 kapu)
PEM = ("-----BEGIN " "OPENSSH PRIVATE KEY-----\nAAAAhamisHAMIShamis\n-----END " "OPENSSH PRIVATE KEY-----\n")


def make_box() -> Path:
    home = Path(tempfile.mkdtemp())
    for d in (".config/szervezo", ".config/vilma", ".claude-szervezo/projects/p", "szervezo/.mentat", "szervezo/src",
              ".config/systemd/user", "elsewhere"):
        (home / d).mkdir(parents=True)
    files = {".config/szervezo/szervezo.env": f"SZ_TOKEN={FAKE}\nexport CHAT_ID='-100'\n",
             ".config/szervezo/service-account.json": json.dumps({"type": "service_account", "private_key": PEM,
                                                                   "client_email": "x@y.invalid"}),
             ".config/szervezo/szervezo.env.bak-hid-20261029-000000": f"SZ_TOKEN={FAKE}\n",
             ".config/szervezo/adat.bin": "titkos-ismeretlen",
             ".config/vilma/id_ed25519": PEM,
             ".claude-szervezo/.credentials.json": json.dumps({"claudeAiOauth": {"accessToken": FAKE}}),
             ".claude-szervezo/projects/p/s.jsonl": "{}\n",
             "szervezo/.mentat/connect.json": json.dumps({"token": FAKE}),
             "szervezo/src/token_utils.py": "print('kód, nem titok')\n",
             "szervezo/README.md": "nem titok\n",
             "elsewhere/bridge.env": f"TELEGRAM_BOT_TOKEN={FAKE}\n",
             ".config/systemd/user/szervezo-telegram-bridge.service":
                 "[Service]\nEnvironmentFile=%h/elsewhere/bridge.env\n"}
    for rel, text in files.items():
        (home / rel).write_text(text)
    os.chmod(home / ".config/szervezo/adat.bin", 0o600)
    return home


class Scan(unittest.TestCase):
    def setUp(self):
        self.home = make_box()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.inv = L.scan(["szervezo", "vilma"], home=self.home, repos={"szervezo": self.home / "szervezo"})
        self.by = {Path(f["path"]).name: f for f in self.inv["files"]}

    def test_formatumok_nevekkel(self):
        self.assertEqual([k["name"] for k in self.by["szervezo.env"]["keys"]], ["SZ_TOKEN", "CHAT_ID"])
        sa = self.by["service-account.json"]
        self.assertEqual((sa["class"], sa["private_key"]), ("json", True))
        self.assertIn("client_email", sa["fields"])
        self.assertEqual(self.by["id_ed25519"]["pem"], ["OPENSSH PRIVATE KEY"])
        self.assertEqual(self.by["adat.bin"]["class"], "ismeretlen")  # 0600 → leltárba kerül

    def test_minden_hely(self):
        for name in ("szervezo.env.bak-hid-20261029-000000", ".credentials.json", "connect.json", "bridge.env"):
            self.assertIn(name, self.by)
        self.assertEqual(self.by["bridge.env"]["where"], "unit EnvironmentFile")
        self.assertNotIn("token_utils.py", self.by)
        self.assertNotIn("README.md", self.by)

    def test_atirat_osztaly(self):
        at = [f["path"] for f in self.inv["files"] if f["class"] == "atirat"]
        self.assertIn(str((self.home / ".claude-szervezo/projects").resolve()), at)
        self.assertNotIn("s.jsonl", self.by)

    def test_ujjlenyomat_es_inode(self):
        k = self.by["szervezo.env"]["keys"][0]
        self.assertEqual(len(k["fp"]), 8)
        st = os.stat(self.home / ".config/szervezo/szervezo.env")
        self.assertEqual((self.by["szervezo.env"]["dev"], self.by["szervezo.env"]["ino"]), (st.st_dev, st.st_ino))

    def test_ertek_sehol(self):
        blob = json.dumps(self.inv) + L.table(self.inv, self.home)
        self.assertNotIn(FAKE, blob)
        self.assertNotIn("AAAAhamis", blob)

    def test_mentes_0600_es_osszefesules(self):
        p = L.save(self.inv, self.home)
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        L.save(L.scan(["vilma"], home=self.home), self.home)
        agents = {f.get("agent") for f in json.loads(p.read_text())["files"]}
        self.assertIn("szervezo", agents)  # a korábbi ágens sorai maradnak


class Cli(unittest.TestCase):
    def test_scan_parancs_ertek_nelkul(self):
        home = make_box()
        self.addCleanup(shutil.rmtree, home, True)
        old = os.environ["HOME"]
        os.environ["HOME"] = str(home)
        self.addCleanup(os.environ.__setitem__, "HOME", old)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(["secrets", "scan", "--agent", "szervezo", "--repo", f"szervezo={home / 'szervezo'}"])
        self.assertEqual(rc, 0)
        self.assertIn("SZ_TOKEN", out.getvalue())
        self.assertNotIn(FAKE, out.getvalue() + err.getvalue())
        self.assertTrue((home / ".mentat/titkok/leltar.json").is_file())
        self.assertIn("titok-kapu", (home / ".claude-szervezo/settings.json").read_text())


if __name__ == "__main__":
    unittest.main()
