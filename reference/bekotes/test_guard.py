import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GUARD = HERE / "szerep_guard.py"
ROLES = {"roles": {"default": "asszisztens", "installed": ["asszisztens", "fejleszto"]}}


def make_repo(roles=ROLES):
    root = pathlib.Path(tempfile.mkdtemp())
    doc = {"schema": 1, "components": {"brain": {"root": "agy"}}}
    doc.update(roles or {})
    (root / "mentat.json").write_text(json.dumps(doc))
    (root / "agy" / "szerepek").mkdir(parents=True)
    for n in ("asszisztens", "fejleszto", "kiado"):
        shutil.copy(HERE / "szerepek" / (n + ".hu.md"), root / "agy" / "szerepek" / (n + ".md"))
    return root


class GuardBase(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_guard(self, payload, role=None, args=()):
        env = {k: v for k, v in os.environ.items() if k not in ("MENTAT_ROLE", "CLAUDE_PROJECT_DIR",
                                                              "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PROJECT_DIR"] = str(self.root)
        # Hermetic: a home of the test's own (KintBase brings one), never the caller's ~/.ssh, gh or git config.
        home = getattr(self, "home", None) or getattr(self, "_iso_home", None)
        if home is None:
            home = self._iso_home = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, home, True)
        for k in ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN"):
            env.pop(k, None)
        env.update(HOME=str(home), XDG_CONFIG_HOME=os.path.join(str(home), ".config"),
                   GH_CONFIG_DIR=os.path.join(str(home), ".config", "gh"))
        if role:
            env["MENTAT_ROLE"] = role
        payload = dict({"cwd": str(self.root), "session_id": "s1"}, **payload)
        return subprocess.run([sys.executable, str(GUARD), *args], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, cwd=self.root)

    def decide(self, tool, inp, role=None, sid="s1", **extra):
        r = self.run_guard(dict({"tool_name": tool, "tool_input": inp, "session_id": sid}, **extra), role)
        self.assertEqual(r.returncode, 0, r.stderr)
        if not r.stdout.strip():
            return "allow"
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]


class GuardTest(GuardBase):
    def test_assistant_cannot_push(self):
        self.assertEqual(self.decide("Bash", {"command": "git push origin main"}), "deny")

    def test_chained_command_is_matched(self):
        self.assertEqual(self.decide("Bash", {"command": "echo hi && git push origin x"}), "deny")

    def test_developer_can_push_branch_but_not_read_bank(self):
        self.assertEqual(self.decide("Bash", {"command": "git push origin feat/x"}, "fejleszto"), "allow")
        self.assertEqual(self.decide("Bash", {"command": "git push origin main"}, "fejleszto"), "deny")
        self.assertEqual(self.decide("Read", {"file_path": str(self.root / "munka/bank/x.csv")},
                                     "fejleszto"), "deny")

    def test_path_and_mcp_rules(self):
        self.assertEqual(self.decide("Edit", {"file_path": "munka/a.txt"}), "deny")
        self.assertEqual(self.decide("Edit", {"file_path": "agy/a.md"}), "allow")
        self.assertEqual(self.decide("mcp__gmail__send_message", {}), "deny")
        self.assertEqual(self.decide("mcp__gmail__search", {}, "fejleszto", "s2"), "deny")

    def test_reason_text(self):
        r = self.run_guard({"tool_name": "Bash", "tool_input": {"command": "git push"}})
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("asszisztens", reason)
        self.assertIn("MENTAT_ROLE=<", reason)

    def test_unknown_role_denies_everything(self):
        self.assertEqual(self.decide("Read", {"file_path": "README.md"}, "kiado"), "deny")

    def test_no_roles_denies_nothing(self):
        shutil.rmtree(self.root)
        self.root = make_repo(roles={})
        self.assertEqual(self.decide("Bash", {"command": "git push origin main"}), "allow")

    def test_role_is_pinned_per_session(self):
        self.decide("Read", {"file_path": "a"}, "fejleszto")
        pin = self.root / ".mentat" / "szerep" / "s1"
        self.assertEqual(pin.read_text().splitlines()[0], "fejleszto")
        # a later run with a different env still uses the pin
        self.assertEqual(self.decide("Bash", {"command": "git push origin feat/x"}), "allow")

    def test_missing_role_file_denies(self):
        (self.root / "agy" / "szerepek" / "asszisztens.md").unlink()
        self.assertEqual(self.decide("Read", {"file_path": "a"}), "deny")

    def test_session_start(self):
        r = self.run_guard({}, "fejleszto", ["--session-start"])
        self.assertEqual(r.returncode, 0, r.stderr)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "SessionStart")
        self.assertIn("Szerep ebben a futásban: fejleszto (env)", ctx["additionalContext"])
        self.assertIn("agy/szerepek/fejleszto.md", ctx["additionalContext"])
        self.assertEqual((self.root / ".mentat" / "szerep" / "s1").read_text().splitlines()[0], "fejleszto")
        self.assertIn(".mentat/", (self.root / ".gitignore").read_text().split())

    def test_session_start_default_is_silent(self):
        r = self.run_guard({}, None, ["--session-start"])
        self.assertEqual(r.stdout.strip(), "")

    def test_session_start_is_silent_whatever_the_callers_home_holds(self):  # docs-dev, 0.3.1
        from unittest import mock
        caller = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, caller, True)
        (caller / ".ssh").mkdir()
        (caller / ".ssh" / "config").write_text("Host doboz\n  HostName 192.0.2.7\n")
        with mock.patch.dict(os.environ, {"HOME": str(caller)}):
            r = self.run_guard({}, None, ["--session-start"])
        self.assertEqual(r.stdout.strip(), "")

    # --- fix round 1 ---


if __name__ == "__main__":
    unittest.main()
