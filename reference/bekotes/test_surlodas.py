"""Path fields never climb above the repo; a named source stays elérhető but is still filtered."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import shutil
import unittest

from _bekotes_repo import BIZ, bk, done, make_agent, write

IP = "10.1." + "2.3"  # built at runtime: the release tree must not carry a real-looking address


class DotDot(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        done(self.root)
        cfg = self.root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"][0]["from"] = "../../../business/remote/x.git"
        d["sources"].append({"name": "kint", "kind": "live", "path": "../kint.txt"})
        cfg.write_text(json.dumps(d, ensure_ascii=False))

    def test_every_command_fails_on_dotdot(self):
        r = bk(self.root, "leltar", "--config", BIZ + "/bekotes.json", "--out", BIZ + "/leltar.json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("..", r.stderr)
        r = bk(self.root, "elokeszit", "--business", "zoldag")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("zoldag-web.from", r.stderr)
        self.assertIn("kint.path", r.stderr)
        out = bk(self.root, "check", "--repo", ".", "--business", "zoldag").stdout
        self.assertIn("FAIL bekotes-json", out)
        self.assertIn("zoldag-web.from", out)


class NamedSourceFiltered(unittest.TestCase):
    def test_named_csv_stays_available_but_is_redacted_when_read(self):
        root = make_agent()
        self.addCleanup(shutil.rmtree, root, True)
        write(root, ".home/bank/befizetesek.csv", "datum;kitol;ip\n2026-10-01;anna@example.com;%s\n" % IP)
        cfg = root / BIZ / "bekotes.json"
        d = json.loads(cfg.read_text())
        d["sources"].append({"name": "bank", "kind": "live", "path": "~/bank/befizetesek.csv"})
        cfg.write_text(json.dumps(d, ensure_ascii=False))
        r = bk(root, "elokeszit", "--business", "zoldag")
        self.assertIn("bank (live): elérhető", r.stdout)
        for out in (bk(root, "olvas", "show", "bank:befizetesek.csv").stdout,
                    bk(root, "olvas", "grep", "2026-10-01", "--source", "bank").stdout):
            self.assertIn("2026-10-01", out)
            self.assertNotIn("anna@example.com", out)
            self.assertNotIn(IP, out)
            self.assertIn("<email>", out)


if __name__ == "__main__":
    unittest.main()
