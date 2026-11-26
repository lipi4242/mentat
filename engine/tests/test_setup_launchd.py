#!/usr/bin/env python3
"""setup on macOS: `setup --install` puts the LaunchAgent in place (not systemd units),
names it in the report, gives no Linux-only advice, and `setup --doctor` checks the
LaunchAgent. launchctl is a fake.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_setup import SetupCase  # noqa: E402
from anytime_engine import launchd, schedule  # noqa: E402


class MacSetup(SetupCase):
    def setUp(self):
        super().setUp()
        schedule.PLATFORM = "darwin"
        launchd.RUNNER = lambda cmd: 0

    def install(self):
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install")
        self.assertEqual(rc, 0, out)
        return out

    def test_install_writes_the_launch_agent_and_names_it(self):
        out = self.install()
        plists = [p.name for p in self.units.iterdir()]
        self.assertEqual(len(plists), 1, plists)
        self.assertTrue(plists[0].startswith("ai.mentat.anytime-") and plists[0].endswith("-hourly.plist"))
        self.assertIn(plists[0], out)
        self.assertNotIn("loginctl", out)

    def test_doctor_checks_the_launch_agent(self):
        self.install()
        rc, out = self.run_setup("--doctor")
        self.assertEqual((rc, out.count("OK ")), (0, 1), out)
        next(self.units.iterdir()).unlink()
        rc, out = self.run_setup("--doctor")
        self.assertEqual(rc, 1)
        self.assertIn("MISSING ai.mentat.anytime-", out)


if __name__ == "__main__":
    unittest.main()
