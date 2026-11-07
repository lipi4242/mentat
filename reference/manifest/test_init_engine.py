"""mentat_init.py --engine: one clone of the Mentat repo (~/src/mentat) at the release tag.

The engine is the engine/ folder of that clone. A clone already at the tag is reused as it
is; one at an older tag is moved to the new tag (fetch + checkout); --engine-src stands in for
GitHub. Settings are written without a timer, and the cases pack comes along.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import subprocess
import tempfile
import unittest

from test_init import InitBase

SETUP = ("import json,pathlib,sys\nm=pathlib.Path('mentat.json');d=json.loads(m.read_text())\n"
         "d['components']['engine']={'timezone':sys.argv[sys.argv.index('--tz')+1],"
         "'args':sys.argv[1:]};m.write_text(json.dumps(d))\nprint('setup: done')\n")
SYNC = '#!/bin/sh\ncp -r "$(dirname "$0")/anytime_engine" "$1/"\necho "$@" > "$1/.sync-args"\n'


class EngineClone(InitBase):
    def setUp(self):
        super().setUp()
        self.src = pathlib.Path(tempfile.mkdtemp()) / "mentat"
        eng = self.src / "engine"
        (eng / "anytime_engine").mkdir(parents=True)
        (eng / "anytime_engine" / "__init__.py").write_text("")
        (eng / "anytime_engine" / "setup.py").write_text(SETUP)
        (eng / "anytime_engine" / "selftest.py").write_text("print('selftest: OK')\n")
        (eng / "sync-to.sh").write_text(SYNC)
        (eng / "sync-to.sh").chmod(0o755)
        (self.src / "INSTALL.md").write_text("brain at the root\n")
        self.src_git("init", "-q")
        self.commit("old")
        self.src_git("tag", "v9.9.8")
        self.commit("release")
        self.src_git("tag", "v9.9.9")
        self.commit("later")  # the branch moves on; the install must stay on the tag
        self.clone = pathlib.Path(self.home) / "src" / "mentat"

    def src_git(self, *args):
        subprocess.run(["git", "-C", str(self.src), *args], check=True, capture_output=True, env=self.env)

    def commit(self, msg):
        self.src_git("add", "-A")
        self.src_git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg, "--allow-empty")

    def at(self):
        return subprocess.run(["git", "-C", str(self.clone), "describe", "--tags"], capture_output=True,
                              text=True, env=self.env).stdout.strip()

    def install(self):
        return self.run_init("--engine", "--tz", "Europe/Budapest", "--engine-src", str(self.src))

    def test_engine_from_the_one_clone_at_the_tag_and_no_timer(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.at(), "v9.9.9")  # the tag, not the later commit on the branch
        self.assertTrue((self.clone / "INSTALL.md").is_file(), "the whole product, not an engine-only repo")
        eng = json.loads((self.root / "mentat.json").read_text())["components"]["engine"]
        self.assertEqual(eng["timezone"], "Europe/Budapest")
        self.assertIn("--no-timer", eng["args"])
        self.assertIn("--install", eng["args"])
        self.assertIn("--pack cases", (self.root / ".sync-args").read_text())
        self.assertFalse((pathlib.Path(self.home) / "src" / "anytime-engine").exists())
        self.assertIn("MENTAT-INIT OK", r.stdout)

    def test_a_clone_at_the_same_tag_is_reused(self):
        subprocess.run(["git", "clone", "-q", "--branch", "v9.9.9", str(self.src), str(self.clone)],
                       check=True, capture_output=True, env=self.env)
        (self.clone / "keep.txt").write_text("mine")  # a re-clone would lose it
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.clone / "keep.txt").read_text(), "mine")
        self.assertEqual(self.at(), "v9.9.9")

    def test_an_older_clone_moves_to_the_new_tag(self):
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "v9.9.8", "file://%s" % self.src,
                        str(self.clone)], check=True, capture_output=True, env=self.env)
        self.assertEqual(self.at(), "v9.9.8")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.at(), "v9.9.9")

    def test_a_missing_tag_is_one_named_problem(self):
        self.src_git("tag", "-d", "v9.9.9")
        r = self.install()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("v9.9.9", r.stdout.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
