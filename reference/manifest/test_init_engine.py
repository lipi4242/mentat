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


class CloneBase(InitBase):
    """A fake Mentat repo with an engine/ folder, tagged v9.9.8 and v9.9.9 (no tests here)."""

    def setUp(self):
        super().setUp()
        self.src = pathlib.Path(tempfile.mkdtemp()) / "mentat"
        eng = self.src / "engine"
        (eng / "anytime_engine").mkdir(parents=True)
        (eng / "anytime_engine" / "__init__.py").write_text("", encoding="utf-8")
        (eng / "anytime_engine" / "setup.py").write_text(SETUP, encoding="utf-8")
        (eng / "anytime_engine" / "selftest.py").write_text("print('selftest: OK')\n", encoding="utf-8")
        (eng / "sync-to.sh").write_text(SYNC, encoding="utf-8")
        (eng / "sync-to.sh").chmod(0o755)
        (self.src / "INSTALL.md").write_text("brain at the root\n", encoding="utf-8")
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
                              text=True, env=self.env, encoding="utf-8", errors="replace").stdout.strip()

    def install(self):
        return self.run_init("--engine", "--tz", "Europe/Budapest", "--engine-src", str(self.src))


class EngineClone(CloneBase):
    def test_engine_from_the_one_clone_at_the_tag_and_no_timer(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.at(), "v9.9.9")  # the tag, not the later commit on the branch
        self.assertTrue((self.clone / "INSTALL.md").is_file(), "the whole product, not an engine-only repo")
        eng = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))["components"]["engine"]
        self.assertEqual(eng["timezone"], "Europe/Budapest")
        self.assertIn("--no-timer", eng["args"])
        self.assertIn("--install", eng["args"])
        self.assertIn("--pack cases", (self.root / ".sync-args").read_text(encoding="utf-8"))
        self.assertFalse((pathlib.Path(self.home) / "src" / "anytime-engine").exists())
        self.assertIn("MENTAT-INIT OK", r.stdout)

    def test_a_clone_at_the_same_tag_is_reused(self):
        subprocess.run(["git", "clone", "-q", "--branch", "v9.9.9", str(self.src), str(self.clone)],
                       check=True, capture_output=True, env=self.env)
        (self.clone / "keep.txt").write_text("mine", encoding="utf-8")  # a re-clone would lose it
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.clone / "keep.txt").read_text(encoding="utf-8"), "mine")
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


# A setup that seeds todo_trusted with the ENGINE'S OWN trusted_seed (copied from the engine tree), so
# the test pins what the brain installer hands over to the real seeding rule and the real hint line.
SEED_SETUP = ("import json,pathlib,sys\nfrom anytime_engine import trusted_seed\n"
              "m=pathlib.Path('mentat.json');d=json.loads(m.read_text())\n"
              "a=sys.argv[sys.argv.index('--todo-owner')+1] if '--todo-owner' in sys.argv else None\n"
              "pm=sys.argv[sys.argv.index('--todo-pm')+1] if '--todo-pm' in sys.argv else None\n"
              "s=d.setdefault('components',{}).setdefault('engine',{});o=trusted_seed.owner_of(a)\n"
              "t=trusted_seed.seed(s,d,o,trusted_seed.pm_of(pm),explicit=(a,pm))\nif t is not None: s['todo_trusted']=t\n"
              "s['args']=sys.argv[1:];m.write_text(json.dumps(d))\nprint('setup: done')\n"
              "if t is not None and not o: print(trusted_seed.HINT)\n")


def engine_trusted_seed() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for d in here.parents:
        for rel in ("engine/release/src/anytime_engine/trusted_seed.py", "engine/src/anytime_engine/trusted_seed.py"):
            if (d / rel).is_file():
                return d / rel
    raise unittest.SkipTest("the engine is not in this tree")


class TrustedOwner(CloneBase):
    """The owner's todo principal reaches the engine setup; without it, the install says how to add it."""

    def setUp(self):
        super().setUp()
        pkg = self.src / "engine" / "anytime_engine"
        (pkg / "trusted_seed.py").write_text(engine_trusted_seed().read_text(encoding="utf-8"), encoding="utf-8")
        (pkg / "setup.py").write_text(SEED_SETUP, encoding="utf-8")
        self.commit("seed")
        self.src_git("tag", "-f", "v9.9.9")
        for k in ("TODO_HANDLE", "ANYTIME_TODO_OWNER", "ANYTIME_TODO_PM"):
            self.env.pop(k, None)

    def trusted(self):
        return json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))["components"]["engine"].get("todo_trusted")

    def test_a_known_owner_is_on_the_trusted_list(self):
        r = self.run_init("--engine", "--tz", "Europe/Budapest", "--engine-src", str(self.src), "--todo-owner", "p_anna")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.trusted(), ["Thufir", "p_anna"])
        self.assertNotIn("Bizalmi lista", r.stdout)

    def test_the_agents_own_pm_reaches_the_engine_setup(self):
        r = self.run_init("--engine", "--tz", "Europe/Budapest", "--engine-src", str(self.src),
                          "--todo-owner", "p_anna", "--todo-pm", "p_paul")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.trusted(), ["Thufir", "p_anna", "p_paul"])

    def test_an_unknown_owner_leaves_the_agent_alone_and_the_install_says_how_to_add_one(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.trusted(), ["Thufir"])
        self.assertIn("Bizalmi lista: csak az ágens van rajta", r.stdout)
        self.assertIn("--todo-owner", r.stdout)
        self.assertIn("MENTAT-INIT OK", r.stdout)

    def test_the_sentence_is_true_running_the_install_again_with_the_owner_adds_the_owner(self):
        self.install()
        self.assertEqual(self.trusted(), ["Thufir"])
        r = self.run_init("--engine", "--tz", "Europe/Budapest", "--engine-src", str(self.src), "--todo-owner", "p_anna")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.trusted(), ["Thufir", "p_anna"])
        self.assertNotIn("Bizalmi lista", r.stdout)


if __name__ == "__main__":
    unittest.main()
