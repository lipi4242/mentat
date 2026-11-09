"""fleet/bin/mentat-todo: a FLEET_AGENT-ből a helyes handle, token és API jut a CLI-hez."""
from __future__ import annotations
import _hermetic  # noqa: F401
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401

BIN = Path(__file__).resolve().parents[1] / "bin" / "mentat-todo"


class TestMentatTodoBin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "todo"
        self.cfg.mkdir()
        (self.cfg / "env").write_text("TODO_API=http://127.0.0.1:9/api/todo/v1\n")
        (self.cfg / "handles").write_text("minta-agent=minta\n")
        (self.cfg / "minta.token").write_text("x\n")
        (self.cfg / "minta.token").chmod(0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def run_bin(self, *args, **env):
        e = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "XDG_CONFIG_HOME": self.tmp.name}
        e.update(env)
        return subprocess.run(["sh", str(BIN), *args], capture_output=True, text=True, env=e,
                              cwd=self.tmp.name)

    def test_agent_maps_to_handle_and_reaches_the_cli(self):
        r = self.run_bin("me", FLEET_AGENT="minta-agent")
        # a CLI elindult, a beállítást elfogadta, és a (szándékosan zárt) API-ig jutott
        self.assertNotIn("mentat-todo:", r.stderr)
        self.assertNotIn("not configured", r.stderr)
        self.assertNotIn("token", r.stderr.lower())
        self.assertNotEqual(r.returncode, 0)
        self.assertNotEqual(r.returncode, 2)

    def test_missing_token_is_a_clear_error(self):
        r = self.run_bin("me", FLEET_AGENT="unknown-agent")
        self.assertEqual(r.returncode, 2)
        self.assertIn("nincs token", r.stderr)

    def test_no_identity_is_refused(self):
        r = self.run_bin("me")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FLEET_AGENT", r.stderr)      # a hibaüzenet megnevezi a lehetőségeket
        self.assertIn("todo_handle", r.stderr)

    def test_desktop_handle_comes_from_the_repo_manifest(self):
        # asztali gép: nincs FLEET_AGENT, nincs --as; a repó mentat.json-ja adja a handle-t,
        # a ~/.config/todo az api-t és a tokent (box–asztal paritás, 11-08)
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        (repo / "mentat.json").write_text('{"schema": 1, "components": {"engine": {"todo_handle": "minta"}}}')
        e = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "XDG_CONFIG_HOME": self.tmp.name}
        r = subprocess.run(["sh", str(BIN), "me"], capture_output=True, text=True, env=e, cwd=repo)
        self.assertNotIn("mentat-todo:", r.stderr)
        self.assertNotIn("not configured", r.stderr)
        self.assertNotIn("token", r.stderr.lower())
        self.assertIn("unreachable", r.stderr)          # a (szándékosan zárt) API-ig jutott

    def test_a_stale_engine_in_the_cwd_does_not_shadow_the_checkout(self):
        stale = Path(self.tmp.name) / "anytime_engine"
        stale.mkdir()
        (stale / "__init__.py").write_text('__version__ = "0.2.1"\n')   # régi, mentat_manifest nélkül
        r = self.run_bin("me", FLEET_AGENT="minta-agent")
        self.assertNotIn("ImportError", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_private_xdg_falls_back_to_home_config(self):
        home = Path(self.tmp.name) / "h"
        (home / ".config").mkdir(parents=True)
        (home / ".config" / "todo").symlink_to(self.cfg)
        r = self.run_bin("me", FLEET_AGENT="minta-agent", HOME=str(home),
                         XDG_CONFIG_HOME=str(Path(self.tmp.name) / "xdg-sajat"))
        self.assertNotIn("mentat-todo:", r.stderr)


if __name__ == "__main__":
    unittest.main()
