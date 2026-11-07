"""F-39 for 0.3.0 users: `szerep_hook.py --harden` adds onFailure "block" and a timeout to the
guard's PreToolUse handler, idempotently, and touches nothing else in the settings.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import szerep_hook

HERE = pathlib.Path(__file__).resolve().parent
OLD_GUARD = ('[ -f "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_guard.py ] || { echo "szerep-őr hiányzik: '
             'futtasd a BEKOTES 0. lépését" >&2; exit 0; }; python3 "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_guard.py')
SETTINGS = {"permissions": {"allow": ["Bash(ls)"]}, "model": "opus",
            "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": OLD_GUARD}]},
                                     {"matcher": "Bash", "hooks": [{"type": "command", "command": "./mine.sh"}]}],
                      "SessionStart": [{"hooks": [{"type": "command", "command": OLD_GUARD + " --session-start"}]}]}}


def harden(repo):
    return subprocess.run([sys.executable, str(HERE / "szerep_hook.py"), "--harden", "--repo", str(repo)],
                          capture_output=True, text=True)


class Harden(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / ".claude").mkdir()
        self.path = self.repo / ".claude" / "settings.json"
        self.path.write_text(json.dumps(SETTINGS, indent=2))

    def test_only_the_guard_handler_changes_and_twice_is_once(self):
        r = harden(self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads(self.path.read_text())
        guard = s["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual((guard["onFailure"], guard["timeout"]), ("block", 10))
        self.assertEqual(guard["command"], szerep_hook.GUARD_PRE)  # the 0.3.0 exit-0 line is replaced
        expect = json.loads(json.dumps(SETTINGS))
        expect["hooks"]["PreToolUse"][0]["hooks"][0].update(onFailure="block", timeout=10,
                                                             command=szerep_hook.GUARD_PRE)
        self.assertEqual(s, expect)  # the user's hook, permissions, model, SessionStart: untouched
        once = self.path.read_text()
        r = harden(self.repo)
        self.assertEqual((r.returncode, self.path.read_text()), (0, once))
        self.assertIn("0", r.stdout)

    def test_a_missing_guard_script_no_longer_passes(self):  # a 0.3.0 line: exit 0 = success
        def run(cmd):
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.repo))  # no .mentat/: a fresh clone
            payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}})
            r = subprocess.run(["/bin/sh", "-c", cmd], input=payload, capture_output=True, text=True, env=env)
            return r.returncode, r.stdout.strip()
        self.assertEqual(run(OLD_GUARD), (0, ""))  # the 0.3.0 line: a silent allow
        harden(self.repo)
        cmd = json.loads(self.path.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        rc, out = run(cmd)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_the_write_is_atomic(self):  # CISO, #71: tmp + rename, never a half file
        from unittest import mock
        before = self.path.read_text()
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                szerep_hook.harden(self.repo)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["settings.json"])

    def test_no_guard_or_broken_file_changes_nothing(self):
        plain = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "./mine.sh"}]}]}}
        self.path.write_text(json.dumps(plain))
        before = self.path.read_text()
        self.assertEqual(harden(self.repo).returncode, 0)
        self.assertEqual(self.path.read_text(), before)
        self.path.write_text("{nem json")
        r = harden(self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.path.read_text(), "{nem json")


if __name__ == "__main__":
    unittest.main()
