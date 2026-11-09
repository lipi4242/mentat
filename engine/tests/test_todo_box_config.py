#!/usr/bin/env python3
"""anytime_todo settings on a fleet box: with FLEET_AGENT set, the missing api, handle and
token come from ~/.config/todo (the same convention as fleet/bin/mentat-todo); without
FLEET_AGENT nothing is read from there.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from anytime_todo import settings  # noqa: E402
except ModuleNotFoundError:  # a csomag nélkül szinkronizált fa (sync-to.sh pack nélkül)
    raise unittest.SkipTest("anytime_todo pack not present")

_KEYS = ("FLEET_AGENT", "XDG_CONFIG_HOME", "HOME", "TODO_API", "TODO_HANDLE", "TODO_TOKEN_FILE")


class BoxConfig(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in _KEYS}
        for k in _KEYS:
            os.environ.pop(k, None)
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["HOME"] = str(self.tmp / "home")
        cfg = self.tmp / "home" / ".config" / "todo"
        cfg.mkdir(parents=True)
        (cfg / "env").write_text("TODO_API=https://todo.example/api/todo/v1/\n")
        (cfg / "handles").write_text("other-agent=x\nrelease-agent=kata\n")
        tok = cfg / "kata.token"
        tok.write_text("not-a-real-token\n")
        tok.chmod(0o600)
        self.tok, self.root = tok, self.tmp / "repo"
        self.root.mkdir()

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_box_fills_api_handle_and_token(self):
        os.environ["FLEET_AGENT"] = "release-agent"
        s = settings.load(self.root)
        self.assertEqual((s.api, s.handle, s.token_file),
                         ("https://todo.example/api/todo/v1", "kata", str(self.tok)))
        self.assertEqual(s.token(), "not-a-real-token")

    def test_unmapped_agent_uses_its_own_name(self):
        os.environ["FLEET_AGENT"] = "kata"
        self.assertEqual(settings.load(self.root).handle, "kata")

    def test_explicit_env_wins(self):
        os.environ.update(FLEET_AGENT="release-agent", TODO_HANDLE="other", TODO_API="https://a.example/x")
        s = settings.load(self.root)
        self.assertEqual((s.api, s.handle, s.token_file), ("https://a.example/x", "other", None))

    def test_without_fleet_agent_the_box_files_are_not_read(self):
        self.assertIsNone(settings.load(self.root))

    def test_desktop_known_handle_fills_api_and_token(self):
        # asztal: nincs FLEET_AGENT, de a handle ismert → az api és a token a ~/.config/todo-ból
        os.environ["TODO_HANDLE"] = "kata"
        s = settings.load(self.root)
        self.assertEqual((s.api, s.handle, s.token_file),
                         ("https://todo.example/api/todo/v1", "kata", str(self.tok)))

    def test_the_stored_token_never_goes_to_another_api(self):
        for fleet in ("release-agent", None):
            os.environ.pop("FLEET_AGENT", None)
            if fleet:
                os.environ["FLEET_AGENT"] = fleet
            os.environ.update(TODO_HANDLE="kata", TODO_API="https://masik.example/api/todo/v1")
            self.assertIsNone(settings.load(self.root).token_file)
            os.environ["TODO_API"] = "https://todo.example/api/todo/v1"     # ugyanaz, mint az env-fájlban
            self.assertEqual(settings.load(self.root).token_file, str(self.tok))

    def test_desktop_handle_from_the_repo_manifest(self):
        (self.root / "mentat.json").write_text('{"schema": 1, "components": {"engine": {"todo_handle": "kata"}}}')
        s = settings.load(self.root)
        self.assertEqual((s.handle, s.token(), s.api), ("kata", "not-a-real-token", "https://todo.example/api/todo/v1"))


if __name__ == "__main__":
    unittest.main()
