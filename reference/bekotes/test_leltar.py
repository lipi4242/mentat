import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent


def run(*args, env=None):
    return subprocess.run([sys.executable, str(HERE / "bekotes.py"), *args],
                          capture_output=True, text=True, env=env)


def git(repo, *a):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.com",
                    *a], check=True, capture_output=True)


class LeltarFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        web = self.root / "web"
        (web / "node_modules").mkdir(parents=True)
        (web / "node_modules" / "x.js").write_text("x")
        (web / ".release-agent").mkdir()
        (web / ".release-agent" / "config.json").write_text("{}")
        (web / "big.txt").write_text("a" * (300 * 1024))
        (web / "a.py").write_text("print(1)\n")
        git(web, "init", "-q")
        git(web, "add", "-A")
        git(web, "commit", "-q", "-m", "first mail me at bob@example.com")
        (web / "b.py").write_text("2\n")
        git(web, "add", "-A")
        git(web, "commit", "-q", "-m", "second")
        mem = self.root / "mem"
        mem.mkdir()
        (mem / "a.md").write_text("---\nname: a\ndescription: Alpha note\n---\nbody\n")
        (mem / "b.md").write_text("---\ndescription: Beta\n---\nbody\n")
        (self.root / "lin.json").write_text(json.dumps({
            "exported_at": "2026-01-02T00:00:00Z", "complete": True,
            "issues": [{"id": "1", "identifier": "ZOL-1", "title": "Mail x@example.com",
                        "state": "Todo", "updatedAt": "2026-01-01T00:00:00Z"},
                       {"id": "2", "identifier": "ZOL-2", "title": "t2",
                        "state": "Done", "updatedAt": "2026-01-03T00:00:00Z"}]}))
        self.cfg = self.root / "bekotes.json"
        self.cfg.write_text(json.dumps({"schema": 1, "business": "zoldag", "sources": [
            {"name": "web", "kind": "repo", "path": "web"},
            {"name": "memoria", "kind": "memory", "path": "mem"},
            {"name": "linear", "kind": "linear", "export": "lin.json", "team": "ZOL"},
            {"name": "elo", "kind": "live", "path": "missing.txt"},
            {"name": "levelezes", "kind": "mail", "state": "tiltott", "reason": "csak kérésre"}]}))
        self.out = self.root / "leltar.json"

    def go(self):
        return run("leltar", "--config", str(self.cfg), "--repo", str(self.root),
                   "--out", str(self.out))


class LeltarTest(LeltarFixture):
    def test_leltar_states_and_exclusions(self):
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(self.out.read_text())
        st = {s["name"]: s["state"] for s in d["sources"]}
        self.assertEqual(st, {"web": "elérhető", "memoria": "elérhető", "linear": "elérhető",
                              "elo": "blokkolt", "levelezes": "tiltott"})
        web = next(s for s in d["sources"] if s["name"] == "web")
        paths = [f["path"] for f in web["files"]]
        self.assertNotIn("node_modules/x.js", paths)
        self.assertEqual(next(f for f in web["files"] if f["path"] == "big.txt")["skipped"],
                         "meret")
        self.assertTrue(web["release_agent"])
        self.assertFalse(d["kiado_alapnak"])
        self.assertIn(".release-agent/config.json", web["configs"])
        self.assertEqual(len(web["commits"]), 2)
        self.assertNotIn("bob@example.com", json.dumps(web["commits"]))
        self.assertFalse(web["dirty"])
        self.assertEqual([h["name"] for h in d["hianylista"]], ["elo", "levelezes"])
        lin = next(s for s in d["sources"] if s["name"] == "linear")
        self.assertEqual(lin["max_updated_at"], "2026-01-03T00:00:00Z")
        self.assertNotIn("x@example.com", json.dumps(lin))
        mem = next(s for s in d["sources"] if s["name"] == "memoria")
        self.assertEqual(mem["files"][0]["description"], "Alpha note")

    def test_deterministic(self):
        self.assertEqual(self.go().returncode, 0)
        first = self.out.read_bytes()
        self.go()
        self.assertEqual(first, self.out.read_bytes())

    def test_dotdot_rejected(self):
        c = json.loads(self.cfg.read_text())
        c["sources"][3]["path"] = "../x"
        self.cfg.write_text(json.dumps(c))
        r = self.go()  # contract since the friction round: '..' fails the command, it is not a gap
        self.assertEqual(r.returncode, 1)
        self.assertIn("elo.path", r.stderr)
        self.assertFalse(self.out.exists())

    def test_dirty_flag(self):
        (self.root / "web" / "a.py").write_text("changed\n")
        self.go()
        d = json.loads(self.out.read_text())
        self.assertTrue(next(s for s in d["sources"] if s["name"] == "web")["dirty"])


if __name__ == "__main__":
    unittest.main()
