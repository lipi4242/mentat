"""A registry normalizálása és a névszabályok. Tiszta függvények."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import registry, names  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_defaults_are_filled_and_input_untouched(self):
        e = {"agent": "x", "workdir": "%h/x"}
        n = registry.normalize(e)
        self.assertEqual(n["status"], "active")
        self.assertEqual(n["claude_account"], "shared")
        self.assertEqual(n["unit"], "x.service")
        self.assertEqual(n["session"], "x")
        self.assertEqual(n["rc_name"], "x")
        self.assertEqual(n["env_file"], "telegram.env")
        self.assertEqual(n["unit_source"], "template")
        self.assertEqual(n["supervision"], "fleet")
        self.assertNotIn("status", e)

    def test_explicit_values_win(self):
        n = registry.normalize({"agent": "gamma-release-agent", "rc_name": "delta",
                                "session": "gamma-release", "env_file": "delta.env",
                                "status": "dormant", "claude_account": "example"})
        self.assertEqual(n["rc_name"], "delta")
        self.assertEqual(n["session"], "gamma-release")
        self.assertEqual(n["env_file"], "delta.env")
        self.assertTrue(registry.is_dormant(n))
        self.assertEqual(n["claude_account"], "example")

    def test_legacy_account_field_is_not_the_claude_account(self):
        n = registry.normalize({"agent": "alpha", "account": "google:alpha@example.test"})
        self.assertEqual(n["account"], "google:alpha@example.test")
        self.assertEqual(n["claude_account"], "shared")

    def test_host_matching(self):
        self.assertTrue(registry.host_matches({"host": None}, "alpha"))
        self.assertTrue(registry.host_matches({"host": "alpha"}, "alpha"))
        self.assertFalse(registry.host_matches({"host": "zeta-hetzner"}, "alpha"))


class TestNames(unittest.TestCase):
    def test_slug_rules(self):
        for ok in ("alpha", "gamma-release-agent", "a1"):
            self.assertTrue(names.is_valid_agent_name(ok), ok)
        for bad in ("", "Alpha", "1abc", "a b", "a_b", "x" * 41):
            self.assertFalse(names.is_valid_agent_name(bad), bad)

    def test_findings_name_the_field(self):
        f = names.name_findings({"agent": "ok", "session": "Bad Name", "rc_name": "fine", "unit": "ok.timer"})
        self.assertEqual(len(f), 2)
        self.assertTrue(any("session" in x for x in f))
        self.assertTrue(any("unit" in x for x in f))


EXAMPLE_AGENTS = Path(__file__).resolve().parents[1] / "examples" / "registry" / "agents.json"


class TestExampleRegistry(unittest.TestCase):
    """A példa-registry: minden bejegyzés normalizálható és névhelyes."""
    def test_every_entry_is_valid(self):
        agents = registry.load_agents(EXAMPLE_AGENTS)
        self.assertGreaterEqual(len(agents), 2)
        for a in agents:
            self.assertEqual(names.name_findings(a), [], a["agent"])
            self.assertIn(a["status"], registry.AGENT_STATUSES)

    def test_dormant_set_matches_operator_decisions(self):
        dormant = {a["agent"] for a in registry.load_agents(EXAMPLE_AGENTS) if registry.is_dormant(a)}
        self.assertEqual(dormant, {"demo-helper"})


if __name__ == "__main__":
    unittest.main()
