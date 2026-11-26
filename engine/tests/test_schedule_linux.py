#!/usr/bin/env python3
"""schedule on Linux: the systemd units, the install commands and the cron line stay
byte-for-byte what they were before the macOS backend existed.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _engine_isolation import IsolatedTestCase  # noqa: E402
from anytime_engine import schedule  # noqa: E402

PY = "/usr/bin/python3"
SERVICE = ("[Unit]\nDescription=Mentat engine hourly tick (bot)\n\n[Service]\nType=oneshot\n"
           "WorkingDirectory={root}\nEnvironment=\"ANYTIME_REPO_ROOT={root}\"\n"
           "Environment=\"ANYTIME_PLUGINS=a.concerns\"\n"
           "ExecStart=/usr/bin/python3 \"-m\" \"anytime_engine.tick\" \"hourly\"\n")
TIMER = ("[Unit]\nDescription=Mentat engine hourly tick schedule (bot)\n\n[Timer]\n"
         "OnCalendar=hourly\n# Persistent: a tick missed while the box was off runs at next boot.\n"
         "Persistent=true\nUnit=anytime-bot-hourly.service\n\n[Install]\nWantedBy=timers.target\n")
CRON = ("0 * * * * cd {root} && mkdir -p data/state data/logs && ANYTIME_REPO_ROOT={root} "
        "ANYTIME_PLUGINS=a.concerns flock -n {root}/data/state/tick.lock /usr/bin/python3 -m "
        "anytime_engine.tick hourly >> {root}/data/logs/anytime-tick.log 2>&1")


class TestLinuxUnchanged(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.fmt = {"root": self.root.resolve()}
        patcher = mock.patch.object(schedule.sys, "executable", PY)
        patcher.start()
        self.addCleanup(patcher.stop)
        schedule.PLATFORM = "linux"   # what a box reports, whatever host runs the test

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = schedule.main(argv)
        return rc, out.getvalue()

    def test_units_are_byte_identical(self):
        units = schedule.render_systemd("bot", "hourly", "hourly", "a.concerns")
        self.assertEqual(units, {"anytime-bot-hourly.service": SERVICE.format(**self.fmt),
                                 "anytime-bot-hourly.timer": TIMER})

    def test_cron_line_is_byte_identical_and_keeps_flock(self):
        rc, out = self.run_main(["--plugins", "a.concerns", "--cron"])
        self.assertEqual((rc, out), (0, CRON.format(**self.fmt) + "\n"))

    def test_install_writes_systemd_units_and_enables_with_systemctl(self):
        unit_dir = self.root / "units"
        with mock.patch.object(schedule.subprocess, "run") as run:
            rc, out = self.run_main(["--plugins", "a.concerns", "--name", "bot",
                                     "--install", "--unit-dir", str(unit_dir)])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(p.name for p in unit_dir.iterdir()),
                         ["anytime-bot-hourly.service", "anytime-bot-hourly.timer"])
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["systemctl", "--user", "daemon-reload"],
                          ["systemctl", "--user", "enable", "--now", "anytime-bot-hourly.timer"]])
        self.assertIn("enabled anytime-bot-hourly.timer", out)
        self.assertNotIn("launchctl", out)


if __name__ == "__main__":
    unittest.main()
