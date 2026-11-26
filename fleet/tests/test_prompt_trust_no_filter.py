"""A prompt-trust git-ellenőrzése nem futtathat repó-konfigban megadott parancsot.

A `git status` a munkafa-fájlt a .gitattributes szerinti `filter.<x>.clean` paranccsal
hasheli újra, és ezt a parancsot a repó-lokális config adja: a reconcile (a fleet
felügyelője) így az ágens repójából kapott parancsot futtatna. Külön OS-user alatt
futó ágensnél ez jogosultság-átlépés. Az ellenőrzés ezért csak az indexet és a HEAD-et
olvassa (ls-files -s, rev-parse HEAD:<út>), a munkafa-fájlt pedig szűrő nélkül hasheli
(hash-object --no-filters). A döntés közben ugyanaz marad: csak a HEAD-del egyező,
követett fájl kiadott."""
from __future__ import annotations
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drift_box import T0, Box  # noqa: E402

from fleet import prompt_trust  # noqa: E402


class TestNoRepoConfigCommand(Box):
    def arm_filter(self) -> Path:
        mark = self.d / "filter-futott"
        self.git("config", "filter.x.clean", "touch '%s'; cat" % mark)
        self.git("config", "filter.x.smudge", "cat")
        (self.wd / ".gitattributes").write_text("*.md filter=x\n")
        self.change(".gitattributes", "*.md filter=x\n")
        if mark.exists():
            mark.unlink()                 # a commit maga lefuttatta; innen mérünk
        return mark

    def test_clean_filter_does_not_run_on_touched_file(self):
        mark = self.arm_filter()
        os.utime(self.wd / "CLAUDE.md", (T0 + 5, T0 + 5))   # a stat eltér: a status újrahashelne
        prompt_trust.git_problems(self.wd, ["CLAUDE.md", "AGENTS.md"])
        prompt_trust.released(self.wd)
        self.assertFalse(mark.exists(), "a repó-lokális clean filter lefutott")

    def test_clean_filter_does_not_run_on_changed_file(self):
        mark = self.arm_filter()
        (self.wd / "CLAUDE.md").write_text("helyben átírva\n")
        probs = prompt_trust.git_problems(self.wd, ["CLAUDE.md"])
        self.assertFalse(mark.exists(), "a repó-lokális clean filter lefutott")
        self.assertEqual(probs, ["CLAUDE.md"])

    def test_no_status_call_and_fsmonitor_still_off(self):
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            return subprocess.run(cmd, **kw)
        prompt_trust.git_problems(self.wd, ["CLAUDE.md"], run=run)
        self.assertTrue(seen)
        for cmd in seen:
            self.assertNotIn("status", cmd)
            self.assertIn("core.fsmonitor=false", cmd)
            self.assertFalse(any("safe.directory" in c for c in cmd), cmd)


class TestSameDecision(Box):
    def test_committed_file_is_clean(self):
        self.assertEqual(prompt_trust.git_problems(self.wd, ["CLAUDE.md", "docs/extra.md"]), [])

    def test_uncommitted_change_is_problem(self):
        (self.wd / "AGENTS.md").write_text("helyi\n")
        self.assertEqual(prompt_trust.git_problems(self.wd, ["AGENTS.md", "CLAUDE.md"]), ["AGENTS.md"])

    def test_staged_but_not_committed_is_problem(self):
        (self.wd / "AGENTS.md").write_text("indexben\n")
        self.git("add", "AGENTS.md")
        self.assertEqual(prompt_trust.git_problems(self.wd, ["AGENTS.md"]), ["AGENTS.md"])

    def test_untracked_is_problem(self):
        (self.wd / ".claude" / "rules" / "uj.md").write_text("új\n")
        self.assertEqual(prompt_trust.git_problems(self.wd, [".claude/rules/uj.md"]), [".claude/rules/uj.md"])

    def test_deleted_tracked_file_is_problem(self):
        (self.wd / "docs" / "extra.md").unlink()
        self.assertEqual(prompt_trust.git_problems(self.wd, ["docs/extra.md"]), ["docs/extra.md"])

    def test_missing_untracked_path_is_not_problem(self):
        self.assertEqual(prompt_trust.git_problems(self.wd, ["nincs.md"]), [])

    def test_workdir_below_repo_root(self):
        sub = self.wd / "docs"
        self.assertEqual(prompt_trust.git_problems(sub, ["extra.md"]), [])
        (sub / "extra.md").write_text("más\n")
        self.assertEqual(prompt_trust.git_problems(sub, ["extra.md"]), ["extra.md"])

    def test_not_a_repo_everything_is_problem(self):
        d = self.d / "nem-repo"
        d.mkdir()
        (d / "CLAUDE.md").write_text("x\n")
        self.assertEqual(prompt_trust.git_problems(d, ["CLAUDE.md"]), ["CLAUDE.md"])


if __name__ == "__main__":
    unittest.main()
