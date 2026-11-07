"""Shared fixture for the capability tests: a throwaway agent repo + the CLI."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"


def no_fleet_path(path=None):
    """PATH without any folder that holds a `fleet` CLI: a gating box has one (Rilí, #90)."""
    dirs = (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep)
    return os.pathsep.join(d for d in dirs if d and not os.path.exists(os.path.join(d, "fleet")))


class CapsBase(unittest.TestCase):
    lang = "hu"

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.home = tempfile.mkdtemp()
        (self.root / "agy").mkdir()
        self.manifest({"components": {"brain": {"root": "agy"}}})

    def manifest(self, doc):
        base = {"schema": 1, "agent": {"name": "t", "language": self.lang}}
        base.update(doc)
        (self.root / "mentat.json").write_text(json.dumps(base), encoding="utf-8")

    def write(self, rel, text=""):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_where(self, *args):
        env = dict(os.environ, HOME=self.home, PATH=no_fleet_path())
        for k in ("CLOUDFLARE_API_TOKEN", "CLAUDE_CONFIG_DIR", "ANYTIME_REPO_ROOT"):
            env.pop(k, None)  # the machine's own setup never leaks into a test
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), "where", *args],
                              capture_output=True, text=True, env=env)

    def find(self, query):
        r = self.run_where("--find", query, "--json")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return json.loads(r.stdout)

    def top(self, query):
        cands = self.find(query)["candidates"]
        return cands[0]["id"] if cands else None

    def by_id(self, query, cid):
        return next(c for c in self.find(query)["candidates"] if c["id"] == cid)
