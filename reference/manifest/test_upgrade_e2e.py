"""The whole upgrade path, end to end without an LLM: a pre-0.5 brain with a vendored 0.2.2 engine
(the real engine sync from this release), and a 0.4-era desktop brain."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _upgrade_fixture as fx  # noqa: E402
import mentat_upgrade_inv as inv  # noqa: E402
from test_upgrade import VERSION, Base  # noqa: E402


class Pre05(Base):
    """The whole path on a pre-0.5 brain with a vendored 0.2.2 engine, the real engine sync."""

    def test_upgrade_keeps_every_user_file_and_records_the_new_layout(self):
        fx.pre05(self.root, self.env)
        before, old_head = self.snapshot(), fx.git(self.root, "rev-parse", "HEAD", env=self.env).stdout.strip()
        src = fx.fake_source(tempfile.mkdtemp(), "v" + VERSION, self.env)
        self.assertEqual(self.up("plan", "--agent", "Terem").returncode, 0)
        r = self.up("apply", "--yes", "--agent", "Terem", "--engine-src", str(src))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("MENTAT-UPGRADE OK", r.stdout)
        self.assertEqual(self.snapshot(), before, "no file of the USER changed")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        import mentat_self_image as si
        self.assertTrue(agents.startswith(si.START), "the self-image block is first")
        self.assertIn("\n" + fx.AGENTS, agents, "the USER's AGENTS.md text is kept whole, blocks come after")
        self.assertIn("mentat:managed:start reference-manual -->", agents)
        self.assertIn("/v%s/" % VERSION, agents)
        hooks = json.loads((self.root / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
        self.assertIn("session-start.sh", json.dumps(hooks["SessionStart"]), "their own hook stays")
        self.assertIn("szerep_guard.py", json.dumps(hooks["PreToolUse"]))
        man = json.loads((self.root / "mentat.json").read_text(encoding="utf-8"))
        self.assertEqual(man["agent"]["name"], "Terem")
        self.assertEqual(man["components"]["engine"]["path"], "anytime_engine")
        self.assertIn("version=%s" % VERSION, (self.root / "anytime_engine" / "VERSION").read_text(encoding="utf-8"))
        backup = [b for b in fx.git(self.root, "branch", "--list", "mentat-backup/*", env=self.env).stdout.split()
                  if b.startswith("mentat-backup/")]
        self.assertEqual(len(backup), 1)
        self.assertEqual(fx.git(self.root, "rev-parse", backup[0], env=self.env).stdout.strip(), old_head)
        self.assertEqual(fx.git(self.root, "status", "--porcelain", env=self.env).stdout, "", "all committed")
        self.assertIn("CHECK skeleton: OK", r.stdout)
        clone = self.home / "src" / "mentat"
        (clone / "engine" / "sync-to.sh").write_text("#!/bin/sh\necho tampered\n", encoding="utf-8")
        fx.commit(self.root, "noop", self.env)
        import mentat_upgrade_steps as st
        from unittest import mock
        # never the real ~/src/mentat; this tree's mentat_init, not a copy another test put on sys.path
        with mock.patch.dict("os.environ", {"HOME": str(self.home)}), \
                mock.patch.object(sys, "path", [str(HERE)] + sys.path), mock.patch.dict(sys.modules):
            for name in [m for m in sys.modules if m.startswith("mentat_init")]:
                del sys.modules[name]
            got = st.engine(self.root, VERSION, str(src)) or ""
        self.assertIn("not exactly the v%s tag" % VERSION, got, "a changed Mentat copy is never run")
        again = self.up("plan", "--agent", "Terem")
        self.assertIn("KIND brain+engine", again.stdout, "the next upgrade sees the new layout")


class Brain(Base):
    """A 0.4-era desktop brain: the product blocks move to this release, the USER's text stays."""

    def test_blocks_are_refreshed_and_the_users_text_kept(self):
        fx.init(self.root, self.env)
        old = "https://raw.githubusercontent.com/lipi4242/" + "mentat/v0.4.0/"  # bump:keep
        tool = [sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu", "--repo", str(self.root)]
        subprocess.run(tool + ["--base", old], capture_output=True, env=self.env)
        agents = self.root / "AGENTS.md"
        mine = "\n## Saját\n\nA kedvenc színem a kék.\n"
        agents.write_text(re.sub(r"<[^<>\n]*TBD>", "Anna", agents.read_text(encoding="utf-8")) + mine,
                          encoding="utf-8")
        subprocess.run(tool + ["--name", "Teszt", "--version", "0.4.0"], capture_output=True, env=self.env)
        fx.commit(self.root, "0.4 brain", self.env)
        self.assertEqual(inv.inventory(self.root)["kind"], "brain")
        self.assertEqual(self.up("plan").returncode, 0)
        r = self.up("apply", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = agents.read_text(encoding="utf-8")
        self.assertIn(mine, text)
        self.assertNotIn("/v0.4.0/", text)
        self.assertIn("/v%s/" % VERSION, text)
        self.assertEqual(json.loads((self.root / ".mentat/local.json").read_text(encoding="utf-8"))["installed"]["brain"], VERSION)
        self.assertEqual(fx.git(self.root, "status", "--porcelain", env=self.env).stdout, "")

    def test_a_brain_from_before_the_local_skills_gets_them_and_the_self_image(self):
        """A 0.5-era brain: no .claude/skills, no self-image block, no /whoami: all arrive, committed."""
        fx.init(self.root, self.env)
        old = "https://raw.githubusercontent.com/lipi4242/" + "mentat/v0.5.1/"  # bump:keep
        tool = [sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu", "--repo", str(self.root)]
        subprocess.run(tool + ["--base", old, "--name", "Teszt", "--version", "0.5.1"], capture_output=True,
                       env=self.env)
        agents = self.root / "AGENTS.md"
        import mentat_self_image as si
        text = re.sub(r"<[^<>\n]*TBD>", "Anna", si.BLOCK.sub("", agents.read_text(encoding="utf-8")).lstrip("\n"))
        agents.write_text(text, encoding="utf-8")
        for rel in (".claude/skills", ".claude/commands", ".mentat/state"):
            shutil.rmtree(self.root / rel, ignore_errors=True)
        note = self.root / "agy" / "people" / "anna.md"
        note.write_text("# Anna\n\nA tulajdonos.\n", encoding="utf-8")
        fx.commit(self.root, "0.5.1 brain", self.env)
        self.assertEqual(self.up("plan").returncode, 0)
        r = self.up("apply", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHECK skeleton: OK", r.stdout)
        for name in ("develop", "backlog", "status"):
            self.assertTrue((self.root / ".claude/skills" / name / "SKILL.md").is_file(), name)
        self.assertTrue(agents.read_text(encoding="utf-8").startswith(si.START), "self-image first")
        self.assertEqual(note.read_text(encoding="utf-8"), "# Anna\n\nA tulajdonos.\n", "notes untouched")
        self.assertEqual(fx.git(self.root, "status", "--porcelain", env=self.env).stdout, "", "all committed")


    def test_a_failed_commit_is_a_loud_stop_not_ok(self):
        """No git identity (a fresh machine, the release agent's hermetic gate): git refuses the
        commit, and the upgrade says so instead of reporting a commit it never made."""
        fx.pre05(self.root, self.env, engine=False)
        for k in ("user.name", "user.email"):
            fx.git(self.root, "config", "--unset", k, env=self.env)
        fx.git(self.root, "config", "user.useConfigOnly", "true", env=self.env)
        env = {k: v for k, v in self.env.items() if not k.startswith(("GIT_AUTHOR", "GIT_COMMITTER")) and k != "EMAIL"}
        self.assertEqual(self.up("plan", "--agent", "Terem").returncode, 0)
        r = subprocess.run([sys.executable, "-I", str(self.root / ".mentat/bin/mentat_upgrade.py"), "apply", "--yes",
                            "--agent", "Terem", "--repo", str(self.root)], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("MENTAT-UPGRADE HIBA", r.stdout)
        self.assertIn("user.name", r.stdout)
        self.assertNotIn("committed ", r.stdout, "no commit is claimed")
        self.assertNotIn("MENTAT-UPGRADE OK", r.stdout)


class Packs(unittest.TestCase):
    """A minor step moves the packs' engine range: every vendored pack is re-synced with the engine,
    listed in mentat.json or not (an older brain may have one it never recorded)."""

    def test_every_vendored_pack_goes_into_the_engine_sync(self):
        import mentat_upgrade_steps as st
        root = pathlib.Path(tempfile.mkdtemp())
        for pkg in ("anytime_engine", "anytime_cases", "anytime_todo"):
            (root / pkg).mkdir()
            (root / pkg / "__init__.py").write_text("", encoding="utf-8")
        (root / "anytime_bekotes").mkdir()  # no __init__.py: not a pack copy
        self.assertEqual(st.sync_args(root), [".", "--pack", "cases", "--pack", "todo"])
        self.assertEqual(st.sync_args(pathlib.Path(tempfile.mkdtemp())), ["."])

if __name__ == "__main__":
    unittest.main()
