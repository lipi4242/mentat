"""J9: on a takeover, mentat_init.py says what it found, what it committed and what it left alone.

Class of error (holdout, 0.3.0): the first answer did not say what was in the folder, the git
status was skipped, the commit's content was never named, and the git identity became a made-up
user@localhost. Now the tool prints a machine inventory (file kinds, half-finished app signs,
notes and todo files, other agents' instruction files, uncommitted changes file by file), the
files of its own commit, and leaves the USER's changes untouched until they decide. A git
identity is asked for only when a commit needs one and none is set.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import subprocess
import unittest

from test_init import ANSWERS, ME, InitBase


class Inventory(InitBase):
    def tidy_repo(self):
        """A folder someone already worked in: a repo with a commit and work left uncommitted."""
        (self.root / "app").mkdir()
        (self.root / "app" / "package.json").write_text('{"name": "tagdij"}\n')
        (self.root / "app" / "index.html").write_text("<!-- TODO: finish the form -->\n")
        (self.root / "notes.md").write_text("# Notes\n")
        (self.root / ".cursorrules").write_text("Always answer in German.\n")
        g = ["git", "-C", str(self.root)]
        subprocess.run(g + ["init", "-q"], check=True, env=self.env)
        subprocess.run(g + ["add", "-A"], check=True, env=self.env)
        subprocess.run(g + ["-c", "user.name=B", "-c", "user.email=b@example.com", "commit", "-qm", "start"],
                       check=True, env=self.env)
        (self.root / "notes.md").write_text("# Notes\n\n- call the accountant\n")
        (self.root / "todo.txt").write_text("finish the fee list\n")
        (self.root / "fees.csv").write_text("name,paid\n")

    def test_the_takeover_summary_names_what_was_found_and_left_alone(self):
        self.tidy_repo()
        r = self.run_init()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout
        for found in ("notes.md", "todo.txt", "app/package.json", "TODO", ".cursorrules", "1 táblázat"):
            self.assertIn(found, out)
        self.assertIn("M notes.md", out)
        self.assertIn("?? todo.txt", out)
        self.assertIn("A commitba ez került:", out)
        self.assertIn("AGENTS.md", out.split("A commitba ez került:")[1].splitlines()[0])
        status = self.git("status", "--porcelain")
        self.assertIn("M notes.md", status)          # still the USER's, uncommitted
        self.assertIn("?? todo.txt", status)
        self.assertNotIn("notes.md", self.git("show", "--name-only", "--format=", "HEAD"))
        self.assertLessEqual(len(out.splitlines()), 12, out)

    def test_the_summary_speaks_the_language_given(self):
        self.tidy_repo()
        args = [a if a != "hu" else "en" for a in ANSWERS]
        r = subprocess.run([*self.cmd(), *args, *ME], capture_output=True, text=True, env=self.env)
        self.assertIn("Found in this folder", r.stdout, r.stdout + r.stderr)
        self.assertIn("Committed:", r.stdout)

    def test_an_empty_folder_says_so_in_one_line(self):
        r = self.run_init()
        self.assertIn("A mappa üres volt", r.stdout)
        self.assertLessEqual(len(r.stdout.splitlines()), 8, r.stdout)

    def cmd(self):
        import sys
        from test_init import TOOL
        return [sys.executable, str(TOOL), "--repo", str(self.root)]


class Identity(InitBase):
    answers = ANSWERS

    def test_no_identity_is_asked_never_invented(self):
        r = self.run_init()
        self.assertNotEqual(r.returncode, 0)
        last = r.stdout.splitlines()[-1]
        self.assertIn("MENTAT-INIT HIBA", last)
        self.assertIn("--git-email", last)
        self.assertNotIn("localhost", r.stdout)
        self.assertEqual(self.git("log", "--oneline"), "")

    def test_a_localhost_address_is_refused(self):
        r = self.run_init("--git-email", "anna@localhost")
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertNotEqual(self.git("config", "user.email"), "anna@localhost")

    def test_an_identity_already_set_is_used_without_asking(self):
        with open(os.path.join(self.home, "gitconfig"), "w") as f:
            f.write("[user]\n\tname = Anna\n\temail = anna@example.com\n")
        r = self.run_init()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("anna@example.com", r.stdout)


if __name__ == "__main__":
    unittest.main()
