"""Prompt-drift szélei: két ágens egy körben EGY riasztás; settings.local.json
kívül; első körös mtime-tartalék; debounce; bukott systemctl után nincs hamis
„újraindultál"; az @include-feloldás nem tekint fájlnak említést, e-mailt, kódblokkot."""
from __future__ import annotations
import functools
import os
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drift_box import IDLE, T0, Box  # noqa: E402

from fleet import prompt_drift, prompt_files, reconcile  # noqa: E402
from fleet.registry import normalize  # noqa: E402


class TestEdges(Box):
    def test_two_agents_one_summary_alert(self):
        e2 = normalize({"agent": "probe-two", "workdir": str(self.wd), "host": "box"})
        self.agents.append(e2); self.gen["probe-two"] = 200
        self.round(T0)
        self.change("CLAUDE.md", "b\n")
        self.settle(T0 + 300)
        self.assertEqual(len(self.restarts()), 2)
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("probe-agent", self.alerts[0]); self.assertIn("probe-two", self.alerts[0])

    def test_settings_local_change_no_restart(self):
        self.round(T0)
        (self.wd / ".claude" / "settings.local.json").write_text('{"permissions": {"allow": ["Bash"]}}')
        self.settle(T0 + 300)
        self.assertEqual(self.restarts(), [])

    def test_settings_json_non_hook_change_restarts(self):
        self.change(".claude/settings.json", "{}"); self.backdate()
        self.round(T0)
        self.change(".claude/settings.json", '{"model": "x"}')
        self.settle(T0 + 300)
        self.assertEqual(len(self.restarts()), 1)

    def test_first_round_file_newer_than_process_start_is_drift(self):
        os.utime(self.wd / "AGENTS.md", (T0 - 10, T0 - 10))      # a processz T0-50-kor indult
        lines = self.settle(T0)
        self.assertEqual(len(self.restarts()), 1, lines)
        self.assertIn("AGENTS.md", self.sent[0])

    def test_first_round_busy_keeps_stale_mark_until_idle(self):
        os.utime(self.wd / "AGENTS.md", (T0 - 10, T0 - 10))
        self.settle(T0, age=5)
        self.assertEqual(self.restarts(), [])
        self.round(T0 + prompt_drift.STABLE_S + 300)
        self.assertEqual(len(self.restarts()), 1)

    def test_release_wave_is_one_restart_after_stable_period(self):
        self.round(T0)
        self.change("CLAUDE.md", "1\n")
        self.round(T0 + 300)
        self.change("AGENTS.md", "2\n")                              # a hullám második fele
        self.round(T0 + 900)
        self.round(T0 + 300 + prompt_drift.STABLE_S + 1)             # az első óta 15 perc, a második óta nem
        self.assertEqual(self.restarts(), [])
        self.round(T0 + 900 + prompt_drift.STABLE_S + 1)
        self.assertEqual(len(self.restarts()), 1)
        self.assertIn("AGENTS.md", self.sent[0]); self.assertIn("CLAUDE.md", self.sent[0])

    def test_systemctl_failure_sends_no_false_notice(self):
        self.round(T0)
        self.change("CLAUDE.md", "# más\n")
        self.round(T0 + 300)
        ex = functools.partial(reconcile.execute, sysctl=lambda *a: self.calls.append(a) or (5 if a[0] == "restart" else 0),
                               run=lambda *a, **k: None, do_postcheck=lambda e, **k: {"status": "ok"})
        reconcile.reconcile(agents=self.agents, now=T0 + 301 + prompt_drift.STABLE_S, measure=self.measure(IDLE),
                            unit_active=lambda u: True, execute_fn=ex, oom_sweep=lambda: {"protected": 0}, procs=None)
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.st().get("drift_notice"))
        self.assertIn("systemctl-hiba", (self.d / "st" / "prompt-drift.log").read_text())


class TestIncludes(unittest.TestCase):
    def test_mentions_emails_and_fences_are_not_files(self):
        home = Path("/h")
        txt = "\n".join(["@AGENTS.md és @~/x/y.md, a@b.example, @valaki", "```", "@kod.md", "```", ""])
        got = prompt_files.includes(txt, Path("/w"), home)
        self.assertEqual(got, [Path("/w/AGENTS.md"), Path("/h/x/y.md")])


if __name__ == "__main__":
    unittest.main()
