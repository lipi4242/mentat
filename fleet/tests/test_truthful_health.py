"""A doctor és a postcheck mondjon igazat.

2026-10-14-én mérve: a doctor a `pending` ütemezést és az `unknown` RC/auth-ot
jónak vette, a `--fix` pedig `ok: True`-t írt a javítás eredményétől
függetlenül; a postcheck OK-t adott egy ágensre, amelynek a startup-parancsa
30 napig egyszer sem ment be. Ezek a tesztek a TERMELŐ kódot hívják
(doctor.assess, doctor.doctor, postcheck_verdict, schedule_verdict), és a
javítás előtti kódon pirosak voltak.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, registry, signals  # noqa: E402
from fleet.postcheck import postcheck_verdict  # noqa: E402

NOW = 1_800_000_000.0
PERIOD = 1800


def _entry(**kw):
    b = {"agent": "probe-agent", "rc_name": "probe", "workdir": "/x", "proactive": True,
         "tick_period_s": PERIOD, "loop_cmd": "/x:startup", "host": "probe-host"}
    b.update(kw)
    return registry.normalize(b)


def _sig(state, detail="", **data):
    return {"state": state, "detail": detail, "data": data}


def _m(proc="up", sched="armed", channel="n/a", rc="connected", auth="ok",
       tick_age=100.0, started=NOW - 4000, pollers=(), auth_detail="", rc_detail=""):
    return {"agent": "probe-agent", "session_id": "s", "transcript_age_s": 10.0,
            "pollers": list(pollers),
            "signals": {"process": _sig(proc, pid=11, rss_mb=300, started_s=started),
                        "schedule": _sig(sched, tick_age_s=tick_age, period_s=PERIOD),
                        "channel": _sig(channel),
                        "rc": _sig(rc, rc_detail),
                        "auth": _sig(auth, auth_detail)}}


def _assess(m):
    return doctor.assess(_entry(), m, {"quarantined": False}, unit_active="active",
                         unit_enabled="enabled", drop_in=True, bridge_installed=None,
                         bridge_current="x", locked=False)


class TestDoctorAssess(unittest.TestCase):
    def test_all_healthy_is_ok(self):
        self.assertTrue(_assess(_m())["ok"])

    def test_pending_schedule_is_not_ok(self):
        r = _assess(_m(sched="pending"))
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("health"), "pending")

    def test_unknown_auth_is_not_ok_and_says_why(self):
        r = _assess(_m(auth=signals.UNKNOWN, auth_detail="nincs session.id"))
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("health"), "unknown")
        self.assertTrue(any("auth" in u and "nincs session.id" in u for u in r.get("unknown", [])))

    def test_unknown_rc_is_optional_na_and_does_not_fail(self):
        # 2026-10-15 elfogadási mérés: RC nélkül a doctor tartósan 1-gyel lépett
        # ki. Az RC opcionális (a postcheck sem követeli): unknown → n/a, kiírva.
        r = _assess(_m(rc=signals.UNKNOWN, rc_detail="nincs RC-esemény"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["health"], "healthy")
        self.assertTrue(any(f.startswith("rc") and "n/a" in f for f in r["facts"]), r["facts"])

    def test_disconnected_rc_still_fails(self):
        self.assertFalse(_assess(_m(rc="disconnected"))["ok"])

    def test_result_is_never_better_than_worst_signal(self):
        r = _assess(_m(sched="pending", auth=signals.UNKNOWN, proc="down"))
        self.assertEqual(r.get("health"), "unhealthy")
        r = _assess(_m(sched="pending", auth=signals.UNKNOWN))
        self.assertEqual(r.get("health"), "unknown")

    def test_unrecognised_state_word_is_not_healthy(self):
        self.assertFalse(_assess(_m(channel="valami-uj"))["ok"])


class TestDoctorFix(unittest.TestCase):
    """A `--fix` csak akkor siker, ha a javítás UTÁN újramérve minden healthy."""

    def run_fix(self, measures):
        unit_dir = Path(tempfile.mkdtemp())
        e = _entry()
        (unit_dir / f"{e['unit']}.d").mkdir()
        (unit_dir / f"{e['unit']}.d" / "10-session-gate.conf").write_text("")
        seq = iter(measures)
        with mock.patch.object(doctor, "load_agents", return_value=[e]), \
                mock.patch.object(doctor, "local_host", return_value="probe-host"), \
                mock.patch.object(doctor, "load_state", return_value={"quarantined": False}), \
                mock.patch.object(doctor, "_sysctl_prop", return_value="active"), \
                mock.patch.object(doctor, "UNIT_DIR", str(unit_dir)), \
                mock.patch.object(doctor, "reconcile", return_value={"lines": ["restart végrehajtva"]}) as rc, \
                mock.patch("fleet.signals.measure", side_effect=lambda _e: next(seq)), \
                mock.patch("fleet.hookguard.claude_version", return_value="2.1.309 (Claude Code)"), \
                mock.patch("fleet.envjel.check", return_value=(None, None)):  # nemakad-jel: a próba-pid nem valódi
            out = doctor.doctor(agent="probe-agent", fix=True)
        rc.assert_called_once()
        return out[-1]

    def test_failed_fix_is_not_reported_as_success(self):
        fix = self.run_fix([_m(proc="down"), _m(proc="down")])
        self.assertFalse(fix["ok"])

    def test_fix_that_leaves_schedule_pending_is_not_success(self):
        fix = self.run_fix([_m(proc="down"), _m(sched="pending")])
        self.assertFalse(fix["ok"])

    def test_fix_proven_by_remeasure_is_success(self):
        fix = self.run_fix([_m(proc="down"), _m()])
        self.assertTrue(fix["ok"])


class TestPostcheckTruth(unittest.TestCase):
    def v(self, m, restart_at, now=NOW):
        return postcheck_verdict(m, restart_at=restart_at, now=now,
                                 grace_over=(now - restart_at) > 15 * 60)[0]

    def test_pending_schedule_right_after_restart_is_not_ok(self):
        m = _m(sched="pending", tick_age=None, started=NOW - 30)
        self.assertEqual(self.v(m, restart_at=NOW - 40), "pending")

    def test_pending_schedule_past_its_deadline_fails(self):
        restart = NOW - (PERIOD + 180 + 60)
        m = _m(sched="pending", tick_age=None, started=restart + 5)
        self.assertEqual(self.v(m, restart_at=restart), "failed")

    def test_tick_from_before_the_restart_is_no_proof(self):
        # 'armed' a restart ELŐTTI tickből — az új generáció még nem tickelt
        m = _m(sched="armed", tick_age=600.0, started=NOW - 60)
        self.assertEqual(self.v(m, restart_at=NOW - 70), "pending")

    def test_tick_after_restart_is_ok(self):
        m = _m(sched="armed", tick_age=20.0, started=NOW - 60)
        self.assertEqual(self.v(m, restart_at=NOW - 70), "ok")

    def test_unknown_auth_waits_then_fails(self):
        m = _m(auth=signals.UNKNOWN, tick_age=20.0, started=NOW - 60)
        self.assertEqual(self.v(m, restart_at=NOW - 70), "pending")
        m = _m(auth=signals.UNKNOWN, tick_age=20.0, started=NOW - 1000)
        self.assertEqual(self.v(m, restart_at=NOW - 1000), "failed")

    def test_unreadable_start_time_does_not_stay_pending_forever(self):
        m = _m(tick_age=20.0, started=None)
        self.assertEqual(self.v(m, restart_at=NOW - 1000), "failed")


class TestScheduleNeverWoundUp(unittest.TestCase):
    def test_no_tick_trace_long_after_start_is_stale_not_unknown(self):
        st, detail = signals.schedule_verdict(proactive=True, tick_age=None, period_s=PERIOD,
                                              process_started_s=NOW - 30 * 86400, now=NOW)
        self.assertEqual(st, "stale")
        self.assertIn("tick", detail)

    def test_without_start_time_it_is_unknown(self):
        st, _ = signals.schedule_verdict(proactive=True, tick_age=None, period_s=PERIOD,
                                         process_started_s=None, now=NOW)
        self.assertEqual(st, signals.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
