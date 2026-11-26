#!/usr/bin/env python3
"""tick --lock: of two ticks started at once exactly one runs; the other says so in one
line, exits 0 and stamps nothing. A Python lock, so it works where flock(1) does not
exist (macOS). Without --lock nothing changes.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
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
from anytime_engine import tick, ticklock  # noqa: E402
from anytime_engine.assembler import clear_providers  # noqa: E402
from anytime_engine.registry import Concern, clear, register  # noqa: E402

SRC = Path(tick.__file__).resolve().parent.parent   # src/ here, the repo root when vendored
PLUGIN = '''from anytime_engine.registry import Concern, register
register(Concern(name="slow", description="d", triggers=["hourly"],
                 should_run=lambda s: True, action="slow", staleness_minutes=60))
'''


class TestLockInProcess(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        clear()
        clear_providers()
        register(Concern(name="todos", description="d", triggers=["hourly"],
                         should_run=lambda s: True, action="todos", staleness_minutes=60))
        self.hb = self.root / "data" / "state" / "orchestrator-heartbeat.json"

    def tearDown(self):
        clear()
        clear_providers()
        super().tearDown()

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = tick.main(list(argv) + ["--no-discover"])
        return rc, out.getvalue(), err.getvalue()

    def test_a_busy_lock_skips_the_tick_in_one_line_without_a_stamp(self):
        with ticklock.held() as got:
            self.assertTrue(got)
            rc, out, err = self.main("hourly", "--lock")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("another tick is running", err)
        self.assertFalse(self.hb.exists())

    def test_a_free_lock_runs_and_releases(self):
        rc, _, _ = self.main("hourly", "--lock")
        self.assertEqual(rc, 0)
        self.assertTrue(self.hb.exists())
        with ticklock.held() as got:
            self.assertTrue(got)

    def test_without_lock_the_tick_ignores_the_lock_as_before(self):
        with ticklock.held():
            rc, _, _ = self.main("hourly")
        self.assertEqual(rc, 0)
        self.assertTrue(self.hb.exists())


class TestTwoProcesses(IsolatedTestCase):
    def test_of_two_ticks_started_at_once_exactly_one_runs(self):
        (self.root / "slowplug").mkdir()
        (self.root / "slowplug" / "__init__.py").write_text(PLUGIN)
        env = dict(os.environ, PYTHONPATH=f"{SRC}{os.pathsep}{self.root}",
                   HOME=str(self.root / "home"))
        cmd = [sys.executable, "-m", "anytime_engine.tick", "hourly", "--lock",
               "--plugins", "slowplug", "--exec", "echo ran >> ran.txt; sleep 2"]
        procs = [subprocess.Popen(cmd, cwd=self.root, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for _ in range(2)]
        results = [p.communicate(timeout=30) for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0], results)
        self.assertEqual((self.root / "ran.txt").read_text().splitlines(), ["ran"], results)
        self.assertEqual(sum("another tick is running" in e for _, e in results), 1, results)


if __name__ == "__main__":
    unittest.main()
