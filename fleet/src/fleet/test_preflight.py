"""Preflight tests.

The pure checks carry most of the weight here; the I/O ones are exercised
through a real temp workdir rather than mocks, because the failure they guard
against (a repo that looks fine and is not deployable) is a filesystem fact.
"""
import os
import stat
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo convention: run under both unittest and pytest)

from fleet import preflight

ENTRY = {"agent": "eta", "unit": "eta.service", "session": "eta",
         "workdir": "%h/eta", "model": "fable", "host": "alpha",
         "proactive": True, "loop_cmd": "/loop 30m python3 entry.py --trigger hourly",
         "tick_period_s": 1800}


class TestMissingFields(unittest.TestCase):

    def test_complete_entry_is_silent(self):
        self.assertEqual(preflight.missing_fields(ENTRY), [])

    def test_each_required_field_is_actually_required(self):
        for field in preflight.REQUIRED_FIELDS:
            entry = dict(ENTRY); entry.pop(field)
            self.assertIn(field, preflight.missing_fields(entry), field)

    def test_proactive_agent_needs_something_to_arm(self):
        entry = dict(ENTRY); entry.pop("loop_cmd")
        self.assertIn("loop_cmd", preflight.missing_fields(entry))

    def test_reactive_agent_needs_no_loop_cmd(self):
        entry = dict(ENTRY); entry["proactive"] = False
        entry.pop("loop_cmd"); entry.pop("tick_period_s")
        self.assertEqual(preflight.missing_fields(entry), [])

    def test_subetha_bridge_must_be_fully_specified(self):
        entry = dict(ENTRY); entry["bridge"] = {"mode": "sub-etha"}
        self.assertEqual(sorted(preflight.missing_fields(entry)),
                         ["bridge.unit", "bridge.version"])


class TestEngineDiscovery(unittest.TestCase):
    """Agents legitimately differ in where (and whether) their engine lives.

    An earlier cut demanded `entry.py` at the workdir root and reported four of
    nine real agents as unfit — alpha keeps its engine under scripts/anytime/v2,
    and lambda-agent and hub have no tick engine at all.
    """

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_root_entry_py_is_found(self):
        (self.d / "entry.py").write_text("")
        self.assertEqual(preflight.engine_cli(self.d), "entry.py")

    def test_nested_engine_is_found(self):
        nested = self.d / "scripts" / "anytime" / "v2"
        nested.mkdir(parents=True)
        (nested / "entry.py").write_text("")
        self.assertEqual(preflight.engine_cli(self.d), "scripts/anytime/v2/entry.py")

    def test_no_engine_is_a_shape_not_a_fault(self):
        self.assertIsNone(preflight.engine_cli(self.d))
        self.assertEqual(preflight.engine_findings(self.d, ["hourly"]), [])


class TestEnvMode(unittest.TestCase):

    def test_0600_passes(self):
        self.assertEqual(preflight.mode_findings(0o100600, "/x/telegram.env"), [])

    def test_group_or_world_readable_is_reported(self):
        self.assertTrue(preflight.mode_findings(0o100644, "/x/telegram.env"))
        self.assertTrue(preflight.mode_findings(0o100640, "/x/telegram.env"))

    def test_missing_file_is_not_a_permission_finding(self):
        # Absence is a different (and differently worded) problem.
        self.assertEqual(preflight.mode_findings(None, "/x/telegram.env"), [])


class TestTokenCollisions(unittest.TestCase):

    def test_distinct_tokens_are_silent(self):
        self.assertEqual(preflight.token_collisions({"a": "aa", "b": "bb"}), [])

    def test_shared_token_names_both_agents(self):
        found = preflight.token_collisions({"a": "same", "b": "same"})
        self.assertEqual(len(found), 1)
        self.assertIn("a", found[0])
        self.assertIn("b", found[0])

    def test_agents_without_a_token_are_not_collisions(self):
        self.assertEqual(preflight.token_collisions({"a": None, "b": None}), [])

    def test_fingerprint_never_reveals_the_token(self):
        token = "434343:AAEsecretsecretsecret"
        fp = preflight.fingerprint(token)
        self.assertNotIn("AAEsecret", fp)
        self.assertNotIn("434343", fp)
        self.assertEqual(fp, preflight.fingerprint(token + "\n"))  # whitespace-stable


