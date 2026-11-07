"""check before `git add`, the guard's implicit Read denies, history attribution."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import shutil
import subprocess
import sys
import unittest

from _bekotes_repo import BIZ, bk, commit_all, done, env, fill_map, leltar, make_agent, szerepek, write


class Uncommitted(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        for r in (leltar(self.root), szerepek(self.root),
                  bk(self.root, "blokk", "--repo", ".", "--business", "zoldag")):
            self.assertEqual(r.returncode, 0, r.stderr)
        fill_map(self.root)  # nothing committed or added

    def check(self):
        return bk(self.root, "check", "--repo", ".", "--business", "zoldag")

    def test_clean_uncommitted_tree_passes(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_forbidden_and_personal_data_fail_before_git_add(self):
        write(self.root, BIZ + "/masolat/ugyfelek/private.json", "{}\n")
        write(self.root, BIZ + "/jegyzet.md", "anna@example.com\n")
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL tiltott: %s/masolat/ugyfelek/private.json" % BIZ, r.stdout)
        self.assertIn("FAIL szuro: %s/jegyzet.md" % BIZ, r.stdout)


class History(unittest.TestCase):
    def test_spoofed_plus_header_does_not_move_attribution(self):
        root = make_agent()
        self.addCleanup(shutil.rmtree, root, True)
        done(root)
        write(root, BIZ + "/x.md", "++ b/README.md\nanna@example.com\n")
        commit_all(root)
        write(root, BIZ + "/x.md", "tiszta\n")
        commit_all(root)
        out = bk(root, "check", "--repo", ".", "--business", "zoldag").stdout
        self.assertIn("történet:%s/x.md" % BIZ, out)
        self.assertNotIn("történet:README.md", out)


    def test_added_line_looking_like_a_header_is_still_scanned(self):
        root = make_agent()
        self.addCleanup(shutil.rmtree, root, True)
        done(root)
        write(root, BIZ + "/y.md", "++ anna@example.com\n")
        commit_all(root)
        write(root, BIZ + "/y.md", "tiszta\n")
        commit_all(root)
        out = bk(root, "check", "--repo", ".", "--business", "zoldag").stdout
        self.assertIn("történet:%s/y.md" % BIZ, out)


class GuardForbiddenReads(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.assertEqual(szerepek(self.root).returncode, 0)

    def decide(self, path, role=None):
        e = dict(env(self.root), CLAUDE_PROJECT_DIR=str(self.root))
        if role:
            e["MENTAT_ROLE"] = role
        payload = {"session_id": "s-" + (role or "x"), "cwd": str(self.root), "tool_name": "Read",
                   "tool_input": {"file_path": path}}
        r = subprocess.run([sys.executable, str(self.root / ".mentat/bin/bekotes/szerep_guard.py")],
                           input=json.dumps(payload), capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else "allow"

    def test_forbidden_globs_deny_read_for_every_role(self):
        for role in (None, "fejleszto", "backlog-manager"):
            for p in ("munka/zoldag-web/ugyfelek/private.json", "munka/zoldag-web/UGYFELEK/private.json",
                      "munka/zoldag-web/a/b/foto-001.jpg",
                      os.path.join(str(self.root), "munka/zoldag-web/ugyfelek/private.json")):
                self.assertEqual(self.decide(p, role), "deny", (role, p))
            self.assertEqual(self.decide("munka/zoldag-web/README.md", role), "allow", role)


if __name__ == "__main__":
    unittest.main()
