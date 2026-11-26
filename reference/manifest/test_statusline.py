"""The Mentat status line: the line, missing fields, speed, the installer (never over the USER's own), /whoami."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import mentat_statusline as sl

HERE = pathlib.Path(__file__).resolve().parent
TOOL, INSTALL = HERE / "mentat_statusline.py", HERE / "mentat_statusline_install.py"
FMAP = {"owner": "Példa Ede", "manager": "thufir", "agents": {"thufir": {
    "main_role": "asszisztens", "extra_roles": ["flottamenedzser"], "home": {"repo": "example/thufir"}, "lang": "hu"}}}
HUD = {"statusLine": {"type": "command", "command": "bash ~/.claude/hud.sh"}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo, self.home, self.reg = self.tmp / "code" / "thufir", self.tmp / "home", self.tmp / "registry"
        for d in (self.repo, self.home, self.reg):
            d.mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "FLEET_REGISTRY")}
        self.env["HOME"] = str(self.home)

    def manifest(self, lang="hu", roles=None):
        (self.repo / "mentat.json").write_text(json.dumps({"agent": {"name": "Thufir", "language": lang},
                                                           "roles": roles or {}}), encoding="utf-8")

    def fleet(self):
        (self.reg / "fleet-map.json").write_text(json.dumps(FMAP, ensure_ascii=False), encoding="utf-8")
        self.env["FLEET_REGISTRY"] = str(self.reg)

    def run_line(self, data, *args):
        return subprocess.run([sys.executable, str(TOOL), *args], input=json.dumps(data) if isinstance(data, dict)
                              else data, capture_output=True, text=True, env=self.env, cwd=self.repo, encoding="utf-8", errors="replace")

    def whoami_installed(self):
        (self.repo / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
        (self.repo / ".claude" / "commands" / "whoami.md").write_text("python3 .mentat/bin/mentat_statusline.py\n", encoding="utf-8")

    def sample(self, **extra):
        return dict({"cwd": str(self.repo), "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
                     "workspace": {"current_dir": str(self.repo), "project_dir": str(self.repo)}}, **extra)


class Line(Base):
    def test_a_sample_input_gives_name_roles_fleet_model_folder_and_tip(self):
        self.manifest(roles={"default": "asszisztens", "installed": ["asszisztens"]})
        self.fleet()
        self.whoami_installed()
        r = self.run_line(self.sample(context_window={"used_percentage": 37.4},
                                      rate_limits={"five_hour": {"used_percentage": 42, "resets_at": 1}}))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.strip()
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.startswith("Thufir · asszisztens+flottamenedzser · Példa Ede flottája │ Opus 5.5"), out)
        self.assertTrue(out.endswith(" │ /whoami · /fleet:roster"), out)
        for s in ("ctx 37%", "5h 42%", "thufir"):
            self.assertIn(s, out)

    def test_missing_map_usage_and_context_drop_the_field_exit_0_and_it_is_fast(self):
        self.manifest(lang="en", roles={"default": "fejleszto", "installed": ["fejleszto"]})
        timings = []
        for _ in range(3):
            t = time.perf_counter()
            r = self.run_line(self.sample())
            timings.append(time.perf_counter() - t)
            self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.strip()
        self.assertEqual(out.split(" │ ")[:2], ["Thufir · developer", "Opus 5.5"])
        for gone in ("fleet", "ctx", "5h", "7d", "None", "/fleet:"):
            self.assertNotIn(gone, out)
        self.assertNotIn("/whoami", out)  # not installed here: no tip at all
        self.assertNotIn("/help", out)
        self.whoami_installed()
        self.assertTrue(self.run_line(self.sample()).stdout.strip().endswith(" │ /whoami"))
        t = time.perf_counter()
        for _ in range(10):
            sl.line(sl.facts(self.sample(), env=self.env, home=self.home))
        self.assertLess((time.perf_counter() - t) / 10, 0.1)  # the script's own work, per call
        self.assertLess(min(timings), 1.0, timings)  # with the interpreter start, a generous bound
        print("statusline: %.0f ms with python start, %.2f ms own work" % (
            min(timings) * 1000, (time.perf_counter() - t) * 100), file=sys.stderr)

    def test_no_brain_no_input_or_garbage_still_exit_0(self):
        for data in ("", "{not json", "[]"):
            r = self.run_line(data)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip(), "a line even without a brain")
        self.assertEqual(self.run_line(self.sample(context_window={"used_percentage": None},
                                                   rate_limits={"five_hour": "?"})).returncode, 0)

    def test_branch_and_worktree_are_read_without_git(self):
        (self.repo / ".git").write_text("gitdir: %s\n" % (self.tmp / "main.git" / "worktrees" / "thufir"), encoding="utf-8")
        (self.tmp / "main.git" / "worktrees" / "thufir").mkdir(parents=True)
        (self.tmp / "main.git" / "worktrees" / "thufir" / "HEAD").write_text("ref: refs/heads/feat/x\n", encoding="utf-8")
        out = self.run_line(self.sample()).stdout
        self.assertIn("(feat/x · wt:thufir)", out)


class Whoami(Base):
    def test_whoami_gives_the_same_facts_on_several_lines_without_stdin(self):
        self.manifest(roles={"default": "asszisztens", "installed": ["asszisztens", "kiado"]})
        self.fleet()
        self.whoami_installed()
        r = subprocess.run([sys.executable, str(TOOL), "--whoami"], capture_output=True, text=True,
                           env=self.env, cwd=self.repo, stdin=subprocess.DEVNULL, timeout=10, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = dict(x.split(": ", 1) for x in r.stdout.strip().splitlines())
        self.assertEqual(rows["Ágens"], "Thufir")
        self.assertEqual(rows["Szerep"], "asszisztens+kiadó+flottamenedzser")
        self.assertEqual(rows["Flotta"], "Példa Ede flottája")
        self.assertEqual(rows["Tipp"], "/whoami · /fleet:roster")
        self.assertTrue(rows["Mappa"].endswith("thufir"))
        line = self.run_line({"cwd": str(self.repo)}).stdout.strip()
        for v in rows.values():
            self.assertIn(v, line)


class Isolation(unittest.TestCase):
    def test_the_run_never_sees_the_real_user_config(self):
        import _tmp_run
        self.assertTrue(os.environ["HOME"].startswith(_tmp_run.RUN_TMP), os.environ["HOME"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", os.environ)
        self.assertNotIn("FLEET_REGISTRY", os.environ)


class Tips(Base):
    def test_the_tip_names_only_commands_that_ship(self):
        """/mentat, /whoami: the installer writes exactly the files the tip probes; /fleet:<x>: a plugin skill."""
        skills = next((d / "fleet" / "plugin" / "skills" for d in HERE.parents
                       if (d / "fleet" / "plugin" / "skills").is_dir()), None)
        self.assertIsNotNone(skills, "the fleet plugin is not in this tree")
        for cmd, _ in sl.TIPS:
            with self.subTest(cmd=cmd):
                if cmd.startswith("/fleet:"):
                    self.assertTrue((skills / cmd.split(":", 1)[1] / "SKILL.md").is_file())
                else:
                    self.assertIn(cmd, ("/mentat", "/whoami"))
                    self.manifest()
                    subprocess.run([sys.executable, str(INSTALL), "--repo", str(self.repo)], env=self.env,
                                   capture_output=True, check=True)
                    self.assertTrue((self.repo / ".claude" / "commands" / (cmd[1:] + ".md")).is_file())
        line = self.run_line(self.sample()).stdout  # both installed: /mentat supersedes /whoami in the tip
        self.assertTrue(line.rstrip().endswith(" │ /mentat"), line)
        self.assertFalse(any(cmd == "/help" for cmd, _ in sl.TIPS))  # Claude Code's own help, not ours


class Install(Base):
    def install(self, *args):
        return subprocess.run([sys.executable, str(INSTALL), "--repo", str(self.repo), *args],
                              capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")

    def settings(self, rel=".claude/settings.json"):
        p = self.repo / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def test_fresh_repo_gets_the_status_line_and_whoami(self):
        self.manifest()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(ls)"]}}', encoding="utf-8")
        self.assertEqual(self.install().returncode, 0)
        s = self.settings()
        self.assertIn("mentat_statusline.py", s["statusLine"]["command"])
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls)"])
        cmd = (self.repo / ".claude" / "commands" / "whoami.md").read_text(encoding="utf-8")
        self.assertIn("python3 .mentat/bin/mentat_statusline.py --whoami", cmd)
        before = (self.repo / ".claude" / "settings.json").read_bytes()
        self.assertIn("változatlan", self.install().stdout)
        self.assertEqual((self.repo / ".claude" / "settings.json").read_bytes(), before)

    def test_a_users_own_status_line_is_never_replaced_without_yes_and_the_decision_is_recorded(self):
        for where in (self.home / ".claude" / "settings.json", self.repo / ".claude" / "settings.local.json",
                      self.repo / ".claude" / "settings.json"):
            with self.subTest(where=where):
                shutil.rmtree(self.repo / ".claude", True)
                shutil.rmtree(self.home / ".claude", True)
                where.parent.mkdir(parents=True)
                where.write_text(json.dumps(HUD), encoding="utf-8")
                r = self.install()
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn("a meglévő statusLine marad", r.stdout)
                self.assertEqual(json.loads(where.read_text(encoding="utf-8")), HUD)
                self.assertNotIn("mentat_statusline", json.dumps(self.settings()))
                rec = json.loads((self.repo / ".mentat" / "statusline.json").read_text(encoding="utf-8"))
                self.assertEqual((rec["decision"], rec["where"]), ("kept", str(where)))
        self.install("--force")
        self.assertIn("mentat_statusline.py", self.settings()["statusLine"]["command"])
        self.assertEqual(json.loads((self.repo / ".mentat" / "statusline.json").read_text(encoding="utf-8"))["decision"],
                         "replaced-with-yes")

    def test_a_foreign_whoami_and_a_broken_settings_file_are_left_alone(self):
        (self.repo / ".claude" / "commands").mkdir(parents=True)
        (self.repo / ".claude" / "commands" / "whoami.md").write_text("mine\n", encoding="utf-8")
        (self.repo / ".claude" / "settings.json").write_text("{broken", encoding="utf-8")
        r = self.install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("nem írtam át", r.stdout)
        self.assertEqual((self.repo / ".claude" / "settings.json").read_text(encoding="utf-8"), "{broken")
        (self.repo / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        self.assertIn("nem a Mentaté", self.install().stdout)
        self.assertEqual((self.repo / ".claude" / "commands" / "whoami.md").read_text(encoding="utf-8"), "mine\n")


if __name__ == "__main__":
    unittest.main()
