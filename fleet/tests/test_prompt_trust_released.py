"""A prompt-drift restart két őre (CISO-követés a #170-hez). Mindkettő a javítás nélkül piros:
  * kiadott = a HEAD az origin alapágának őse; a helyben commitolt, de ki nem adott változás
    (az ágens maga is commitolhat) és a remote nélküli repó csak jelzés, restart nincs
  * az origin/HEAD csak refs/remotes/origin/ alá mutathat; a git hívásokban az fsmonitor ki van
    kapcsolva (a repó-lokális fsmonitor parancsot futtatna a reconcile alatt)
  * a settings.json-t abból a bájtsorból parse-oljuk, amit a biztonságos olvasás beolvasott:
    a beolvasás és egy második olvasás közti csere (TOCTOU) nem hat a döntésre."""
from __future__ import annotations
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401  (repo konvenció)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drift_box import T0, Box  # noqa: E402

from fleet import prompt_safe_read, prompt_trust  # noqa: E402


class TestReleased(Box):
    def assert_alert_only(self):
        self.assertEqual(self.restarts(), [])
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("csak-jelzes", self.alerts[0])

    def test_pushed_change_restarts(self):
        self.round(T0)
        self.change("CLAUDE.md", "kiadva\n")
        self.settle(T0 + 300)
        self.assertEqual(len(self.restarts()), 1)

    def test_local_commit_not_on_origin_alerts_only(self):
        self.round(T0)
        self.change("CLAUDE.md", "helyben commitolva\n", push=False)
        self.settle(T0 + 300)
        self.assert_alert_only()

    def test_repo_without_origin_alerts_only(self):
        self.git("remote", "remove", "origin")
        self.round(T0)
        self.change("CLAUDE.md", "remote nélkül\n", push=False)
        self.settle(T0 + 300)
        self.assert_alert_only()

    def test_released_helper(self):
        self.assertTrue(prompt_trust.released(self.wd))
        self.change("AGENTS.md", "x\n", push=False)
        self.assertFalse(prompt_trust.released(self.wd))
        self.git("push", "-q", "origin", "HEAD")
        self.assertTrue(prompt_trust.released(self.wd))


class TestGitHardening(Box):
    def test_origin_head_outside_remote_namespace_is_not_released(self):
        branch = subprocess.run(["git", "-C", str(self.wd), "symbolic-ref", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/heads/" + branch)
        self.change("AGENTS.md", "helyi\n", push=False)
        self.assertFalse(prompt_trust.released(self.wd))

    def test_every_git_call_disables_fsmonitor(self):
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            return subprocess.run(cmd, **kw)
        prompt_trust.released(self.wd, run=run)
        prompt_trust.git_problems(self.wd, ["CLAUDE.md"], run=run)
        self.assertTrue(seen)
        for cmd in seen:
            self.assertIn("core.fsmonitor=false", cmd[cmd.index("-c") + 1:cmd.index("-c") + 2], cmd)

    def test_repo_local_fsmonitor_command_does_not_run(self):
        mark = self.d / "fsmonitor-futott"
        hook = self.d / "fsmon.sh"
        hook.write_text("#!/bin/sh\ntouch '%s'\n" % mark)
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        prompt_trust.git_problems(self.wd, ["CLAUDE.md"])
        prompt_trust.released(self.wd)
        self.assertFalse(mark.exists(), "a repó-lokális fsmonitor parancs lefutott")


class TestSingleRead(Box):
    def swap_after_read(self, p: Path, later: str):
        real = prompt_safe_read.os.read

        def read(fd, n):
            data = real(fd, n)
            p.write_text(later)          # a biztonságos olvasás UTÁN cserélődik a fájl
            return data
        return mock.patch.object(prompt_safe_read.os, "read", read)

    def test_load_parses_the_bytes_already_read(self):
        p = self.wd / ".claude" / "settings.json"
        p.write_text('{"hooks": {}}')
        with self.swap_after_read(p, "{nem json"):
            obj, bad = prompt_trust._load(p)
        self.assertFalse(bad)
        self.assertEqual(obj, {"hooks": {}})

    def test_hooks_fingerprint_from_the_same_read(self):
        p = self.wd / ".claude" / "settings.json"
        p.write_text('{"hooks": {}}')
        want = prompt_trust.hooks_fp(p)
        with self.swap_after_read(p, '{"hooks": {"PreToolUse": [{"command": "x"}]}}'):
            self.assertEqual(prompt_trust.hooks_fp(p), want)

    def test_read_bytes_markers(self):
        self.assertEqual(prompt_safe_read.read_bytes(self.d / "nincs"), (None, None))
        os.mkfifo(self.d / "fifo")
        mark, data = prompt_safe_read.read_bytes(self.d / "fifo")
        self.assertTrue(mark.startswith("nem-fajl"))
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
