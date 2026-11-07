"""Arming-verdict tests.

The case that matters most is `test_newborn_that_never_ticked_is_not_armed`:
that is the exact state Eta was in on 2026-08-12 — unit active, session alive,
no tick ever, and `liveness.should_rearm` returning False because `tick_age_s`
was `None`.
"""
import unittest

import pytest  # noqa: F401  (repo convention: run under both unittest and pytest)

from fleet import arming

PERIOD = 1800.0  # Eta's 30-minute tick


def verdict(**kw):
    base = dict(tick_age_s=None, unit_uptime_s=0.0, attempts_used=0,
                tick_period_s=PERIOD)
    base.update(kw)
    return arming.arming_verdict(**base)


class TestArmingVerdict(unittest.TestCase):

    def test_tick_after_unit_start_is_armed(self):
        # Up for an hour, ticked a minute ago → the loop is wound up.
        self.assertEqual(verdict(tick_age_s=60.0, unit_uptime_s=3600.0),
                         arming.ARMED)

    def test_newborn_that_never_ticked_is_not_armed(self):
        # THE regression: no tick trace at all. Must not read as healthy.
        self.assertNotEqual(verdict(unit_uptime_s=3600.0), arming.ARMED)

    def test_tick_older_than_the_unit_is_not_armed(self):
        # A last-tick.json left behind by the PREVIOUS run. The file exists,
        # so a naive existence check would call this armed; it is not.
        self.assertNotEqual(verdict(tick_age_s=4000.0, unit_uptime_s=600.0),
                            arming.ARMED)

    def test_inside_the_deadline_we_wait(self):
        # A newborn is allowed to be silent while it boots.
        self.assertEqual(verdict(unit_uptime_s=60.0), arming.WAIT)

    def test_deadline_is_grace_plus_one_period(self):
        self.assertEqual(arming.deadline_s(PERIOD, grace_s=180), 1980.0)
        self.assertEqual(verdict(unit_uptime_s=1979.0), arming.WAIT)
        self.assertEqual(verdict(unit_uptime_s=1981.0), arming.REARM)

    def test_deadline_tracks_the_agents_own_period(self):
        # An hourly agent gets an hour; a flat threshold would nag it.
        hourly = dict(tick_period_s=3600.0, unit_uptime_s=2000.0)
        self.assertEqual(verdict(**hourly), arming.WAIT)
        self.assertEqual(verdict(tick_period_s=600.0, unit_uptime_s=2000.0),
                         arming.REARM)

    def test_past_the_deadline_we_rearm(self):
        self.assertEqual(verdict(unit_uptime_s=9999.0, attempts_used=0),
                         arming.REARM)
        self.assertEqual(verdict(unit_uptime_s=9999.0, attempts_used=1),
                         arming.REARM)

    def test_attempts_are_bounded_then_it_fails_loudly(self):
        # Bounded is the whole reason this is safe to run where the
        # steady-state check refuses to: it cannot storm, it can only give up.
        self.assertEqual(verdict(unit_uptime_s=9999.0, attempts_used=2),
                         arming.FAILED)
        self.assertEqual(verdict(unit_uptime_s=9999.0, attempts_used=99),
                         arming.FAILED)

    def test_a_tick_arriving_during_the_attempts_wins(self):
        # Re-arm worked: verdict flips to armed even with attempts spent.
        self.assertEqual(verdict(tick_age_s=5.0, unit_uptime_s=9999.0,
                                 attempts_used=2), arming.ARMED)

    def test_armed_beats_the_deadline_regardless_of_uptime(self):
        # No window in which a genuinely ticking agent is reported as failed.
        for uptime in (200.0, 2000.0, 20000.0):
            self.assertEqual(verdict(tick_age_s=1.0, unit_uptime_s=uptime,
                                     attempts_used=9), arming.ARMED)


