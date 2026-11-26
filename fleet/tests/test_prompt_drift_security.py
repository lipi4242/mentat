"""A prompt-drift biztonsági őrei (CISO-audit). Mindegyik a javítás nélkül piros:
FIFO/óriásfájl/symlink/kifelé mutató include nem akaszt és nem tágít; csak
kiadott (git-követett, HEAD-del egyező) változás indít restartot; hooks-változás
és hibás settings csak jelzés; a request-restart csak a sajátra; a fájlnevek szűrve."""
from __future__ import annotations
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest  # noqa: F401  (repo konvenció)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _drift_box import T0, Box  # noqa: E402

from fleet import prompt_files, prompt_safe_read, request_restart_cli, requested_stop  # noqa: E402


class TestReadGuards(Box):
    def snap(self):
        return prompt_files.snapshot(self.agents[0])

    def test_fifo_include_does_not_hang(self):
        os.mkfifo(self.wd / "cso.md")
        (self.wd / "AGENTS.md").write_text("@cso.md\n")
        out = {}
        t = threading.Thread(target=lambda: out.update(s=self.snap()), daemon=True)
        t.start(); t.join(5)
        self.assertFalse(t.is_alive(), "a snapshot egy FIFO-n megakadt")
        self.assertTrue(out["s"][str((self.wd / "cso.md").resolve())].startswith("nem-fajl"))

    def test_include_outside_roots_is_ignored(self):
        (self.d / "kint.md").write_text("titok\n")
        (self.wd / "AGENTS.md").write_text("@../kint.md\n")
        self.assertFalse(any("kint.md" in k for k in self.snap()))

    def test_symlink_in_tree_is_skipped_and_big_file_is_marked(self):
        (self.wd / ".claude" / "rules" / "link.md").symlink_to("/etc/hosts")
        (self.wd / ".claude" / "rules" / "nagy.md").write_bytes(b"x" * (prompt_safe_read.MAX_BYTES + 1))
        s = self.snap()
        self.assertFalse(any(k.endswith("link.md") for k in s))
        self.assertTrue(s[str(self.wd / ".claude" / "rules" / "nagy.md")].startswith("nagy:"))

    def test_max_files_enforced_during_walk(self):
        for i in range(20):
            (self.wd / ".claude" / "rules" / f"f{i:02}.md").write_text("x")
        self.assertEqual(len(prompt_safe_read.walk(self.wd / ".claude" / "rules", 5)), 5)

    def test_time_budget_returns_none(self):
        ticks = iter(range(0, 10_000, 30))
        self.assertIsNone(prompt_files.snapshot(self.agents[0], clock=lambda: next(ticks)))


class TestTrust(Box):
    def assert_alert_only(self, kind):
        self.assertEqual(self.restarts(), [])
        self.assertEqual(len(self.alerts), 1)
        self.assertIn(kind, self.alerts[0])

    def test_uncommitted_change_alerts_only(self):
        self.round(T0)
        self.change("CLAUDE.md", "kézzel átírva\n", commit=False)
        self.settle(T0 + 300)
        self.assert_alert_only("csak-jelzes")

    def test_untracked_new_rule_alerts_only(self):
        self.round(T0)
        self.change(".claude/rules/uj.md", "nem követett\n", commit=False)
        self.settle(T0 + 300)
        self.assert_alert_only("csak-jelzes")

    def test_config_root_change_alerts_only(self):
        self.round(T0)
        cfg = Path(os.environ["HOME"]) / ".claude"; cfg.mkdir()
        (cfg / "CLAUDE.md").write_text("fiók-szintű\n")
        self.settle(T0 + 300)
        self.assert_alert_only("csak-jelzes")

    def test_committed_hooks_change_alerts_only(self):
        self.change(".claude/settings.json", '{"model": "x"}'); self.backdate()
        self.round(T0)
        self.change(".claude/settings.json", '{"model": "x", "hooks": {"PreToolUse": []}}')
        self.settle(T0 + 300)
        self.assert_alert_only("hooks")

    def test_invalid_settings_no_restart(self):
        self.change(".claude/settings.json", "{}"); self.backdate()
        self.round(T0)
        self.change(".claude/settings.json", "{nem json")
        self.settle(T0 + 300)
        self.assert_alert_only("hibas-settings")


class TestRequestAndNames(Box):
    def test_request_for_another_agent_is_refused(self):
        with mock.patch.dict(os.environ, {"FLEET_AGENT": "probe-agent"}):
            rc = request_restart_cli.cmd_request_restart(SimpleNamespace(agent="masik-agent"))
        self.assertEqual(rc, 2)
        self.assertFalse(requested_stop.restart_pending("masik-agent"))

    def test_own_agent_from_cwd(self):
        env = {k: v for k, v in os.environ.items() if k != "FLEET_AGENT"}
        self.assertEqual(request_restart_cli.own_agent(self.wd / "docs", env, self.agents), "probe-agent")
        self.assertIsNone(request_restart_cli.own_agent(self.d, env, self.agents))

    def test_far_future_marker_is_clamped(self):
        requested_stop.mark_restart("probe-agent")
        p = requested_stop._restart_path("probe-agent"); p.write_text("9999999999")
        self.assertFalse(requested_stop.restart_pending("probe-agent", p.stat().st_mtime + requested_stop.RESTART_VALID_S + 1))

    def test_file_names_are_ascii_filtered_in_notice_log_and_alert(self):
        self.round(T0)
        self.change(".claude/rules/ré\x1b[31m.md", "x\n")
        self.settle(T0 + 300)
        log = (self.d / "st" / "prompt-drift.log").read_text()
        for text in (self.sent[0], log, self.alerts[0]):
            self.assertNotIn("\x1b", text); self.assertNotIn("é", text.split("rules/")[1].split()[0])
        self.assertIn(".claude/rules/r31m.md", self.sent[0])


if __name__ == "__main__":
    unittest.main()
