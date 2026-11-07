"""Kézi lépés nélküli telepítés (elfogadási mérés 2026-10-15, 06-flotta):
a felhasználónak tmux-ba kellett lépnie a Bypass-ablakért, intéznie kellett
az auth-ot, kézzel kellett felvenni a session-id hookot, és a tmux hiányát
semmi nem jelezte. Ezek a tesztek a TERMELŐ kódot hívják (install_flow,
claude_firstrun, claude_auth, pane) hamis systemctl/claude/tmux mellett.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import sys
import unittest
from unittest import mock
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_install_txn import Base, _entry  # noqa: E402
from fleet import claude_auth, claude_firstrun, pane  # noqa: E402


class TestFirstRunDialogs(Base):
    def test_install_preaccepts_theme_trust_bypass_and_remote_dialog(self):
        r = self.install()
        self.assertEqual(r["status"], "ok", r)
        g = json.loads((self.home / ".claude.json").read_text())
        self.assertTrue(g["hasCompletedOnboarding"])
        self.assertTrue(g["remoteDialogSeen"])
        self.assertTrue(g["projects"][str(Path("/home/x/probe").resolve())]["hasTrustDialogAccepted"])
        st = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertTrue(st["skipDangerousModePermissionPrompt"])
        self.assertEqual((self.home / ".claude.json").stat().st_mode & 0o777, 0o600)

    def test_seeding_keeps_existing_keys_and_is_idempotent(self):
        (self.home / ".claude").mkdir()
        (self.home / ".claude.json").write_text(json.dumps({"theme": "light", "oauthAccount": {"x": 1}}))
        (self.home / ".claude/settings.json").write_text(json.dumps(
            {"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}))
        self.install()
        g = json.loads((self.home / ".claude.json").read_text())
        self.assertEqual((g["theme"], g["oauthAccount"]), ("light", {"x": 1}))
        st = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(st["model"], "opus")
        self.assertIn("Stop", st["hooks"])
        again = claude_firstrun.apply(_entry(), home=self.home)
        self.assertEqual(again["changes"], [])

    def test_session_id_hook_installed_once_and_points_at_checkout(self):
        self.install(); self.install()
        st = json.loads((self.home / ".claude/settings.json").read_text())
        cmds = [h["command"] for g in st["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(len(cmds), 1, cmds)
        self.assertTrue(cmds[0].endswith("/bin/capture-session-id.sh"))
        self.assertTrue(Path(cmds[0]).is_file())

    def test_legacy_hook_elsewhere_is_replaced_not_duplicated(self):
        """L23: a régi (más checkoutból bejegyzett) hook csak THUFIR_AGENT-et ismert, így az új,
        FLEET_AGENT-es ágensnek nem lett session.id. A sajátunkra cseréljük: egy hook marad."""
        doc = {"hooks": {"SessionStart": [{"hooks": [{"type": "command",
                                                      "command": "/opt/f/bin/capture-session-id.sh"}]}]}}
        ch = claude_firstrun.seed_settings(doc, "/new/bin/capture-session-id.sh")
        cmds = [h["command"] for g in doc["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(cmds, ["/new/bin/capture-session-id.sh"])
        self.assertIn("SessionStart hook", " ".join(ch))
        self.assertEqual(claude_firstrun.seed_settings(doc, "/new/bin/capture-session-id.sh"), [])

    def test_invalid_json_is_never_overwritten(self):
        (self.home / ".claude.json").write_text("{nem json")
        r = self.install()
        self.assertEqual(r["status"], "failed")
        self.assertIn("nem érvényes JSON", " ".join(r["problems"]))
        self.assertEqual((self.home / ".claude.json").read_text(), "{nem json")
        self.assertFalse((self.ud / "probe.service").exists())

    def test_named_account_seeds_its_own_config_dir(self):
        self.install(_entry(claude_account="masik"))
        self.assertTrue((self.home / ".claude-masik/.claude.json").exists())
        self.assertTrue((self.home / ".claude-masik/settings.json").exists())


class TestPaneDialog(Base):
    def test_active_unit_stuck_at_dialog_is_a_failure_not_ok(self):
        self.fb.pane("WARNING: Claude Code running in Bypass Permissions mode\n❯ 1. No, exit\n  2. Yes, I accept\n")
        r = self.install()
        self.assertEqual(r["status"], "failed", r)
        self.assertIn("Bypass Permissions", " ".join(r["problems"]))
        self.assertIn("tmux capture-pane -p -t =probe:", self.fb.calls())

    def test_matcher_knows_each_first_run_dialog(self):
        for text, name in (("Quick safety check: Is this a project", "workspace trust"),
                           ("Choose the text style that looks best", "téma (első indítás)"),
                           ("Select login method:", "bejelentkezés")):
            self.assertEqual(pane.dialog_in(text)[0], name)
        self.assertIsNone(pane.dialog_in("> Try \"refactor\"\n? for shortcuts"))


class TestAuthForTheUnit(Base):
    def test_shell_token_is_handed_to_the_unit_0600_never_printed(self):
        self.fb.logged_out()
        r = self.install(environ={"CLAUDE_CODE_OAUTH_TOKEN": "tok-SECRET-123"})
        self.assertEqual(r["status"], "ok", r)
        # a hely a telepítendő unittól függ (claude-auth.env a #9-es sablon óta)
        env = claude_auth.token_file(_entry(), self.home)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN=tok-SECRET-123", env.read_text())
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("tok-SECRET-123", json.dumps(r, ensure_ascii=False))
        self.assertNotIn("tok-SECRET-123", "\n".join(self.fb.calls()))

    def test_installer_shell_token_alone_is_not_proof_for_the_unit(self):
        # régen: a shell tokenjével zöld a precheck, a unit mégsem lát logint
        self.fb.logged_out()
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "shell-tok", "ANTHROPIC_API_KEY": "k"}):
            r = self.install(environ={})
        self.assertEqual(r["status"], "failed", r)
        self.assertIn("`fleet auth probe`", " ".join(r["problems"]))

    def test_no_login_anywhere_gives_one_command_fix_before_any_write(self):
        self.fb.logged_out()
        r = self.install()
        self.assertEqual(r["status"], "failed")
        self.assertIn("`fleet auth probe`", " ".join(r["problems"]))
        self.assertFalse((self.ud / "probe.service").exists())

    def test_expired_shell_token_says_so(self):
        self.fb.logged_out()
        r = self.install(environ={"CLAUDE_CODE_OAUTH_TOKEN": "bad-token"})
        self.assertIn("így sem lát érvényes logint", " ".join(r["problems"]))


class TestTmuxPreflight(Base):
    def test_missing_tmux_stops_before_any_write_with_install_command(self):
        r = self.install(tmux_bin=Path(self.tmp.name) / "nincs" / "tmux")
        self.assertEqual(r["status"], "failed")
        self.assertIn("hiányzik a tmux", r["problems"][0])
        self.assertIn("Telepítsd", r["problems"][0])
        self.assertFalse((self.ud / "probe.service").exists())


if __name__ == "__main__":
    unittest.main()
