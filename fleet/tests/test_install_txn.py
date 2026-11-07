"""Tranzakciós telepítés: hamis systemctl/claude a PATH elején.

Amit az elfogadási teszt mért egy friss Ubuntun: `fleet install` után a unit
inaktív (a claude azonnal kilépett), nem jött fel reconcile-timer, és semmi
nem mondta, hogy nem sikerült. Ezek a tesztek ezt a hármat zárják ki.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import sys
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet import registry, install, install_checks, install_flow  # noqa: E402
from fleet.txn import StepFailed  # noqa: E402
from fakebin import FakeBin  # noqa: E402


def _entry(**kw):
    base = {"agent": "probe", "workdir": "/home/x/probe", "host": "box1",
            "proactive": False, "tick_period_s": 3600}
    base.update(kw)
    return registry.normalize(base)


def _proc(state, pid=None):
    return {"signals": {"process": {"state": state, "data": {"pid": pid}, "detail": ""}}}


def measure_seq(*states):
    """Egymás utáni mérések; az utolsó ismétlődik."""
    seq = list(states)

    def m(_e):
        return seq.pop(0) if len(seq) > 1 else seq[0]
    return m


def pc(status, problems=(), pending=()):
    return lambda e, restart_at=None, wait_s=0: {"status": status, "problems": list(problems),
                                                 "pending": list(pending)}


class Base(unittest.TestCase):
    def setUp(self):
        self.fb = FakeBin()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.ud, self.cfg, self.reg = root / "units", root / "cfg", root / "reg"
        self.ud.mkdir(); self.reg.mkdir()
        self.home = root / "home"
        (self.home / ".config/probe").mkdir(parents=True)
        (self.home / ".config/probe/telegram.env").write_text("")
        self.pending = []

    def tearDown(self):
        self.fb.cleanup(); self.tmp.cleanup()

    def install(self, entry=None, **kw):
        args = dict(unit_dir=self.ud, config_dir=self.cfg, registry=self.reg, host="box1",
                    claude_bin=self.fb.claude, sleep=lambda s: None, wait_s=4, stable_s=1,
                    measure=measure_seq(_proc("up", 7)), postcheck_fn=pc("ok"),
                    record_pending=lambda a, t: self.pending.append(a), home=self.home,
                    tmux_bin=self.fb.tmux, environ={})
        args.update(kw)
        return install_flow.install_agent(entry or _entry(), **args)


class TestInstallUnitChecksExitCodes(Base):
    def test_failed_enable_rolls_back_unit_and_dropin(self):
        old = "[Unit]\nDescription=régi\n"
        (self.ud / "probe.service").write_text(old)
        self.fb.fail_on("enable probe.service")
        with self.assertRaises(StepFailed):
            install.install_unit(_entry(), unit_dir=self.ud, config_dir=self.cfg)
        self.assertEqual((self.ud / "probe.service").read_text(), old)
        self.assertFalse((self.ud / "probe.service.d" / "10-session-gate.conf").exists())


class TestRollbackOrder(Base):
    def test_rollback_disables_new_units_and_reenables_restored_ones(self):
        # élesben mérve mindkét irány bukott: az új timer letiltása a fájl
        # törlése UTÁN, a régi engedélyezése a visszaírás ELŐTT
        self.fb.units_in(self.ud)
        for n in ("agent-liveness.timer", "agent-liveness.service"):
            (self.ud / n).write_text("[Unit]\n")
        self.fb.set_active("agent-liveness.timer")
        r = self.install(measure=measure_seq(_proc("down")))
        self.assertEqual(r["status"], "failed")
        self.assertFalse(any(n.startswith("visszaállítás:") for n in r["notes"]), r["notes"])
        active = self.fb.dir / "active"
        self.assertTrue((active / "agent-liveness.timer").exists())
        self.assertFalse((active / "fleet-reconcile.timer").exists())
        self.assertTrue((self.ud / "agent-liveness.timer").exists())


class TestMissingEnvFile(Base):
    UNGUARDED = "ExecStart=tmux ... /bin/sh -c 'set -a; . %h/.config/probe/telegram.env 2>/dev/null; set +a; exec claude'"
    GUARDED = "ExecStart=tmux ... /bin/sh -c 'set -a; if [ -r %h/.config/probe/telegram.env ]; then . %h/.config/probe/telegram.env; fi; set +a'"

    def test_unguarded_source_with_missing_env_file_is_a_precheck_failure(self):
        home = Path(self.tmp.name) / "uj"
        got = install_checks.env_file_problem(_entry(), home=home, unit_text=self.UNGUARDED)
        self.assertIn("hiányzik az env-fájl", got[0])
        (home / ".config/probe").mkdir(parents=True)
        (home / ".config/probe/telegram.env").write_text("")
        self.assertEqual(install_checks.env_file_problem(_entry(), home=home, unit_text=self.UNGUARDED), [])

    def test_guarded_template_needs_no_env_file_but_warns(self):
        home = Path(self.tmp.name) / "uj"
        self.assertEqual(install_checks.env_file_problem(_entry(), home=home, unit_text=self.GUARDED), [])
        got = install_checks.env_file_check(_entry(), home=home, unit_text=self.GUARDED)
        self.assertEqual(got["errors"], [])
        self.assertIn("nincs env-fájl", got["warnings"][0])


class TestInstallFlow(Base):
    def test_green_install_brings_up_supervision_and_removes_liveness(self):
        (self.ud / "agent-liveness.timer").write_text("[Timer]\n")
        (self.ud / "agent-liveness.service").write_text("[Service]\n")
        r = self.install()
        self.assertEqual(r["status"], "ok", r)
        calls = self.fb.calls()
        self.assertIn("systemctl --user disable --now agent-liveness.timer", calls)
        self.assertIn("systemctl --user enable --now fleet-reconcile.timer", calls)
        self.assertIn("systemctl --user restart probe.service", calls)
        self.assertFalse((self.ud / "agent-liveness.timer").exists())
        svc = (self.ud / "fleet-reconcile.service").read_text()
        self.assertIn(install.fleet_root_for_units() + "/bin/fleet reconcile", svc)
        self.assertEqual((self.cfg / "controller").read_text().strip(), "reconcile")
        self.assertEqual((self.cfg / "registry").read_text().strip(), str(self.reg))

    def test_claude_exits_immediately_is_a_loud_failure_with_journal_and_rollback(self):
        self.fb.journal("x.service:11: Unit uses KillMode=none. This is unsafe\ntmux new-session ok\n")
        self.fb.claude_says("Credit balance is too low\n")
        r = self.install(measure=measure_seq(_proc("up", 7), _proc("down")))
        self.assertIn("tmux new-session ok", r["journal"])
        self.assertFalse(any("KillMode" in x for x in r["journal"]))
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("azonnal kilépett" in p for p in r["problems"]), r["problems"])
        self.assertIn("claude -p: Credit balance is too low", r["journal"])
        # friss telepítés volt: semmi nem marad utána
        self.assertFalse((self.ud / "probe.service").exists())
        self.assertFalse((self.ud / "probe.service.d").exists())
        self.assertFalse((self.ud / "fleet-reconcile.timer").exists())
        self.assertIn("systemctl --user stop probe.service", self.fb.calls())
        self.assertIn("systemctl --user disable probe.service", self.fb.calls())

    def test_never_comes_up_is_failure(self):
        r = self.install(measure=measure_seq(_proc("down")))
        self.assertEqual(r["status"], "failed")

    def test_failed_postcheck_rolls_back_and_restarts_previous_unit(self):
        old = "[Unit]\nDescription=régi\n"
        (self.ud / "probe.service").write_text(old)
        self.fb.set_active("probe.service")
        r = self.install(postcheck_fn=pc("failed", problems=["telegram 409"]))
        self.assertEqual(r["status"], "failed")
        self.assertEqual((self.ud / "probe.service").read_text(), old)
        self.assertIn("az előző unit visszaállítva és újraindítva", r["notes"])

    def test_pending_postcheck_is_not_done_and_is_handed_to_reconcile(self):
        r = self.install(postcheck_fn=pc("pending", pending=["ütemezés: még nincs tick"]))
        self.assertEqual(r["status"], "pending")
        self.assertEqual(self.pending, ["probe"])
        self.assertTrue((self.ud / "probe.service").exists())

    def test_logged_out_claude_stops_before_any_write(self):
        self.fb.logged_out()
        r = self.install()
        self.assertEqual(r["status"], "failed")
        self.assertIn("claude auth login", " ".join(r["problems"]))
        self.assertFalse((self.ud / "probe.service").exists())

    def test_missing_claude_binary_stops_before_any_write(self):
        r = self.install(claude_bin=Path(self.tmp.name) / "nincs" / "claude")
        self.assertEqual(r["status"], "failed")
        self.assertIn("hiányzik a claude bináris", r["problems"][0])
        self.assertFalse((self.ud / "probe.service").exists())

    def _with_unit_text(self, text):
        orig = install.unit_text_for
        install.unit_text_for = lambda e: text
        self.addCleanup(setattr, install, "unit_text_for", orig)

    def test_missing_env_file_with_unguarded_template_stops_before_any_write(self):
        # a sablonjavítás (#6) ELŐTTI unit: a hiányzó env-fájl a shellt leállítaná
        self._with_unit_text(TestMissingEnvFile.UNGUARDED)
        (self.home / ".config/probe/telegram.env").unlink()
        r = self.install()
        self.assertEqual(r["status"], "failed")
        self.assertIn("hiányzik az env-fájl", " ".join(r["problems"]))
        self.assertFalse((self.ud / "probe.service").exists())

    def test_missing_env_file_with_guarded_template_is_only_a_warning(self):
        # a sablonjavítás UTÁNI unit: indul env-fájl nélkül is → figyelmeztetés, nem hiba
        self._with_unit_text(TestMissingEnvFile.GUARDED)
        (self.home / ".config/probe/telegram.env").unlink()
        r = self.install()
        self.assertEqual(r["status"], "ok", r)
        self.assertTrue(any("nincs env-fájl" in n for n in r["notes"]), r["notes"])
        self.assertTrue((self.ud / "probe.service").exists())

    def test_other_host_is_refused(self):
        r = self.install(host="masik-gep")
        self.assertEqual(r["status"], "failed")
        self.assertIn("box1", r["problems"][0])

    def test_inactive_reconcile_timer_after_enable_fails(self):
        self.fb.fail_on("is-active fleet-reconcile.timer")
        r = self.install()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(any("fleet-reconcile.timer nem aktív" in p for p in r["problems"]), r)


if __name__ == "__main__":
    unittest.main()
