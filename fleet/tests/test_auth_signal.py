"""Az auth-jel: a lejárt login a többi négy jel mellett zöldben marad
(2026-10-01, Beta: 4 óra, 8 tick kiesett, 11 üzenet kapott hibát)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import unittest

from fleet import authsig, reconcile, signals

OK = '{"type":"assistant","timestamp":"2026-10-01T15:00:00Z","message":{"model":"claude-opus-5","content":[{"type":"text","text":"rendben"}]}}'
FAIL1 = '{"type":"assistant","timestamp":"2026-10-01T16:47:47Z","error":"authentication_failed","isApiErrorMessage":true,"message":{"model":"<synthetic>","content":[{"type":"text","text":"Login expired · Please run /login"}]}}'
FAIL2 = '{"type":"assistant","timestamp":"2026-10-01T17:17:46Z","error":"authentication_failed","isApiErrorMessage":true,"message":{"model":"<synthetic>"}}'
OVERLOAD = '{"type":"assistant","timestamp":"2026-10-01T17:30:00Z","error":"overloaded","isApiErrorMessage":true,"message":{"model":"<synthetic>"}}'
RECOVERED = '{"type":"assistant","timestamp":"2026-10-01T20:17:00Z","message":{"model":"claude-opus-5","content":[{"type":"text","text":"visszatértem"}]}}'
USER = '{"type":"user","timestamp":"2026-10-01T18:00:00Z","message":{"content":"Login expired · Please run /login"}}'


class TestAuthEvents(unittest.TestCase):
    def test_only_assistant_records_count_and_other_api_errors_are_neither(self):
        ev = authsig.auth_events([OK, FAIL1, USER, OVERLOAD, FAIL2])
        self.assertEqual([k for _, k in ev], ["ok", "auth_failed", "auth_failed"])

    def test_user_quoting_the_error_text_is_not_an_event(self):
        self.assertEqual(authsig.auth_events([USER]), [])


class TestAuthVerdict(unittest.TestCase):
    def test_vocabulary(self):
        v = lambda lines: authsig.auth_verdict(authsig.auth_events(lines))[0]
        self.assertEqual(v([]), signals.UNKNOWN)
        self.assertEqual(v([USER, OVERLOAD]), signals.UNKNOWN)
        self.assertEqual(v([OK]), "ok")
        self.assertEqual(v([OK, FAIL1, FAIL2]), "expired")
        self.assertEqual(v([OK, FAIL1, FAIL2, RECOVERED]), "ok")   # a gyógyulás nyoma a későbbi valódi válasz

    def test_expired_reports_since_first_failure_of_the_run_and_count(self):
        state, detail, data = authsig.auth_verdict(authsig.auth_events([FAIL1, OK, FAIL1, FAIL2]))
        self.assertEqual(state, "expired")
        self.assertEqual(data["failed"], 2)
        self.assertEqual(data["since_s"], authsig.auth_events([FAIL1])[0][0])
        self.assertIn("claude auth login", detail)


def _entry():
    return {"agent": "probe-agent", "status": "active", "rc_name": "probe-agent", "unit": "probe.service",
            "proactive": True, "tick_period_s": 61200, "bridge": {"unit": "probe-bridge.service"}}


def _measure(auth):
    now = 1_700_000_000
    return {"agent": "probe-agent", "session_id": "s", "transcript_age_s": 1200.0, "pollers": [],
            "signals": {"process": {"state": "up", "detail": "", "data": {"pid": 11, "rss_mb": 300, "started_s": now - 4000}},
                        "schedule": {"state": "armed", "detail": "", "data": {"tick_age_s": 100.0, "period_s": 61200}},
                        "channel": {"state": "ok", "detail": "", "data": {}},
                        "rc": {"state": "connected", "detail": "", "data": {}},
                        "auth": auth}}


class TestDecideAuth(unittest.TestCase):
    def d(self, auth):
        return reconcile.decide(_entry(), _measure(auth), {"restarts": []},
                                unit_active=True, locked=False, now=1_700_000_000)

    def test_expired_login_alerts_once_per_expiry_and_never_restarts(self):
        acts = self.d({"state": "expired", "detail": "Login expired 10-01 16:47 óta", "data": {"since_s": 1759337267}})
        self.assertEqual([a for a, _ in acts], ["alert:auth:probe-agent:1759337267"])
        acts2 = self.d({"state": "expired", "detail": "", "data": {"since_s": 1759400000}})
        self.assertNotEqual(acts[0][0], acts2[0][0])     # új lejárat = új kulcs = új riasztás

    def test_ok_is_healthy_and_unknown_is_named(self):
        self.assertEqual(self.d({"state": "ok", "detail": "", "data": {}}), [("noop", "egészséges")])
        self.assertEqual(self.d({"state": signals.UNKNOWN, "detail": "", "data": {}}), [("noop", "egészséges")])

    def test_measure_without_auth_key_still_decides(self):
        m = _measure({"state": "ok", "detail": "", "data": {}}); del m["signals"]["auth"]
        self.assertEqual(reconcile.decide(_entry(), m, {"restarts": []}, unit_active=True, locked=False,
                                          now=1_700_000_000), [("noop", "egészséges")])


if __name__ == "__main__":
    unittest.main()