class TestPlanHasWork(unittest.TestCase):
    """The phantom-trigger signature: valid JSON, exit 0, nothing to do."""

    def test_empty_plan_is_no_work(self):
        self.assertFalse(preflight._plan_has_work('{"plan": []}'))
        self.assertFalse(preflight._plan_has_work('{"actions": []}'))

    def test_populated_plan_is_work(self):
        self.assertTrue(preflight._plan_has_work('{"plan": ["pr_scan"]}'))
        self.assertTrue(preflight._plan_has_work('{"levels": [["a"]]}'))

    def test_non_json_output_falls_back_to_non_empty(self):
        # Engines differ across repos; demanding one JSON shape would make this
        # fail on the next agent and get skipped.
        self.assertTrue(preflight._plan_has_work("will run: pr_scan"))
        self.assertFalse(preflight._plan_has_work("   \n"))


class TestDeclinedOnPurpose(unittest.TestCase):
    """An engine that says WHY it planned nothing has proved it knows the
    trigger — which is precisely what a phantom trigger cannot do."""

    #: Verbatim from gamma-release-agent on 2026-08-12, which the first cut
    #: of this check accused of having a phantom trigger.
    REAL = ('{"skipped": "lease-busy", "message": "Ez a tick nem fut: a kiadasi '
            'lease-t alpha:2959285 tartja. A kovetkezo ebredesnel ujra nezem."}')

    def test_the_real_false_positive_is_not_a_finding(self):
        self.assertTrue(preflight._declined_on_purpose(self.REAL))
        self.assertFalse(preflight._plan_has_work(self.REAL))

    def test_a_silent_empty_plan_is_still_suspicious(self):
        # The Eta phantom-trigger shape: no work, no explanation.
        self.assertFalse(preflight._declined_on_purpose('{"plan": []}'))

    def test_empty_reason_does_not_excuse_an_empty_plan(self):
        self.assertFalse(preflight._declined_on_purpose('{"reason": ""}'))

    def test_non_json_is_not_an_explanation(self):
        self.assertFalse(preflight._declined_on_purpose("nothing to do"))


class TestTriggerExtraction(unittest.TestCase):

    def test_trigger_comes_from_the_loop_cmd_systemd_will_type(self):
        self.assertEqual(preflight._triggers_from_loop_cmd(ENTRY), ["hourly"])

    def test_no_trigger_in_cmd_invents_nothing(self):
        # Checking a made-up trigger instead of the real one is worse than not
        # checking: it reports green about something that never runs.
        self.assertEqual(
            preflight._triggers_from_loop_cmd({"loop_cmd": "/alpha:startup"}), [])


