"""Operátor-skillek: a merge-agents a box Claude Code-jában is látsszon (H5-mérés, 2026-10-29)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fleet import cli, operator_skills as ops


def fake_plugin(root: Path) -> Path:
    d = root / "fl" / "plugin" / "skills" / "merge-agents"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: merge-agents\n---\n")
    return root / "fl" / "plugin"


class TestLink(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plugin = fake_plugin(self.tmp)
        self.target = self.tmp / "claude" / "skills"

    def test_links_and_is_idempotent(self):
        notes = ops.link_operator_skills(self.plugin, self.target)
        link = self.target / "merge-agents"
        self.assertTrue(link.is_symlink())
        self.assertTrue((link / "SKILL.md").is_file())
        self.assertEqual(len(notes), 1)
        self.assertEqual(ops.link_operator_skills(self.plugin, self.target), [])

    def test_relinks_our_link_to_a_moved_checkout(self):
        old = fake_plugin(self.tmp / "old")
        ops.link_operator_skills(old, self.target)
        ops.link_operator_skills(self.plugin, self.target)
        self.assertEqual(Path(os.readlink(self.target / "merge-agents")),
                         (self.plugin / "skills" / "merge-agents").resolve())

    def test_never_overwrites_a_foreign_dir_or_link(self):
        (self.target / "merge-agents").mkdir(parents=True)
        notes = ops.link_operator_skills(self.plugin, self.target)
        self.assertIn("nem írom felül", notes[0])
        self.assertFalse((self.target / "merge-agents").is_symlink())
        other = self.tmp / "t2"
        other.mkdir()
        (other / "merge-agents").symlink_to(self.tmp)
        self.assertIn("idegen", ops.link_operator_skills(self.plugin, other)[0])

    def test_missing_skill_in_checkout_is_silent(self):
        empty = self.tmp / "e" / "plugin"
        empty.mkdir(parents=True)
        self.assertEqual(ops.link_operator_skills(empty, self.target), [])

    def test_claude_config_dir_wins(self):
        self.assertEqual(ops.skills_dir({"CLAUDE_CONFIG_DIR": "/c"}, Path("/h")), Path("/c/skills"))
        self.assertEqual(ops.skills_dir({}, Path("/h")), Path("/h/.claude/skills"))


class TestHelp(unittest.TestCase):
    def test_top_level_help_points_to_plan_merge_in_both_languages(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["--help"])
        txt = out.getvalue()
        for need in ("kivezetése", "beolvasztása", "retire", "merge", "fleet plan-merge", "SKILL.md", "⛔"):
            self.assertIn(need, txt)

    def test_read_only_commands_do_not_link(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            try:
                cli.main(["validate"])
            except SystemExit:
                pass
        self.assertNotIn("skill:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
