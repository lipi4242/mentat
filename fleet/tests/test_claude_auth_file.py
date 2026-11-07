"""A Claude-token helye: külön `claude-auth.env` (0600), nem az ágens
env-fájlja — azt (alapból telegram.env) a híd is betölti. A sablon-PR (#9)
előtti unitnál a token az env-fájlba megy, figyelmeztetéssel: a két PR
sorrendje így nem törhet el semmit. A TERMELŐ install_flow-t hívja."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_install_txn import Base, _entry  # noqa: E402
from fleet import claude_auth, install  # noqa: E402

NEW = ("ExecStart=tmux ... /bin/sh -c 'set -a; if [ -r %h/.config/probe/telegram.env ]; then "
       ". %h/.config/probe/telegram.env; fi; if [ -r %h/.config/probe/claude-auth.env ]; then "
       ". %h/.config/probe/claude-auth.env; fi; set +a'")


class TestTokenFile(Base):
    def _unit(self, text):
        orig = install.unit_text_for
        install.unit_text_for = lambda e: text
        self.addCleanup(setattr, install, "unit_text_for", orig)

    def test_token_goes_to_claude_auth_env_not_the_bridge_env(self):
        self._unit(NEW)
        self.fb.logged_out()
        r = self.install(environ={"CLAUDE_CODE_OAUTH_TOKEN": "tok-SECRET"})
        self.assertEqual(r["status"], "ok", r)
        auth = self.home / ".config/probe/claude-auth.env"
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN=tok-SECRET", auth.read_text())
        self.assertEqual(auth.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("tok-SECRET", (self.home / ".config/probe/telegram.env").read_text())
        self.assertNotIn("tok-SECRET", json.dumps(r, ensure_ascii=False))

    def test_old_template_falls_back_to_env_file_with_warning(self):
        self._unit(NEW.replace("claude-auth.env", "x.env"))
        self.fb.logged_out()
        r = self.install(environ={"CLAUDE_CODE_OAUTH_TOKEN": "tok-SECRET"})
        self.assertEqual(r["status"], "ok", r)
        self.assertIn("tok-SECRET", (self.home / ".config/probe/telegram.env").read_text())
        self.assertIn("FIGYELEM: a unit-sablon még nem tölti be", " ".join(r["notes"]))

    def test_unit_env_reads_auth_file_over_env_file(self):
        d = self.home / ".config/probe"
        (d / "telegram.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=regi\n")
        (d / "claude-auth.env").write_text("CLAUDE_CODE_OAUTH_TOKEN=uj\n")
        self.assertEqual(claude_auth.unit_env(_entry(), self.home, {})["CLAUDE_CODE_OAUTH_TOKEN"], "uj")


if __name__ == "__main__":
    unittest.main()
