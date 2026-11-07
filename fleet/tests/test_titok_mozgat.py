"""`fleet secrets approve|move|copy|audit`: tételes, lejáró, egyszer használható jóváhagyás; az érték
nem kerül argv-be, kimenetbe, hibaüzenetbe; nyugta hash8-cal; audit fájl:sorral, érték nélkül."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import json
from unittest import mock
import os
import shutil
import subprocess
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

from fleet import cli, titok_audit as A, titok_jovahagy as J, titok_leltar as L, titok_mozgat as M
from test_titok_leltar import FAKE, make_box


class Base(unittest.TestCase):
    def setUp(self):
        self.home = make_box()
        self.addCleanup(shutil.rmtree, self.home, True)
        L.save(L.scan(["szervezo", "vilma"], home=self.home, repos={"szervezo": self.home / "szervezo"}), self.home)

    def approve(self, *items, ttl=60, now=None):
        return J.create([J.parse_item(i) for i in items], "Igen, a SZ_TOKEN mehet Vilmához.", ttl, home=self.home,
                        now=now)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        old = os.environ["HOME"]
        os.environ["HOME"] = str(self.home)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                rc = cli.main(list(argv))
        finally:
            os.environ["HOME"] = old
        return rc, out.getvalue() + err.getvalue()


class Move(Base):
    def test_copy_ertek_nelkuli_kimenettel_es_nyugtaval(self):
        aid = self.approve("copy:SZ_TOKEN:szervezo:vilma:a fogadó küld")
        rc, text = self.run_cli("secrets", "copy", "--name", "SZ_TOKEN", "--from", "szervezo", "--to", "vilma",
                                "--approval", aid)
        self.assertEqual(rc, 0, text)
        self.assertNotIn(FAKE, text)
        dest = self.home / ".config/vilma/vilma.env"
        self.assertEqual(dest.read_text(), f"SZ_TOKEN={FAKE}\n")
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        self.assertFalse(dest.is_symlink())
        rec = json.loads((self.home / ".mentat/titkok/nyugtak.jsonl").read_text().splitlines()[-1])
        self.assertEqual((rec["name"], rec["approval"], len(rec["hash8"])), ("SZ_TOKEN", aid, 8))
        self.assertNotIn(FAKE, json.dumps(rec))
        self.assertIn(f"SZ_TOKEN={FAKE}", (self.home / ".config/szervezo/szervezo.env").read_text())  # copy

    def test_egyszer_hasznalhato(self):
        aid = self.approve("copy:SZ_TOKEN:szervezo:vilma:x")
        M.run("copy", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)
        with self.assertRaises(J.Refused):
            M.run("copy", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)

    def test_move_nem_dormant_donorbol_elutasit_a_forras_marad(self):
        # H5 (2026-10-29): a move elvitte a még visszaállítható donor kulcsait.
        aid = self.approve("move:SZ_TOKEN:szervezo:vilma:x")
        with mock.patch("fleet.registry.get_agent", return_value={"agent": "szervezo", "status": "active"}):
            with self.assertRaises(J.Refused) as cm:
                M.run("move", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)
        self.assertIn("copy", str(cm.exception))
        self.assertIn(f"SZ_TOKEN={FAKE}", (self.home / ".config/szervezo/szervezo.env").read_text())
        self.assertFalse((self.home / ".config/vilma/vilma.env").exists())

    def test_move_ismeretlen_registry_elutasit(self):
        aid = self.approve("move:SZ_TOKEN:szervezo:vilma:x")
        with mock.patch("fleet.registry.get_agent", side_effect=RuntimeError("nincs registry")):
            with self.assertRaises(J.Refused):
                M.run("move", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)

    def test_move_kiveszi_a_forrasbol_a_tobbi_sor_marad(self):
        aid = self.approve("move:SZ_TOKEN:szervezo:vilma:x")
        with mock.patch("fleet.registry.get_agent", return_value={"agent": "szervezo", "status": "dormant"}):
            M.run("move", "SZ_TOKEN", "szervezo", "vilma", aid, self.home)
        src = (self.home / ".config/szervezo/szervezo.env").read_text()
        self.assertNotIn("SZ_TOKEN", src)
        self.assertIn("CHAT_ID", src)

    def test_elutasitasok(self):
        aid = self.approve("copy:SZ_TOKEN:szervezo:vilma:x")
        old = self.approve("copy:SZ_TOKEN:szervezo:vilma:x", ttl=1, now=time.time() - 3600)
        for args in (("copy", "CHAT_ID", "szervezo", "vilma", aid),       # nincs a tételek közt
                     ("move", "SZ_TOKEN", "szervezo", "vilma", aid),      # más művelet
                     ("copy", "SZ_TOKEN", "szervezo", "vilma", "nincs-ilyen"),
                     ("copy", "SZ_TOKEN", "szervezo", "vilma", old)):     # lejárt
            with self.assertRaises(J.Refused) as cm:
                M.run(*args, home=self.home)
            self.assertNotIn(FAKE, str(cm.exception))
        self.assertFalse((self.home / ".config/vilma/vilma.env").exists())

    def test_jovahagyas_kotelezo_mezoi(self):
        for items, text, ttl in (([], "igen", 60), ([J.parse_item("copy:A:b:c:d")], " ", 60),
                                 ([J.parse_item("copy:A:b:c:d")], "igen", 61)):
            with self.assertRaises(J.Refused):
                J.create(items, text, ttl, home=self.home)
        with self.assertRaises(J.Refused):
            J.parse_item("delete:A:b:c:d")

    def test_symlink_celre_nem_ir(self):
        link = str(self.home / "link.env")
        (self.home / "link.env").symlink_to(self.home / "szervezo/README.md")
        aid = self.approve(f"copy:SZ_TOKEN:szervezo:{link}:x")
        with self.assertRaises(J.Refused):
            M.run("copy", "SZ_TOKEN", "szervezo", link, aid, self.home)
        self.assertEqual((self.home / "szervezo/README.md").read_text(), "nem titok\n")


class Audit(Base):
    def test_lelet_fajl_sorral_ertek_nelkul(self):
        t = self.home / ".claude-vilma/projects/p"
        t.mkdir(parents=True)
        (t / "s.jsonl").write_text('{"a":1}\n{"tool_result":"SZ_TOKEN=%s"}\n' % FAKE)
        repo = self.home / "vilma-repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "config.py").write_text("T = '%s'\n" % FAKE)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t.invalid", "-c", "user.name=t", "commit",
                        "-qm", "x"], check=True)
        res = A.audit([repo], self.home)
        hol = [x["hol"] for x in res["leletek"]]
        self.assertTrue(any(h.endswith("s.jsonl:2") for h in hol), hol)
        self.assertTrue(any(h.endswith("config.py:1") for h in hol), hol)
        self.assertTrue(any("@git:" in h for h in hol), hol)
        self.assertNotIn(FAKE, json.dumps(res) + A.report(res))


if __name__ == "__main__":
    unittest.main()
