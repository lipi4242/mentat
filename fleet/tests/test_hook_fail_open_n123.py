"""F-39 follow-ups (CISO, fleet #64): N1 the user-level PreToolUse hooks (~/.claude or the
agent's ~/.claude-<account>) run for every agent and are checked too; N2 an unmeasurable
Claude Code version is not a silent green; N3 the version is the unit's binary
(~/.local/bin/claude), not whatever `claude` PATH finds. Production code: hookguard, doctor.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, hookguard  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402

OPEN = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 /u/h.py"}]}]}}
KW = dict(unit_active="active", unit_enabled="enabled", drop_in=True, bridge_installed=None,
          bridge_current="x", locked=False)


def fake_claude(text):
    d = Path(tempfile.mkdtemp()) / "claude"
    d.write_text("#!/bin/sh\necho '%s'\n" % text)
    d.chmod(0o755)
    return d


class N1UserLevel(unittest.TestCase):
    def test_user_settings_of_the_agents_claude_home_are_checked(self):
        e = _entry(workdir=tempfile.mkdtemp())
        home = Path(os.environ["HOME"]) / ".claude"
        home.mkdir(exist_ok=True)
        (home / "settings.json").write_text(json.dumps(OPEN))
        probs = doctor.hook_problems_for(e)
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("~/.claude", probs[0])
        (home / "settings.json").unlink()


class N2Unmeasurable(unittest.TestCase):
    def test_unknown_version_is_not_green(self):
        r = doctor.assess(_entry(), _m(), {}, claude_unknown="Claude Code verzió nem mérhető", **KW)
        self.assertFalse(r["ok"])
        self.assertTrue(any("nem mérhető" in u for u in r["unknown"]), r)


class N3UnitBinary(unittest.TestCase):
    def test_the_units_binary_is_measured_not_path(self):
        old = fake_claude("2.1.200 (Claude Code)")
        new = fake_claude("2.1.309 (Claude Code)")
        with mock.patch.dict(os.environ, {"PATH": str(new.parent) + os.pathsep + os.environ["PATH"]}), \
                mock.patch.object(hookguard, "CLAUDE_BIN", old):
            self.assertIn("2.1.200", hookguard.version_problem(hookguard.claude_version()))
        with mock.patch.object(hookguard, "CLAUDE_BIN", Path("/nincs/claude")):
            self.assertIsNone(hookguard.claude_version())


if __name__ == "__main__":
    unittest.main()
