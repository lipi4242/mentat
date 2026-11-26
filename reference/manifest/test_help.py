"""The /mentat help: a hand-written, versioned text (no generator), the agent's language, and a
/mentat status built from the same facts as the status line. Every command the text names exists."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_help.py"
REF = HERE.parent
# the admin's npm scripts: dev tree (brain/release/reference) or the composed public tree (reference)
PKG_PATH = next((d / "admin" / "worker" / "package.json" for d in REF.parents
                 if (d / "admin" / "worker" / "package.json").is_file()), None)
COMMANDS = {"/mentat", "/whoami", "/fleet:roster"}  # the installer's two + the fleet plugin's skill


def texts():
    return {lang: (HERE / ("mentat-help.%s.md" % lang)).read_text(encoding="utf-8") for lang in ("hu", "en")}


class Text(unittest.TestCase):
    def test_both_languages_carry_the_same_version_and_sections(self):
        heads = {lang: [x for x in t.splitlines() if x.startswith("== ")] for lang, t in texts().items()}
        self.assertEqual(len(heads["hu"]), len(heads["en"]))
        ver = {lang: re.search(r"^Mentat .* v(\d+) \((\d{4}-\d\d-\d\d)\)$", t, re.M) for lang, t in texts().items()}
        self.assertTrue(all(ver.values()), "a version line in both")
        self.assertEqual(ver["hu"].groups(), ver["en"].groups())

    def test_the_main_part_fits_about_25_lines_and_marks_the_feature_list(self):
        for lang, t in texts().items():
            main = t.split("\n== ")[0]
            self.assertLessEqual(len(main.strip().splitlines()), 26, lang)
            self.assertIn("[[", main, "the feature list placeholder")

    def test_every_named_command_exists(self):
        """Nothing made up: slash commands, .mentat/bin tools on the download list, npm scripts."""
        init = {lang: (REF / ("initialization%s.md" % ("" if lang == "en" else ".hu"))).read_text(encoding="utf-8")
                for lang in ("hu", "en")}
        for lang, t in texts().items():
            for cmd in re.findall(r"(?:^|\s)(/[a-z]+(?::[a-z-]+)?)(?=[\s,.)]|$)", t, re.M):
                self.assertIn(cmd, COMMANDS, (lang, cmd))
            for tool in re.findall(r"\.mentat/bin/([\w.-]+\.py)", t):
                self.assertTrue((HERE / tool).is_file(), tool)
                self.assertIn(tool, init[lang], (lang, tool, "not on the download list"))
            self.assertIsNotNone(PKG_PATH, "the admin is not in this tree")
            scripts = json.loads(PKG_PATH.read_text(encoding="utf-8"))["scripts"]
            for script in re.findall(r"npm run ([\w:-]+)", t):
                self.assertIn(script, scripts, (lang, script))
            self.assertIn("mentat-help.%s.md" % lang, init[lang])
            self.assertIn("mentat_help.py", init[lang])


class Tool(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.env = {k: v for k, v in os.environ.items() if k != "FLEET_REGISTRY"}

    def manifest(self, lang="hu", **components):
        (self.repo / "mentat.json").write_text(json.dumps({
            "agent": {"name": "Anna", "language": lang}, "components": components,
            "roles": {"default": "asszisztens", "installed": ["asszisztens"]}}), encoding="utf-8")

    def run_help(self, *args):
        r = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                           cwd=self.repo, env=self.env, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_help_is_the_text_in_the_agents_language_under_a_who_line(self):
        for lang, word in (("hu", "asszisztens"), ("en", "assistant")):
            self.manifest(lang)
            out = self.run_help()
            self.assertTrue(out.splitlines()[0].startswith("Anna · " + word), out[:80])
            self.assertIn(texts()[lang].split("\n== ")[0].strip(), out)

    def test_todo_prints_the_enable_steps(self):
        self.manifest("hu")
        out = self.run_help("todo")
        self.assertIn("npm run connect -- --repo", out)
        self.assertIn("--plugins todo", out)

    def test_status_with_nothing_connected_points_to_todo(self):
        self.manifest("hu")
        out = self.run_help("status")
        self.assertRegex(out, r"Todo: nincs bekapcsolva")
        self.assertRegex(out, r"Ütemező: nincs telepítve")
        self.assertRegex(out, r"Következő lépés: .*/mentat todo")

    def test_status_with_todo_and_a_fleet_schedule(self):
        self.manifest("en", admin={"plugins": ["cases", "todo"], "todo_handle": "anna_agent"},
                      engine={"schedule_owner": "fleet"})
        out = self.run_help("status")
        self.assertIn("Todo: on (@anna_agent)", out)
        self.assertIn("Scheduler: the fleet runs it", out)

    def test_status_with_the_engine_scheduler_and_a_last_tick(self):
        self.manifest("hu", admin={"plugins": ["todo"], "todo_handle": "anna"}, engine={"plugins": ["x"]})
        tick = self.repo / "data" / "state" / "last-tick.json"
        tick.parent.mkdir(parents=True)
        tick.write_text("{}", encoding="utf-8")
        at = datetime.datetime(2026, 11, 13, 12, 0).timestamp()
        os.utime(tick, (at, at))
        out = self.run_help("status")
        self.assertRegex(out, r"Ütemező: a motor ütemezi, utolsó ütemezett futás: 2026-11-\d\d \d\d:\d\d")
        self.assertRegex(out, r"Következő lépés: minden alap be van kapcsolva")

    def test_cases_only_admin_is_not_todo(self):
        self.manifest("hu", admin={"plugins": ["cases"]})
        self.assertIn("Todo: nincs bekapcsolva (az admin be van kötve, a todo nincs)", self.run_help("status"))


if __name__ == "__main__":
    unittest.main()
