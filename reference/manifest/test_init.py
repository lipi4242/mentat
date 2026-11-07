"""mentat_init.py: install in one call (measured 2026-10-23: 8-12 turns, 14-42 tool calls).

One call does the preflight, the skeleton with the guard hook, the identity placeholders,
mentat.json, git identity, the first commit, optionally the engine pinned to the tag
with a no-timer config, and a selftest; it prints a short human summary ending in
`MENTAT-INIT OK` (the harness metric's anchor) or `MENTAT-INIT HIBA: <one thing>`.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_init.py"
BASE = "https://example.com/kit/v9.9.9/"
ANSWERS = ["--lang", "hu", "--user", "Kertész Anna", "--address", "tegez", "--agent", "Thufir",
           "--base", BASE, "--version", "9.9.9", "--no-prove"]
ME = ["--git-email", "anna@example.com"]  # the USER's own address; the tool never invents one


def fake_bin(d, name, body):
    p = pathlib.Path(d) / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(0o755)


class InitBase(unittest.TestCase):
    answers = ANSWERS + ME

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.home = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()
        fake_bin(self.bin, "claude", 'echo "2.1.309 (Claude Code)"')
        path = self.bin + os.pathsep + os.environ["PATH"]
        self.env = dict(os.environ, HOME=self.home, PATH=path, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.path.join(self.home, "gitconfig"))
        for k in ("CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR"):
            self.env.pop(k, None)

    def run_init(self, *extra, env=None):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *self.answers, *extra],
                              capture_output=True, text=True, env=env or self.env)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True,
                              env=self.env).stdout.strip()


class Init(InitBase):
    def test_one_call_installs_and_says_so_briefly(self):
        r = self.run_init()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[-1], "MENTAT-INIT OK")
        self.assertLessEqual(len(lines), 12, r.stdout)
        self.assertIn("munkamappán kívül", r.stdout)  # the boundary, in human words
        agents = (self.root / "AGENTS.md").read_text()
        for done in ("Kertész Anna", "Thufir", "tegez"):
            self.assertIn(done, agents)
        for gone in ("<FELHASZNÁLÓ neve TBD>", "<megszólítás TBD>", "<ügynök neve TBD>"):
            self.assertNotIn(gone, agents)
        self.assertIn("<munka, fókuszterületek TBD>", agents)  # the conversation fills these
        self.assertEqual(json.loads((self.root / "mentat.json").read_text())["agent"]["name"], "Thufir")
        self.assertEqual(self.git("config", "user.name"), "Kertész Anna")
        self.assertEqual(len(self.git("log", "--oneline").splitlines()), 1)
        pre = json.loads((self.root / ".claude/settings.json").read_text())["hooks"]["PreToolUse"][-1]["hooks"][0]
        self.assertEqual(pre.get("onFailure"), "block")

    def test_the_vendored_guard_is_probed_with_an_outside_read(self):
        bk = self.root / ".mentat" / "bin" / "bekotes"
        shutil.copytree(HERE.parent / "bekotes", bk, ignore=shutil.ignore_patterns("test_*", "__pycache__"))
        for f in ("mentat_roles.py", "mentat_manifest.py", "mentat_rules.py"):
            shutil.copy(HERE / f, bk / f)
        r = self.run_init()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with (bk / "szerep_kint.py").open("a") as f:  # a guard that runs fine but sees nothing outside
            f.write("\n\ndef outside(*a, **k):\n    return []\n")
        r = self.run_init()
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("szerep-őr", r.stdout.splitlines()[-1])

    def test_a_guard_that_denies_everything_is_not_green(self):  # CISO, #69: the probe needs an allow too
        bk = self.root / ".mentat" / "bin" / "bekotes"
        shutil.copytree(HERE.parent / "bekotes", bk, ignore=shutil.ignore_patterns("test_*", "__pycache__"))
        for f in ("mentat_roles.py", "mentat_manifest.py", "mentat_rules.py"):
            shutil.copy(HERE / f, bk / f)
        with (bk / "szerep_kint.py").open("a") as f:  # every path "outside": every call asked
            f.write("\n\ndef outside(root, tool, inp, cwd, sid=None):\n    return [('x', 'olvas', False)]\n")
        r = self.run_init()
        self.assertIn("MENTAT-INIT HIBA", r.stdout)

    def test_twice_is_the_same(self):
        self.assertEqual(self.run_init().returncode, 0)
        r = self.run_init()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.git("log", "--oneline").splitlines()), 1)

    def test_preflight_names_the_one_missing_thing(self):
        fake_bin(self.bin, "claude", 'echo "2.1.200 (Claude Code)"')  # before onFailure: fails open
        r = self.run_init()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("2.1.295", r.stdout)
        self.assertFalse((self.root / "AGENTS.md").exists(), "nothing done before the preflight passes")
        nogit = dict(self.env, PATH=self.bin)  # no git, no python3 on PATH (we run sys.executable)
        r = self.run_init(env=nogit)
        self.assertIn("git", r.stdout.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
