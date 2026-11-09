"""Liveness tests — OOM protection must not report failure as silence.

The case that matters: measured on a production box, 2026-09-23. Every agent
process sat at `oom_score_adj=200` (the target is `AGENT_OOM_ADJ = -600`)
because `sudo -n` is denied for that box's unix user. The liveness line said
`0 OOM-védelem beírva` every three minutes — which reads as *no work to do*.

The `and` that joined `needs_oom_protect()` to `write_oom_adj()` made the two
outcomes numerically identical: "nothing needed protection" and "every single
write was refused" both produced zero. On a 3.8 GB box running five agents,
that is the difference between being protected and being first in line for the
OOM killer, and nothing in the log distinguished them.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import tempfile
import unittest

import pytest  # noqa: F401  (repo convention: run under both unittest and pytest)

from fleet import liveness


class OomFailureIsNotSilenceTest(unittest.TestCase):
    def setUp(self):
        self._saved = (liveness.claude_pids, liveness.read_oom_adj,
                       liveness.write_oom_adj)
        liveness.claude_pids = lambda: [111, 222]
        liveness.read_oom_adj = lambda pid: 200        # unprotected
        # A registry-útvonal feloldása a load_json ELŐTT fut: egy üres, de
        # létező registry-könyvtár, hogy a teszt ne a gép beállításától függjön.
        self._reg = tempfile.TemporaryDirectory()
        self._env = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = self._reg.name

    def tearDown(self):
        (liveness.claude_pids, liveness.read_oom_adj,
         liveness.write_oom_adj) = self._saved
        if self._env is None:
            os.environ.pop("FLEET_REGISTRY", None)
        else:
            os.environ["FLEET_REGISTRY"] = self._env
        self._reg.cleanup()

    def test_denied_sudo_is_counted_as_failure(self):
        liveness.write_oom_adj = lambda pid, value=liveness.AGENT_OOM_ADJ: False
        r = liveness.oom_sweep()
        self.assertEqual(r["protected"], 0)
        self.assertEqual(r["oom_failed"], 2)

    def test_successful_write_counts_as_protected(self):
        # The ON side of the same branch. Without it, an implementation that
        # always reported failure would satisfy the test above.
        liveness.write_oom_adj = lambda pid, value=liveness.AGENT_OOM_ADJ: True
        r = liveness.oom_sweep()
        self.assertEqual(r["protected"], 2)
        self.assertEqual(r["oom_failed"], 0)

    def test_already_protected_attempts_no_write_and_counts_neither(self):
        # Negative control: "nothing to do" must leave BOTH counters at zero —
        # this is precisely the case the old code could not tell apart from
        # total failure. The stub fails the test if a write is attempted.
        liveness.read_oom_adj = lambda pid: liveness.AGENT_OOM_ADJ
        liveness.write_oom_adj = lambda pid, value=liveness.AGENT_OOM_ADJ: self.fail(
            "must not attempt a write on an already-protected process")
        r = liveness.oom_sweep()
        self.assertEqual(r["protected"], 0)
        self.assertEqual(r["oom_failed"], 0)

    def test_mixed_outcome_is_reported_on_both_counters(self):
        seen = []

        def flaky(pid, value=liveness.AGENT_OOM_ADJ):
            seen.append(pid)
            return pid == 111

        liveness.write_oom_adj = flaky
        r = liveness.oom_sweep()
        self.assertEqual(seen, [111, 222])
        self.assertEqual(r["protected"], 1)
        self.assertEqual(r["oom_failed"], 1)


if __name__ == "__main__":
    unittest.main()


class OomHelperPreferenceTest(unittest.TestCase):
    """The validating helper is the only path; there is no `tee` fallback (FL-02).

    Ubuntu 26.04 ships sudo-rs, which refuses wildcards in command arguments:

        <user> ALL=(root) NOPASSWD: /usr/bin/tee /proc/[0-9]*/oom_score_adj
        → "wildcards are not allowed in command arguments"

    Allowing bare `tee` instead would grant root-write to ANY file — not a
    narrowing at all. So the privilege belongs to a helper that validates its
    own arguments, and this test pins which command is actually invoked.
    """

    def setUp(self):
        self._run = liveness.subprocess.run
        self._exists = liveness.Path.exists
        self.calls = []

        def fake_run(cmd, **kw):
            self.calls.append(cmd)
            class R:
                returncode = 0
            return R()

        liveness.subprocess.run = fake_run

    def tearDown(self):
        liveness.subprocess.run = self._run
        liveness.Path.exists = self._exists

    def test_helper_is_used_when_installed(self):
        liveness.Path.exists = lambda self: True
        self.assertTrue(liveness.write_oom_adj(4242, -600))
        self.assertEqual(self.calls[0],
                         ["sudo", "-n", liveness.OOM_HELPER, "4242", "-600"])

    def test_no_tee_fallback_when_helper_absent(self):
        # FL-02 (CISO 10-22): under classic sudo the old `tee /proc/[0-9]*/…` rule's `*`
        # matches any characters, so it granted root-write to any file. The helper is the
        # only path; without it nothing is attempted (not fatal, the caller counts it).
        liveness.Path.exists = lambda self: False
        self.assertFalse(liveness.write_oom_adj(4242, -600))
        self.assertEqual(self.calls, [])
        self.assertFalse(any("tee" in c for call in self.calls for c in call))


class OomHelperScriptTest(unittest.TestCase):
    """A fleet/bin/oom-protect a saját argumentumait ellenőrzi (rootként fut)."""
    HELPER = os.path.join(os.path.dirname(__file__), "..", "bin", "oom-protect")

    def run_helper(self, *args):
        import subprocess
        return subprocess.run(["sh", self.HELPER, *args], capture_output=True, text=True).returncode

    def test_rejects_bad_arguments(self):
        for args in [(), ("1",), ("x1", "-600"), ("1", "abc"), ("1", "-"), ("1", "-2000"), ("1", "5000")]:
            self.assertEqual(self.run_helper(*args), 2, args)

    def test_refuses_a_process_that_is_not_an_agent(self):
        self.assertEqual(self.run_helper(str(os.getpid()), "-600"), 3)

    def test_a_process_that_only_looks_like_an_agent_is_refused(self):
        # A cmdline utánozható: egy python-processz „claude … --remote-control x”
        # argumentumokkal átmegy a mintán, de a futó bináris nem claude (#39).
        import subprocess
        import sys as _sys
        fake = subprocess.Popen([_sys.executable, "-c", "import time; time.sleep(30)",
                                 "claude", "--remote-control", "x"])
        try:
            r = subprocess.run(["sh", self.HELPER, str(fake.pid), "-600"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)
            if os.path.isdir("/proc"):
                self.assertIn("nem claude", r.stderr)
        finally:
            fake.kill(); fake.wait()

    def test_missing_helper_is_named_in_the_log_line(self):
        line = liveness.format_oom({"protected": 0, "oom_failed": 1, "helper_missing": True})
        self.assertIn(liveness.OOM_HELPER, line)
        self.assertIn("sudo install", line)
        self.assertIn("sudo -n tiltva", liveness.format_oom({"protected": 0, "oom_failed": 1}))
