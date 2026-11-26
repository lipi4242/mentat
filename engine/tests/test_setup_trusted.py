#!/usr/bin/env python3
"""setup records the first components.engine.todo_trusted list: the agent and (if known) the owner;
an existing list is never overwritten; and the data framing still works with the filled list.
Compatible with pytest and direct execution (stdlib unittest)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_setup import SetupCase  # noqa: E402
from anytime_engine import trusted_seed  # noqa: E402


class TrustedCase(SetupCase):
    def setUp(self):
        super().setUp()
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["agent"] = {"name": "rocky", "language": "en"}
        (self.root / "mentat.json").write_text(json.dumps(doc))

    def trusted(self):
        return self.engine().get("todo_trusted")

    def set_engine(self, **kw):
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"].update(kw)
        (self.root / "mentat.json").write_text(json.dumps(doc))


class TestSeed(TrustedCase):
    def test_fresh_install_lists_the_agent_and_the_known_owner(self):
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer", "--todo-owner", "p_krisz")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.trusted(), ["rocky", "p_krisz"])
        self.assertNotIn(trusted_seed.HINT[:30], out)

    def test_unknown_owner_lists_only_the_agent_and_says_how_to_extend(self):
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.trusted(), ["rocky"])
        self.assertIn("--todo-owner", out)
        self.assertIn("components.engine.todo_trusted", out)

    def test_an_existing_hand_extended_list_is_not_overwritten(self):
        self.set_engine(todo_trusted=["rocky", "p_krisz", "p_anna"])
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")   # no flag: untouched
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.trusted(), ["rocky", "p_krisz", "p_anna"])
        self.assertNotIn("only this agent is listed", out)

    def test_an_empty_list_is_also_kept(self):
        self.set_engine(todo_trusted=[])
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(self.trusted(), [])

    def test_a_rerun_keeps_the_first_list(self):
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer", "--todo-owner", "p_krisz")
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(self.trusted(), ["rocky", "p_krisz"])

    def test_dry_run_writes_nothing(self):
        before = (self.root / "mentat.json").read_text()
        self.run_setup("--tz", "Europe/Budapest", "--todo-owner", "p_krisz")
        self.assertEqual((self.root / "mentat.json").read_text(), before)

    def test_owner_from_the_environment(self):
        import os
        os.environ["ANYTIME_TODO_OWNER"] = "p_env"
        self.addCleanup(os.environ.pop, "ANYTIME_TODO_OWNER", None)
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(self.trusted(), ["rocky", "p_env"])

    def test_the_agents_own_pm_is_listed_too(self):
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer",
                                 "--todo-owner", "p_krisz", "--todo-pm", "p_paul")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.trusted(), ["rocky", "p_krisz", "p_paul"])

    def test_pm_from_the_environment_and_no_duplicate_when_the_owner_is_the_pm(self):
        import os
        os.environ["ANYTIME_TODO_PM"] = "p_krisz"
        self.addCleanup(os.environ.pop, "ANYTIME_TODO_PM", None)
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer", "--todo-owner", "p_krisz")
        self.assertEqual(self.trusted(), ["rocky", "p_krisz"])



class TestExtend(TrustedCase):
    """An existing list: an EXPLICIT --todo-owner/--todo-pm adds what is missing, at the end; nothing
    is removed or reordered. Without the flags (the environment included) the list is left alone."""

    def test_the_hint_is_true_a_rerun_with_the_owner_adds_the_owner(self):
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(self.trusted(), ["rocky"])
        self.assertIn("re-run setup with --todo-owner", out)        # what the hint promises ...
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer", "--todo-owner", "p_krisz")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.trusted(), ["rocky", "p_krisz"])        # ... is what a re-run does
        self.assertIn("todo_trusted: added p_krisz", out)
        self.assertNotIn("only this agent is listed", out)

    def test_a_hand_extended_list_keeps_every_entry_and_its_order(self):
        self.set_engine(todo_trusted=["p_anna", "rocky", "p_krisz"])
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer",
                       "--todo-owner", "p_krisz", "--todo-pm", "p_paul")
        self.assertEqual(self.trusted(), ["p_anna", "rocky", "p_krisz", "p_paul"])

    def test_the_environment_alone_does_not_extend_an_existing_list(self):
        import os
        self.set_engine(todo_trusted=["rocky"])
        os.environ.update(ANYTIME_TODO_OWNER="p_env", ANYTIME_TODO_PM="p_envpm")
        self.addCleanup(os.environ.pop, "ANYTIME_TODO_OWNER", None)
        self.addCleanup(os.environ.pop, "ANYTIME_TODO_PM", None)
        self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer")
        self.assertEqual(self.trusted(), ["rocky"])

    def test_nothing_new_means_nothing_written(self):
        self.set_engine(todo_trusted=["rocky", "p_krisz"])
        rc, out = self.run_setup("--tz", "Europe/Budapest", "--install", "--no-timer", "--todo-owner", "p_krisz")
        self.assertEqual(self.trusted(), ["rocky", "p_krisz"])
        self.assertNotIn("todo_trusted: added", out)


if __name__ == "__main__":
    unittest.main()
