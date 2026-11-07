"""Guard 0.3.1: the two gaps #38 left open, plus the obvious detours.

1. A bare file name read from inside a forbidden folder (`cd bank && cat x.csv`,
   or the hook cwd already in it).
2. Bash commands that write (`sed -i`, `>`, `tee`, `cp`, `mv`, `rm`, `dd of=`, `sh -c`)
   are matched against the role's Edit/Write rules and the built-in role-file rules.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from test_guard import GuardBase


class GuardBashCwd(GuardBase):
    def setUp(self):
        super().setUp()
        (self.root / "munka" / "bank").mkdir(parents=True)
        (self.root / "munka" / "bank" / "x.csv").write_text("1\n")
        (self.root / "munka" / "a.txt").write_text("a\n")

    def bash(self, cmd, role="fejleszto", cwd=None):
        extra = {"cwd": str(cwd)} if cwd else {}
        return self.decide("Bash", {"command": cmd}, role, **extra)

    def test_cd_into_forbidden_folder_then_bare_name(self):
        for cmd in ("cd bank && cat x.csv", "cd bank; head -1 x.csv", "pushd bank && grep 1 x.csv"):
            self.assertEqual(self.bash(cmd, cwd=self.root / "munka"), "deny", cmd)

    def test_hook_cwd_inside_forbidden_folder(self):
        for cmd in ("cat x.csv", "ls", "wc -l *.csv"):
            self.assertEqual(self.bash(cmd, cwd=self.root / "munka" / "bank"), "deny", cmd)
        self.assertEqual(self.bash("cd ../.. && git status", cwd=self.root / "munka" / "bank"), "allow")

    def test_code_and_symlink_detours(self):
        self.assertEqual(self.bash("python3 -c \"print(open('munka/bank/x.csv').read())\""), "deny")
        self.assertEqual(self.bash("echo `cat munka/bank/x.csv`"), "deny")
        (self.root / "b").symlink_to(self.root / "munka" / "bank")
        self.assertEqual(self.bash("cat b/x.csv"), "deny")
        self.assertEqual(self.bash("cd b && cat x.csv"), "deny")

    def test_reads_that_stay_allowed(self):
        for cmd in ("ls", "git status", "cat munka/a.txt", "echo bank", "grep bank munka/a.txt",
                    "git commit -m 'fix bank/x parsing'",
                    "python3 .mentat/bin/mentat_cli.py role --json"):
            self.assertEqual(self.bash(cmd), "allow", cmd)


class GuardBashWrite(GuardBase):
    def setUp(self):
        super().setUp()
        (self.root / "munka").mkdir()
        (self.root / "munka" / "a.txt").write_text("a\n")

    def test_assistant_cannot_write_the_work_folder_from_bash(self):
        for cmd in ("sed -i 's/a/b/' munka/a.txt", "sed -i.bak -e s/a/b/ munka/a.txt",
                    "perl -pi -e s/a/b/ munka/a.txt", "echo x > munka/a.txt", "echo x >> munka/a.txt",
                    "date | tee -a munka/log.txt", "cp /tmp/x munka/a.txt", "mv munka/a.txt /tmp/",
                    "rm -f munka/a.txt", "dd if=/dev/zero of=munka/a.txt", "truncate -s0 munka/a.txt",
                    "bash -c 'echo x > munka/a.txt'", "cd munka && sed -i s/a/b/ a.txt",
                    "touch munka/new.txt"):
            self.assertEqual(self.decide("Bash", {"command": cmd}), "deny", cmd)

    def test_role_files_cannot_be_edited_from_bash(self):
        for cmd in ("sed -i s/kiado/x/ agy/szerepek/fejleszto.md", "echo '{}' > mentat.json",
                    "cp /tmp/s .claude/settings.json"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto", "w"), "deny", cmd)

    def test_reading_and_writing_elsewhere_stay_allowed(self):
        for cmd in ("sed -n 1p munka/a.txt", "cat munka/a.txt > agy/x", "cp munka/a.txt agy/x",
                    "grep a munka/a.txt 2>&1 | tee /dev/null", "echo hi > agy/x.md", "ls munka >/dev/null"):
            self.assertEqual(self.decide("Bash", {"command": cmd}), "allow", cmd)


if __name__ == "__main__":
    unittest.main()