ENTRY = {"agent": "eta", "unit": "eta.service", "session": "eta",
         "loop_cmd": "/loop 30m python3 entry.py --trigger hourly",
         "tick_period_s": PERIOD}


class TestVerifyLoop(unittest.TestCase):
    """The loop only ever returns ARMED or FAILED — 'still waiting' as a result
    is exactly how an unarmed agent gets filed as fine."""

    def _verify(self, uptimes, tick_ages, **kw):
        """Drive the loop through scripted (uptime, tick_age) observations."""
        ups, ticks, sent = list(uptimes), list(tick_ages), []
        return arming.verify(
            ENTRY, poll_s=1.0, sleep=lambda s: None,
            uptime=lambda: ups.pop(0) if ups else 99999.0,
            tick_age=lambda: ticks.pop(0) if ticks else None,
            rearm=lambda: (sent.append(1), True)[1],
            log=lambda *a: None, **kw), sent

    def test_already_ticking_returns_armed_without_rearming(self):
        r, sent = self._verify([3600.0], [30.0])
        self.assertEqual(r["verdict"], arming.ARMED)
        self.assertEqual(r["attempts"], 0)
        self.assertEqual(sent, [])

    def test_waits_through_the_grace_then_succeeds(self):
        # Silent while booting, then the first tick lands. No re-arm needed.
        r, sent = self._verify([60.0, 120.0, 200.0], [None, None, 5.0])
        self.assertEqual(r["verdict"], arming.ARMED)
        self.assertEqual(sent, [])

    def test_the_eta_regression_rearms_and_recovers(self):
        # Past the deadline with no tick ever → re-send, and then the tick arrives.
        r, sent = self._verify([2000.0, 2100.0], [None, 10.0])
        self.assertEqual(r["verdict"], arming.ARMED)
        self.assertEqual(r["attempts"], 1)
        self.assertEqual(len(sent), 1)

    def test_gives_up_loudly_after_the_bounded_attempts(self):
        r, sent = self._verify([9999.0] * 6, [None] * 6)
        self.assertEqual(r["verdict"], arming.FAILED)
        self.assertEqual(len(sent), arming.DEFAULT_MAX_ATTEMPTS)
        self.assertIn("re-arm", r["detail"])

    def test_unreadable_unit_start_fails_rather_than_assuming_health(self):
        r, sent = self._verify([None], [None])
        self.assertEqual(r["verdict"], arming.FAILED)
        self.assertIn("unit start time", r["detail"])
        self.assertEqual(sent, [])

    def test_missing_loop_cmd_fails_instead_of_pretending_to_rearm(self):
        entry = dict(ENTRY); entry.pop("loop_cmd")
        r = arming.verify(entry, poll_s=1.0, sleep=lambda s: None,
                          uptime=lambda: 9999.0, tick_age=lambda: None,
                          rearm=lambda: True, log=lambda *a: None)
        self.assertEqual(r["verdict"], arming.FAILED)
        self.assertIn("loop_cmd", r["detail"])


class TestUnitUptime(unittest.TestCase):

    class _R:
        def __init__(self, out, rc=0):
            self.stdout, self.returncode = out, rc

    def test_never_started_unit_is_unknown_not_zero(self):
        # systemd reports 0 for a unit that never activated. Zero uptime would
        # read as "just started", i.e. permanently inside the grace window.
        self.assertIsNone(arming.unit_uptime_s("x.service",
                                               run=lambda c: self._R("0")))

    def test_garbage_and_failure_are_unknown(self):
        self.assertIsNone(arming.unit_uptime_s("x.service",
                                               run=lambda c: self._R("nem szam")))
        self.assertIsNone(arming.unit_uptime_s("x.service",
                                               run=lambda c: self._R("123", rc=1)))

    def test_oserror_is_unknown_not_a_crash(self):
        def boom(cmd):
            raise OSError("no systemctl")
        self.assertIsNone(arming.unit_uptime_s("x.service", run=boom))


if __name__ == "__main__":
    unittest.main()
