"""A teljes reconcile-kör nem marad ki a zár miatt, és a restart utáni postcheck-várakozás nem tartja a zárat."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import fcntl
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import reconcile  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402

OKR = {"status": reconcile.OK, "ok": True, "problems": [], "pending": []}


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.st = self.d / "st"
        self.patches = [
            mock.patch.object(reconcile, "STATE_DIR", self.st),
            mock.patch.object(reconcile, "LOCK_PATH", self.st / "lock"),
            mock.patch.object(reconcile, "controller_is_us", lambda: True),
            mock.patch.object(reconcile, "local_host", lambda: "probe-host"),
            mock.patch.object(reconcile, "_may_act", lambda e, log: True),
            mock.patch.object(reconcile, "LOCK_POLL_S", 0.02),
            mock.patch.object(reconcile, "LOCK_WAIT_S", 2),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.st.mkdir()
        self.e = _entry()

    def run_round(self, **kw):
        measured = kw.pop("measured", [])
        base = dict(agents=[self.e], now=time.time(),
                    measure=lambda _e: measured.append(1) or _m(),
                    unit_active=lambda u: True, execute_fn=lambda *a, **k: None,
                    oom_sweep=lambda: {"protected": 0, "oom_failed": 0})
        base.update(kw)
        return reconcile.reconcile(**base)

    def hold(self):
        f = (self.st / "lock").open("w")
        fcntl.flock(f, fcntl.LOCK_EX)
        return f


class WaitForLock(Base):
    def test_full_round_waits_for_a_busy_lock_and_runs(self):
        f = self.hold()
        threading.Timer(0.3, lambda: (fcntl.flock(f, fcntl.LOCK_UN), f.close())).start()
        measured = []
        with mock.patch.object(reconcile, "LOCK_WAIT_S", 10):
            out = self.run_round(measured=measured)
        self.assertEqual(len(measured), 1)   # ma: üresen tér vissza, a kör kimarad
        self.assertFalse(any("kilépek" in x for x in out["lines"]))

    def test_full_round_gives_up_after_the_timeout_and_counts_it(self):
        f = self.hold()
        self.addCleanup(f.close)
        measured = []
        with mock.patch.object(reconcile, "LOCK_WAIT_S", 0.2):
            out = self.run_round(measured=measured)
        self.assertEqual(measured, [])
        self.assertTrue(any("a kör kimaradt" in x for x in out["lines"]))
        self.assertEqual((self.st / "reconcile-skipped").stat().st_size, 1)

    def test_fast_path_does_not_wait_and_the_skipped_round_is_reported_next_time(self):
        f = self.hold()
        t0 = time.monotonic()
        out = self.run_round(fast=True)
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertEqual(out["lines"], [])
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
        out = self.run_round()
        self.assertTrue(any("1 kör kimaradt" in x for x in out["lines"]))
        self.assertEqual((self.st / "reconcile-skipped").stat().st_size, 0)
        self.assertFalse(any("kimaradt" in x for x in self.run_round()["lines"]))


class PostcheckWaitOutsideTheLock(Base):
    def test_fast_path_and_full_round_can_start_during_the_postcheck_wait(self):
        seen = {}

        def slow_postcheck(entry, restart_at=None, wait_s=90):
            seen["fast"] = self.run_round(fast=True)
            seen["full"] = self.run_round(observe=True)
            seen["skipped"] = (self.st / "reconcile-skipped").exists() and (self.st / "reconcile-skipped").stat().st_size
            return OKR

        def execute(e, action, m, st, *, now, log):
            reconcile.execute(e, action, m, st, now=now, log=log, sysctl=lambda *a, **k: 0, do_postcheck=slow_postcheck)

        out = self.run_round(measure=lambda _e: _m(proc="down"), unit_active=lambda u: False, execute_fn=execute)
        self.assertTrue(any("start végrehajtva" in x for x in out["lines"]), out["lines"])
        self.assertFalse(seen["skipped"])                       # egyik kör sem maradt ki
        self.assertTrue(any("skip:postcheck-in-progress" in x for x in seen["full"]["lines"]), seen["full"]["lines"])
        self.assertFalse(any("recheck" in x or "start —" in x for x in seen["full"]["lines"]))   # nincs dupla restart / recheck
        st = reconcile.load_state("probe-agent")
        self.assertIsNone(st["pending_postcheck"])               # a kör végén a rögzítés megtörtént
        self.assertEqual(len(st["restarts"]), 1)

    def test_postcheck_result_is_recorded_on_fresh_state(self):
        def slow_postcheck(entry, restart_at=None, wait_s=90):
            other = reconcile.load_state("probe-agent")
            other["bridge_restarts"] = [123.0]      # közben egy másik kör írt az állapotba
            reconcile.save_state("probe-agent", other)
            return OKR

        def execute(e, action, m, st, *, now, log):
            reconcile.execute(e, action, m, st, now=now, log=log, sysctl=lambda *a, **k: 0, do_postcheck=slow_postcheck)

        self.run_round(measure=lambda _e: _m(proc="down"), unit_active=lambda u: False, execute_fn=execute)
        self.assertEqual(reconcile.load_state("probe-agent")["bridge_restarts"], [123.0])

    def test_stale_claim_does_not_block_forever(self):
        now = time.time()
        st = reconcile.empty_state()
        st["pending_postcheck"] = {"restart_at": now - 1000, "claimed_at": now - reconcile.CLAIM_TTL_S - 1}
        acts = reconcile.decide(self.e, _m(), st, unit_active=True, locked=False, now=now)
        self.assertFalse(any(a.startswith("skip:postcheck") for a, _ in acts))


if __name__ == "__main__":
    unittest.main()
