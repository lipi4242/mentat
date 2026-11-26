#!/usr/bin/env python3
"""schedule on macOS: a per-user LaunchAgent (RunAtLoad + StartInterval) instead of a
systemd timer, --uninstall that leaves nothing behind, and no flock anywhere (macOS has
none; the tick's own --lock keeps two ticks apart). launchctl is a fake: no test loads
a real LaunchAgent.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import os
import plistlib
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _engine_isolation import IsolatedTestCase  # noqa: E402
from anytime_engine import launchd, schedule  # noqa: E402

LABEL = "ai.mentat.anytime-bot-hourly"


class _MacCase(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        schedule.PLATFORM = "darwin"
        self.calls: list[list[str]] = []
        launchd.RUNNER = lambda cmd: self.calls.append(list(cmd)) or 0
        self.agents = self.root / "LaunchAgents"

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = schedule.main(list(argv) + ["--unit-dir", str(self.agents)])
        return rc, out.getvalue() + err.getvalue()

    def install(self):
        return self.run_main("--plugins", "a.concerns", "--name", "bot", "--install")


class TestInstall(_MacCase):
    def test_install_writes_a_launch_agent_that_ticks_hourly_while_awake(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        path = self.agents / f"{LABEL}.plist"
        agent = plistlib.loads(path.read_bytes())
        self.assertEqual(agent["Label"], LABEL)
        self.assertIs(agent["RunAtLoad"], True)
        self.assertEqual(agent["StartInterval"], 3600)
        self.assertNotIn("KeepAlive", agent)   # a tick exiting 3 (unhandled) is not re-run
        self.assertEqual(agent["WorkingDirectory"], str(self.root.resolve()))
        self.assertEqual(agent["ProgramArguments"][1:],
                         ["-m", "anytime_engine.tick", "hourly", "--lock"])
        self.assertEqual(agent["EnvironmentVariables"]["ANYTIME_PLUGINS"], "a.concerns")
        self.assertTrue(agent["StandardOutPath"].endswith("data/logs/anytime-tick.log"))
        self.assertTrue((self.root / "data" / "logs").is_dir())   # launchd will not create it
        self.assertEqual(self.calls[-1], ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])
        self.assertIn(f"enabled {LABEL}", out)

    def test_reinstall_unloads_the_old_agent_first(self):
        self.install()
        self.calls.clear()
        self.install()
        self.assertEqual(self.calls[0], ["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
        self.assertEqual(self.calls[1][:2], ["launchctl", "bootstrap"])

    def test_no_enable_only_writes(self):
        rc, _ = self.run_main("--plugins", "a.concerns", "--name", "bot", "--install", "--no-enable")
        self.assertEqual(rc, 0)
        self.assertTrue((self.agents / f"{LABEL}.plist").is_file())
        self.assertEqual(self.calls, [])

    def test_a_failed_bootstrap_is_not_reported_as_enabled(self):
        launchd.RUNNER = lambda cmd: 5 if "bootstrap" in cmd else 0
        rc, out = self.install()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(f"enabled {LABEL}", out)

    def test_dry_run_prints_the_plist_and_writes_nothing(self):
        rc, out = self.run_main("--plugins", "a.concerns", "--name", "bot")
        self.assertEqual(rc, 0)
        self.assertIn("<key>StartInterval</key>", out)
        self.assertIn("launchctl bootstrap", out)
        self.assertFalse(self.agents.exists())
        self.assertEqual(self.calls, [])


class TestUninstall(_MacCase):
    def test_uninstall_leaves_no_trace(self):
        self.install()
        self.calls.clear()
        rc, out = self.run_main("--name", "bot", "--uninstall")
        self.assertEqual(rc, 0, out)
        self.assertEqual(list(self.agents.iterdir()), [])
        self.assertEqual(self.calls, [["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"]])

    def test_uninstall_when_nothing_is_installed_is_quiet_success(self):
        launchd.RUNNER = lambda cmd: 3   # bootout of an agent that is not loaded
        rc, out = self.run_main("--name", "bot", "--uninstall")
        self.assertEqual(rc, 0, out)


class TestNoFlockOnMac(_MacCase):
    def test_nothing_generated_for_macos_mentions_flock(self):
        _, plan = self.run_main("--plugins", "a.concerns", "--name", "bot")
        _, cron = self.run_main("--plugins", "a.concerns", "--cron")
        self.assertNotIn("flock", plan + cron)
        self.assertIn("anytime_engine.tick hourly --lock", cron)


if __name__ == "__main__":
    unittest.main()
