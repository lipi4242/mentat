"""A map-karbantartas skill szövege: nem mergel, csak mozgat, move-check bizonyíték nélkül nincs PR,
és minden `fleet map …` parancsa, amit leír, létezik a CLI-ben."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import re
import shlex
import unittest
from pathlib import Path

from fleet import cli

SKILL = Path(__file__).resolve().parents[1] / "plugin" / "skills" / "map-karbantartas" / "SKILL.md"
FENCE = re.compile(r"```.*?```", re.S)


class TestSkillText(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_names_the_skill(self):
        self.assertTrue(self.text.startswith("---\nname: map-karbantartas\ndescription: "))
        self.assertIn("soha nem mergel", self.text.split("---")[1])

    def test_the_no_merge_rule_and_no_merge_command_to_run(self):
        self.assertIn("**Ne mergelj.**", self.text)
        for cmd in ("gh pr merge", "git merge"):
            self.assertIn("se `%s`" % cmd, self.text.lower())  # only as a prohibition
            for block in FENCE.findall(self.text):
                self.assertNotIn(cmd, block)
        self.assertNotRegex(self.text, r"git push[^\n]*\b(main|master)\b")

    def test_the_move_only_rule_and_the_move_check_call(self):
        self.assertIn("**Csak mozgatás.**", self.text)
        self.assertIn("fleet map move-check /tmp/regi-AGENTS.md AGENTS.md --dups", self.text)
        self.assertIn("törölve, mert duplikált: <a sor> → itt maradt meg:", self.text)  # the --dups row format

    def test_a_red_move_check_opens_no_pr_only_a_todo(self):
        red = self.text[self.text.index("`1` (van lelet)"):]
        self.assertIn("**nincs PR.**", red[:200])
        self.assertIn("mentat-todo item new", red[:400])
        self.assertIn("kimenetét", self.text[self.text.index("`0` (tiszta mozgatás)"):][:200])

    def test_rewording_is_never_done_only_proposed(self):
        self.assertIn("nem te csinálod meg", self.text)
        self.assertIn("jóváhagyása után", self.text)

    def test_every_fleet_map_command_in_the_skill_parses(self):
        parser = cli.build_parser()
        calls = re.findall(r"`(fleet map [^`]+)`", self.text) + re.findall(r"^\s*(fleet map .+)$", self.text, re.M)
        self.assertGreaterEqual(len(calls), 6)
        for call in calls:
            args = shlex.split(re.sub(r"<[^>]+>", "x", call))[1:]  # placeholders become a plain word
            if len(args) == 2:
                continue  # a bare command name in prose, not a call
            with self.subTest(call=call):
                try:
                    parser.parse_args(args)
                except SystemExit as e:
                    self.fail("%s: %s" % (call, e))


if __name__ == "__main__":
    unittest.main()