class TestPreflightIntegration(unittest.TestCase):

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)
        (self.home / "eta").mkdir()
        self.brain = self.home / "eta" / "AGENTS.md"
        self.brain.write_text("# L\n\n## Scope boundary\nx\n\n## Release\ny\n")

    def _entry(self, **kw):
        e = dict(ENTRY); e.update(kw); return e

    def test_dormant_agent_is_never_unfit(self):
        e = self._entry(status="dormant", workdir="%h/does-not-exist")
        self.assertEqual(preflight.preflight(e, home=self.home), [])

    def test_missing_workdir_is_reported(self):
        e = self._entry(workdir="%h/nope")
        self.assertTrue(any("does not exist" in f
                            for f in preflight.preflight(e, home=self.home)))

    def test_missing_brain_is_reported(self):
        self.brain.unlink()
        self.assertTrue(any("AGENTS.md" in f
                            for f in preflight.preflight(self._entry(), home=self.home)))

    def test_an_engineless_agent_is_not_reported_as_unfit(self):
        # lambda-agent and hub have no tick engine; that is a shape, not a
        # fault, and reporting it failed a third of the real fleet.
        self.assertEqual(preflight.preflight(self._entry(), home=self.home), [])

    def test_a_deployable_repo_passes(self):
        # A minimal entry.py that validates and plans work for `hourly`.
        (self.home / "eta" / "entry.py").write_text(
            "import sys\n"
            "print('{\"plan\": [\"x\"], \"errors\": []}')\n"
            "sys.exit(0)\n")
        self.assertEqual(preflight.preflight(self._entry(), home=self.home), [])

    def test_a_trigger_that_plans_nothing_is_caught(self):
        # The Eta phantom-trigger shape: exit 0, valid JSON, empty plan.
        (self.home / "eta" / "entry.py").write_text(
            "import sys\nprint('{\"plan\": []}')\nsys.exit(0)\n")
        found = preflight.preflight(self._entry(), home=self.home)
        self.assertTrue(any("plans NO work" in f for f in found), found)

    def test_bridge_agent_without_env_file_is_caught(self):
        (self.home / "eta" / "entry.py").write_text(
            "import sys\nprint('{\"plan\": [\"x\"]}')\nsys.exit(0)\n")
        e = self._entry(bridge={"mode": "sub-etha", "unit": "u", "version": "1.4.0"})
        self.assertTrue(any("telegram.env" in f
                            for f in preflight.preflight(e, home=self.home)))

    def test_world_readable_env_is_caught(self):
        (self.home / "eta" / "entry.py").write_text(
            "import sys\nprint('{\"plan\": [\"x\"]}')\nsys.exit(0)\n")
        cfg = self.home / ".config" / "eta"
        cfg.mkdir(parents=True)
        env = cfg / "telegram.env"
        env.write_text("TELEGRAM_BOT_TOKEN=1:abc\n")
        os.chmod(env, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        e = self._entry(bridge={"mode": "sub-etha", "unit": "u", "version": "1.4.0"})
        self.assertTrue(any("0600" in f for f in preflight.preflight(e, home=self.home)))


if __name__ == "__main__":
    unittest.main()


class TestBoxAwareness(unittest.TestCase):
    """The fleet can span more than one box, and every check here reads the
    LOCAL filesystem. Observed in production: preflight run on one box declared
    the agents of another box unfit, because their repos live elsewhere."""

    BOXES = [{"key": "box-a", "hostname": "host-a"},
             {"key": "box-b", "hostname": "host-b"}]

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ("FLEET_HOST", "HOME")}
        self._home = tempfile.TemporaryDirectory()
        os.environ["HOME"] = self._home.name      # no ~/.config/fleet/host
        os.environ.pop("FLEET_HOST", None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._home.cleanup()

    def test_fleet_host_env_wins(self):
        os.environ["FLEET_HOST"] = "box-b"
        self.assertEqual(preflight.local_box_key(self.BOXES), "box-b")

    def test_identifies_the_box_from_the_hostname(self):
        import socket
        boxes = [{"key": "box-a", "hostname": socket.gethostname()}]
        self.assertEqual(preflight.local_box_key(boxes), "box-a")

    def test_an_unknown_machine_is_no_box(self):
        self.assertIsNone(preflight.local_box_key(self.BOXES))

    def test_foreign_agent_is_not_checkable_here(self):
        self.assertFalse(
            preflight.is_checkable_here({"host": "box-b"}, "box-a"))
        self.assertTrue(
            preflight.is_checkable_here({"host": "box-a"}, "box-a"))

    def test_off_box_we_check_anyway_rather_than_refuse(self):
        # A developer machine is where people iterate on this module; refusing
        # there would make it untestable exactly where it is being written.
        self.assertTrue(preflight.is_checkable_here({"host": "box-a"}, None))
