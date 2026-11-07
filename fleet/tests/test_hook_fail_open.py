"""F-39: a PreToolUse command hook without `onFailure: "block"` fails OPEN (a crash, a
timeout or a missing python lets the tool call through), and Claude Code before 2.1.295
ignores the field. `fleet doctor` reports both as a problem (red), and fixes nothing.
Production code: fleet.hookguard and doctor.assess.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, hookguard  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402

GUARD = 'python3 -I "$CLAUDE_PROJECT_DIR"/.mentat/bin/bekotes/szerep_guard.py'


def repo(settings=None, local=None, raw=None):
    d = Path(tempfile.mkdtemp())
    (d / ".claude").mkdir()
    if settings is not None:
        (d / ".claude/settings.json").write_text(raw if raw is not None else json.dumps(settings))
    if local is not None:
        (d / ".claude/settings.local.json").write_text(json.dumps(local))
    return d


def pre(*handlers):
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": list(handlers)}]}}


class HookProblems(unittest.TestCase):
    def test_fail_open_handlers_are_named(self):
        bad = repo(pre({"type": "command", "command": GUARD, "timeout": 10}))
        self.assertEqual(len(hookguard.hook_problems(bad)), 1)
        self.assertIn("onFailure", hookguard.hook_problems(bad)[0])
        good = repo(pre({"type": "command", "command": GUARD, "timeout": 10, "onFailure": "block"}))
        self.assertEqual(hookguard.hook_problems(good), [])
        local = repo(pre({"type": "command", "command": GUARD, "onFailure": "block"}),
                     local=pre({"type": "command", "command": "python3 x.py"}))
        self.assertEqual(len(hookguard.hook_problems(local)), 1)  # settings.local.json counts too

    def test_no_settings_is_no_problem_but_a_broken_file_is(self):
        self.assertEqual(hookguard.hook_problems(repo()), [])
        self.assertEqual(len(hookguard.hook_problems(repo({}, raw="{nem json"))), 1)

    def test_claude_version(self):
        self.assertIn("2.1.295", hookguard.version_problem("2.1.200 (Claude Code)"))
        self.assertIsNone(hookguard.version_problem("2.1.309 (Claude Code)"))
        self.assertIsNone(hookguard.version_problem(None))  # not measurable: not a verdict

    def test_doctor_turns_it_red_without_fixing(self):
        e = _entry()
        kw = dict(unit_active="active", unit_enabled="enabled", drop_in=True, bridge_installed=None,
                  bridge_current="x", locked=False)
        ok = doctor.assess(e, _m(), {}, **kw)
        self.assertTrue(ok["ok"], ok)
        r = doctor.assess(e, _m(), {}, hook_problems=["PreToolUse-hook fail-open"],
                          claude_problem="Claude Code 2.1.200", **kw)
        self.assertFalse(r["ok"])
        self.assertTrue(any("fail-open" in p for p in r["problems"]))
        self.assertTrue(any("2.1.200" in p for p in r["problems"]))

    def test_bridge_version_drift_is_a_warning_not_red(self):
        kw = dict(unit_active="active", unit_enabled="enabled", drop_in=True, locked=False)
        e = _entry(bridge={"unit": "x-telegram-bridge.service"})
        r = doctor.assess(e, _m(), {}, bridge_installed="2.0.1", bridge_current="2.1.0", **kw)
        self.assertTrue(r["ok"], r)
        self.assertTrue(any("híd-drift" in w for w in r["warnings"]))
        self.assertIn("⚠️", doctor.format_report([r]))


if __name__ == "__main__":
    unittest.main()
