"""mentat_model.py: switch one repo's agent to an OpenRouter model and back, safely."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_model.py"
MODEL = "deepseek/deepseek-v4.1-flash-1017"
KEY = "sk-or-v1-" + "a" * 64
# A stand-in for `claude -p`: answers from whatever model the repo's settings name,
# or from FAKE_ANSWER (e.g. a Claude model), or fails when FAKE_FAIL is set.
FAKE = """#!/usr/bin/env python3
import json, os, pathlib
env = json.loads(pathlib.Path('.claude/settings.local.json').read_text()).get('env', {}) \
    if pathlib.Path('.claude/settings.local.json').exists() else {}
m = os.environ.get('FAKE_ANSWER') or env.get('ANTHROPIC_MODEL', 'claude-opus-5-5')
print(json.dumps({'is_error': bool(os.environ.get('FAKE_FAIL')), 'result': 'ok', 'modelUsage': {m: {}}}))
"""


class Model(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.root = self.tmp / "agent"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        fake = self.tmp / "claude"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.env = dict(os.environ, MENTAT_CLAUDE=str(fake), MENTAT_KEY_FILE=str(self.tmp / "cfg" / "openrouter.env"))
        self.env.pop("FLEET_AGENT", None)

    def run_tool(self, *args, stdin=None, **extra):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args], capture_output=True,
                              text=True, input=stdin, env=dict(self.env, **extra))

    def settings(self):
        p = self.root / ".claude" / "settings.local.json"
        return json.loads(p.read_text()) if p.exists() else None

    def test_key_from_stdin_is_saved_0600_and_never_printed(self):
        r = self.run_tool("key", stdin=KEY + "\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn(KEY, r.stdout + r.stderr)
        f = self.tmp / "cfg" / "openrouter.env"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual(f.read_text(), "OPENROUTER_API_KEY=%s\n" % KEY)

    def test_key_that_is_not_openrouter_is_refused(self):
        self.assertEqual(self.run_tool("key", stdin="sk-ant-xyz\n").returncode, 2)
        self.assertFalse((self.tmp / "cfg" / "openrouter.env").exists())

    def test_use_without_key_refuses_and_writes_nothing(self):
        r = self.run_tool("use", MODEL)
        self.assertEqual(r.returncode, 2)
        self.assertIsNone(self.settings())

    def test_use_switches_every_alias_probes_and_keeps_the_file_ignored(self):
        self.run_tool("key", stdin=KEY)
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.local.json").write_text('{"permissions": {"allow": ["Bash(ls)"]}}')
        r = self.run_tool("use", MODEL)
        self.assertEqual(r.returncode, 0, r.stdout)
        s = self.settings()
        self.assertEqual(s["permissions"], {"allow": ["Bash(ls)"]})  # the user's own keys survive
        for a in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                  "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            self.assertEqual(s["env"][a], MODEL, a)
        self.assertEqual(s["env"]["ANTHROPIC_AUTH_TOKEN"], KEY)
        self.assertEqual(s["env"]["ANTHROPIC_API_KEY"], "")
        self.assertNotIn(KEY, r.stdout)
        self.assertIn("DATA  everything this agent reads", r.stdout)  # AG-10: what leaves, and where
        self.assertIn("Settings > Privacy", r.stdout)
        p = self.root / ".claude" / "settings.local.json"
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        for rel in (".claude/settings.local.json", ".mentat/model.env"):
            ok = subprocess.run(["git", "-C", str(self.root), "check-ignore", "-q", rel])
            self.assertEqual(ok.returncode, 0, rel)
        self.assertEqual((self.root / ".mentat" / "model.env").read_text(), "MENTAT_MODEL=%s\n" % MODEL)
        self.assertIn(MODEL, self.run_tool("status").stdout)

    def test_probe_answering_from_claude_rolls_back(self):
        self.run_tool("key", stdin=KEY)
        r = self.run_tool("use", MODEL, FAKE_ANSWER="claude-opus-5-5")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ROLLED BACK", r.stdout)
        self.assertIsNone(self.settings())
        self.assertFalse((self.root / ".mentat" / "model.env").exists())

    def test_failed_probe_restores_previous_settings_exactly(self):
        self.run_tool("key", stdin=KEY)
        (self.root / ".claude").mkdir()
        before = '{"permissions": {}}'
        (self.root / ".claude" / "settings.local.json").write_text(before)
        self.assertEqual(self.run_tool("use", MODEL, FAKE_FAIL="1").returncode, 1)
        self.assertEqual((self.root / ".claude" / "settings.local.json").read_text(), before)

    def test_unmeasured_model_needs_force(self):
        self.run_tool("key", stdin=KEY)
        self.assertEqual(self.run_tool("use", "z-ai/glm-5.3-flash").returncode, 2)
        self.assertEqual(self.run_tool("use", "z-ai/glm-5.3-flash", "--force", "--no-probe").returncode, 0)

    def test_committed_settings_file_is_refused(self):
        self.run_tool("key", stdin=KEY)
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.local.json").write_text("{}")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", ".claude/settings.local.json"], check=True)
        r = self.run_tool("use", MODEL)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already committed", r.stdout)
        self.assertEqual(self.settings(), {})

    def test_back_to_claude_removes_only_our_keys(self):
        self.run_tool("key", stdin=KEY)
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.local.json").write_text('{"env": {"MY_VAR": "1"}}')
        self.run_tool("use", MODEL)
        r = self.run_tool("use", "claude")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.settings(), {"env": {"MY_VAR": "1"}})
        self.assertFalse((self.root / ".mentat" / "model.env").exists())
        self.assertIn("Claude (default)", self.run_tool("status").stdout)

    def test_fleet_agent_schedules_its_own_restart_out_of_band(self):
        # the USER never types a command: the tool runs `systemd-run ... fleet restart <agent>`
        bindir, log = self.tmp / "bin", self.tmp / "calls"
        bindir.mkdir()
        for name in ("fleet", "systemd-run"):
            f = bindir / name
            f.write_text('#!/bin/sh\necho "%s $*" >> %s\n' % (name, log))
            f.chmod(0o755)
        self.run_tool("key", stdin=KEY)
        r = self.run_tool("use", MODEL, FLEET_AGENT="media-agent", PATH="%s:%s" % (bindir, os.environ["PATH"]))
        self.assertIn("RESTART in 20 s", r.stdout)
        self.assertRegex(log.read_text(), r"systemd-run --user --on-active=20 --unit mentat-model-restart-"
                                          r"media-agent-\d+ \S*fleet restart media-agent")

    def test_without_fleet_the_agent_asks_its_deployer(self):
        self.run_tool("key", stdin=KEY)
        r = self.run_tool("use", MODEL, FLEET_AGENT="media-agent", PATH="/usr/bin:/bin")
        self.assertIn("no `fleet` command", r.stdout)

    def test_interactive_agent_tells_the_user_in_words(self):
        self.run_tool("key", stdin=KEY)
        self.assertIn("close this session and open a new one", self.run_tool("use", MODEL).stdout)


if __name__ == "__main__":
    unittest.main()
