"""06-flotta 2. kör: a wait-up csak új processz-generációt fogad el
visszajövésnek; a join kitölti az agy/motor mezőket; a javító sorok pontosak;
az init a teljes hátralévő sort kiírja. A TERMELŐ kódot hívja."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _hermetic  # noqa: F401,E402  (első import: HOME → tmp, lásd tests/_hermetic.py)

from test_zero_touch_ops import Home  # noqa: E402
from fleet import agentctl, signals  # noqa: E402


def _fake_run(cmd):
    """A join systemctl-lépései a futtató gépet nem érhetik el (hermetikus teszt)."""
    out = "active\n" if cmd[-2:-1] == ["is-active"] else ""
    return subprocess.CompletedProcess(cmd, 0, out, "")


def _proc(pid, started):
    return signals.Signal("process", "up", "", {"pid": pid, "started_s": started})


DOWN = signals.Signal("process", "down", "")


class TestWaitUpGeneration(Home):
    def setUp(self):
        super().setUp()
        self.addCleanup(agentctl.clear_generation, "probe")

    def _wait(self, seq, **kw):
        it = iter(seq)
        return agentctl.wait_up(self.e, timeout_s=60, home=self.home, sig=lambda e: next(it),
                                sleep=lambda s: None, clock=iter(range(0, 1000, 5)).__next__, **kw)

    def test_old_generation_still_dying_is_not_back(self):
        # a stop előtt pid 10 futott; a leállás közben még látszik, majd lemegy, majd új pid jön
        agentctl.mark_generation(self.e["agent"], {"pid": 10, "started_s": 100})
        r = self._wait([_proc(10, 100), DOWN, _proc(20, 400)])
        self.assertTrue(r["ok"]); self.assertIn("új processz", r["notes"][-1])
        self.assertIn("pid 20", r["notes"][-1])

    def test_old_generation_forever_means_not_back(self):
        agentctl.mark_generation(self.e["agent"], {"pid": 10, "started_s": 100})
        r = self._wait([_proc(10, 100)] * 30)
        self.assertFalse(r["ok"]); self.assertIn("NEM jött vissza", r["notes"][-1])

    def test_stop_records_generation_of_running_process(self):
        with mock.patch.object(agentctl, "_generation", return_value={"pid": 7, "started_s": 9}):
            agentctl.stop(self.e, run=lambda c: subprocess.CompletedProcess(c, 0, "", ""), home=self.home)
        self.assertEqual(agentctl.read_generation(self.e["agent"]), {"pid": 7, "started_s": 9})

    def test_no_mark_and_already_up_says_so_immediately(self):
        agentctl.clear_generation(self.e["agent"])
        r = self._wait([_proc(5, 50)])
        self.assertTrue(r["ok"]); self.assertIn("már fut", r["notes"][-1])


class TestComponentsDetected(unittest.TestCase):
    def test_join_fills_brain_and_reducer_from_repo(self):
        import tempfile
        from fleet import join
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "AGENTS.md").write_text("# agy\n")
            (repo / "anytime_engine").mkdir()
            (repo / "anytime_engine" / "__init__.py").write_text('__version__ = "0.3.0"\n')
            (repo / "mentat.json").write_text(json.dumps(
                {"schema": 1, "components": {"brain": {"root": "agy"}, "engine": {"path": "anytime_engine"}}}))
            r = join.join(repo, agent="probe", unit_dir=repo / "u", host="b", run=_fake_run)
            c = r["manifest"]["components"]
            self.assertEqual(c["reducer"], "0.3.0")
            self.assertTrue(c["brain"])
            r = join.join(repo, agent="probe", brain="9", unit_dir=repo / "u", host="b", run=_fake_run)
            self.assertEqual(r["manifest"]["components"]["brain"], "9")

    def test_nothing_found_stays_null(self):
        import tempfile
        from fleet import join
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            r = join.join(Path(d), agent="probe", run=_fake_run)
            self.assertIsNone(r["manifest"]["components"]["brain"])
            self.assertIsNone(r["manifest"]["components"]["reducer"])


class TestInitHints(Home):
    def setUp(self):
        super().setUp()
        self.repo = self.work
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        p = mock.patch.dict(os.environ, {"HOME": str(self.home)}); p.start(); self.addCleanup(p.stop)
        for k in ("FLEET_REGISTRY", "FLEET_HOST", "CLAUDE_CODE_OAUTH_TOKEN"):
            os.environ.pop(k, None)

    def _init(self, **kw):
        from fleet.init import init
        return init("mini", repo=self.repo, home=self.home, claude_bin=self.fb.claude,
                    tmux_bin=kw.pop("tmux_bin", self.fb.tmux), host_name="boxx", **kw)

    def test_tmux_hint_has_apt_update(self):
        with mock.patch("shutil.which", side_effect=lambda x: "/x" if x == "apt-get" else None):
            r = self._init(tmux_bin=self.home / "nincs")
        self.assertIn("sudo apt-get update && sudo apt-get install -y tmux", r["summary"])

    def test_auth_hint_uses_systemd_env_when_token_there(self):
        (self.fb.dir / "logged-out").write_text("")
        with mock.patch("fleet.claude_auth.systemd_token", return_value="sk-secret-9"):
            r = self._init()
        self.assertIn("fleet auth mini --from-systemd", r["summary"])
        self.assertNotIn("sk-secret-9", r["summary"])

    def test_failed_summary_lists_the_whole_remaining_sequence(self):
        (self.fb.dir / "logged-out").write_text("")
        r = self._init(tmux_bin=self.home / "nincs")
        s = r["summary"]
        self.assertIn("hátra", s)
        for step in ("fleet auth mini", "fleet setup mini", "fleet wait-up mini"):
            self.assertIn(step, s)
        self.assertLess(s.index("fleet auth mini"), s.index("fleet setup mini"))

    def test_ok_summary_has_setup_and_probe(self):
        r = self._init()
        self.assertEqual(r["status"], "ok", r["summary"])
        self.assertIn("fleet setup mini", r["summary"]); self.assertIn("fleet wait-up mini", r["summary"])


class TestSystemdToken(unittest.TestCase):
    def test_systemd_token_strips_quotes(self):
        from fleet import claude_auth
        cp = subprocess.CompletedProcess([], 0, "A=1\nCLAUDE_CODE_OAUTH_TOKEN='sk-x'\n", "")
        self.assertEqual(claude_auth.systemd_token(run=lambda c: cp), "sk-x")
        self.assertIsNone(claude_auth.systemd_token(run=lambda c: subprocess.CompletedProcess([], 1, "", "")))


if __name__ == "__main__":
    unittest.main()
