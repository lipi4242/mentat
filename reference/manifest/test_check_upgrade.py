"""--check on a brain made before a managed block existed: WARN + exit 0, with the
one-line fix; after running that line the brain is OK. A fresh brain stays strict."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_scaffold.py"


class OldBrainCheck(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        home = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))
        self.run_tool("--base", "https://example.com/kit/v9.9.9/")
        agents = self.root / "AGENTS.md"
        agents.write_text(re.sub(r"<[^<>\n]*TBD>", "Anna", agents.read_text()))
        self.run_tool("--name", "Thufir", "--version", "0.2.0")
        for k, v in (("user.name", "Anna"), ("user.email", "anna@example.com")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], env=self.env)
        self.run_tool("--commit")

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "--lang", "hu", "--repo", str(self.root),
                               *args], capture_output=True, text=True, env=self.env)

    def drop_intake(self):
        agents = self.root / "AGENTS.md"
        text = agents.read_text()
        agents.write_text(text[:text.index("\n<!-- mentat:managed:start intake -->")] + "\n")

    def test_fresh_brain_is_ok_without_warning(self):
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("WARN", r.stdout)

    def test_old_brain_warns_with_a_fix_that_works(self):
        self.drop_intake()
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        warn = [ln for ln in r.stdout.splitlines() if ln.startswith("WARN")]
        self.assertEqual(len(warn), 1, r.stdout)
        self.assertIn("intake", warn[0])
        fix = warn[0].split("fix: ", 1)[1]
        subprocess.run(fix, shell=True, cwd=self.root, check=True)
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("WARN", r.stdout)
        self.assertEqual((self.root / "AGENTS.md").read_text().count("managed:start intake"), 1)

    def test_a_broken_core_block_still_fails(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(agents.read_text().replace("managed:start claims -->", "x -->"))
        r = self.run_tool("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISSING managed block claims", r.stdout)


if __name__ == "__main__":
    unittest.main()
