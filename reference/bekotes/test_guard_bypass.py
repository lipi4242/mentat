"""Role guard hardening: bypass probes (cwd, Write, push forms, symlinks, case)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import subprocess
import sys
import unittest

from test_guard import GUARD, GuardBase


class GuardBypass(GuardBase):
    def test_cwd_moved_does_not_disable_guard(self):
        self.assertEqual(self.decide("Bash", {"command": "git push origin main"}, cwd="/tmp"), "deny")

    def test_write_is_covered_by_edit_rules(self):
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["roles"]["installed"].append("kiado")
        (self.root / "mentat.json").write_text(json.dumps(doc))
        self.assertEqual(self.decide("Write", {"file_path": "agy/x.md"}, "kiado", "k"), "deny")
        self.assertEqual(self.decide("MultiEdit", {"file_path": "agy/x.md"}, "kiado", "k"), "deny")
        self.assertEqual(self.decide("NotebookEdit", {"notebook_path": "agy/x.ipynb"}, "kiado", "k"), "deny")

    def test_push_bypasses_closed(self):
        for cmd in ("git push origin HEAD:main", "git push", "git push origin", "git -C . push origin main",
                    "git -c a=b push origin HEAD:master", "GIT_X=1 git push origin HEAD:main"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto", "f"), "deny", cmd)
        self.assertEqual(self.decide("Bash", {"command": "git -C . push origin feat/x"}, "fejleszto", "f"), "allow")

    def test_symlink_escape(self):
        (self.root / "munka").mkdir()
        (self.root / "link").symlink_to(self.root / "munka")
        self.assertEqual(self.decide("Edit", {"file_path": "link/a.txt"}), "deny")
        self.assertEqual(self.decide("Edit", {"file_path": "munka/../munka/a.txt"}), "deny")

    def test_grep_path_uses_read_rules(self):
        self.assertEqual(self.decide("Grep", {"pattern": "x", "path": "munka/bank/"}, "fejleszto", "g"), "deny")

    def test_builtin_protects_role_files(self):
        for path in ("agy/szerepek/fejleszto.md", ".mentat/local.json", "mentat.json", ".claude/settings.json"):
            self.assertEqual(self.decide("Edit", {"file_path": path}, "fejleszto", "b"), "deny", path)

    def test_pinned_role_must_still_be_installed(self):
        pin = self.root / ".mentat" / "szerep"
        pin.mkdir(parents=True)
        (pin / "p").write_text("kiado\n")  # kiado is not installed in ROLES
        self.assertEqual(self.decide("Read", {"file_path": "a"}, sid="p"), "deny")

    def test_invalid_stdin_denies(self):
        r = subprocess.run([sys.executable, str(GUARD)], input="{nope", capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_session_start_bad_manifest_says_deny(self):
        (self.root / "mentat.json").write_text("{broken")
        r = self.run_guard({}, None, ["--session-start"])
        self.assertIn("tilt", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])

    # --- fix round 2 ---
    def test_push_probes_denied_for_developer(self):
        for cmd in ("git push origin HEAD", "git push -f origin feat/x", "git push -u origin",
                    "git push origin HEAD:refs/heads/main", "git push origin x:refs/heads/master",
                    "git --no-pager push origin main", "git --git-dir .git push origin main",
                    "git   push   origin   main", "git push --force-with-lease origin feat/x",
                    "git push --mirror origin", "git push --all origin", "git push origin +feat/x",
                    "env FOO=1 git push origin main", "/usr/bin/git push origin HEAD:MAIN"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto", "f"), "deny", cmd)

    def test_push_branch_allowed_for_developer(self):
        for cmd in ("git push origin feat/x", "git push -u origin feat/x", "git --no-pager status",
                    "git push origin feat/x:feat/y", "git commit -m 'push main'"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto", "f"), "allow", cmd)

    def test_assistant_push_variants_denied(self):
        for cmd in ("git --no-pager push", "git   push", "git -C . push origin x"):
            self.assertEqual(self.decide("Bash", {"command": cmd}), "deny", cmd)

    def test_builtin_paths_case_insensitive(self):
        for path in ("MENTAT.JSON", ".Mentat/local.json", ".claude/Settings.json", "agy/SZEREPEK/x.md"):
            self.assertEqual(self.decide("Edit", {"file_path": path}, "fejleszto", "c"), "deny", path)

    # --- fix round 3 ---
    def test_round3_probes(self):
        for cmd in ("git push origin @", "git push origin refs/heads/*:refs/heads/*",
                    "git --attr-source HEAD push origin main", "git status & git push origin main"):
            self.assertEqual(self.decide("Bash", {"command": cmd}, "fejleszto", "r3"), "deny", cmd)
        self.assertEqual(self.decide("Bash", {"command": "git --attr-source HEAD push origin feat/x"},
                                     "fejleszto", "r3"), "allow")


if __name__ == "__main__":
    unittest.main()
