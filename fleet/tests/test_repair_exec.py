"""flotta-menedzser: a javító végrehajtó. Engedélylista, a sorrend (zár → Worker-ellenőrzés → szándék →
végrehajtás → eredmény), ütköző zárak (box-szint vs ágens), kötelező felmérés bizonytalan lépés után,
újraindítási keret, dolgozó ágens, elavult fence, összeomlott lépés, registry-tripwire, nem igazolható
karantén-ok, nonce-os lezárás, elérhetetlen Worker. Valódi hálózat és valódi ágens nincs."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fleet import incident_cli, maintenance, repair_exec as X, repair_lock, repair_steps
from fleet.cli import build_parser
from fleet.repair_client import Worker
from _flotta_fake import Opener

AGENTS = [{"agent": "munkas", "host": "alfa"}, {"agent": "masik", "host": "alfa"}]
SECRET = "titkos-claim-0123456789"


class FakeWorker:
    def __init__(self, case, **answers):
        self.case, self.calls, self.answers = case, [], answers

    def _a(self, name, **kw):
        self.calls.append((name, kw))
        hook = self.answers.get(name + "_hook")
        if hook:
            hook()
        return self.answers.get(name, (True, {"code": "ok"}))

    def check(self, op_id, step, target): return self._a("check", step=step, target=target, op_id=op_id)
    def intent(self, op_id, step, target): return self._a("intent", step=step, op_id=op_id)
    def result(self, op_id, outcome, summary, assessment=None, step=None, target=None):
        return self._a("result", outcome=outcome, assessment=assessment, summary=summary, step=step, target=target)
    def verify_start(self): return self._a("verify_start")
    def verify_result(self, nonce, boot_id, green, summary): return self._a("verify_result", nonce=nonce, boot_id=boot_id, green=green)

    def names(self): return [c[0] for c in self.calls]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.dir, True)
        for obj, name, val in ((repair_lock, "ROOT", self.dir / "repair"), (incident_cli, "CLAIMS", self.dir / "claims")):
            p = mock.patch.object(obj, name, val); p.start(); self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"FLEET_MAINTENANCE_DIR": str(self.dir / "maint")}); p.start(); self.addCleanup(p.stop)
        self.executed = []
        self.steps = SimpleNamespace(
            busy=lambda e: False, registry_digest=lambda: "h1",
            doctor=lambda e: (self.executed.append("doctor") or ("ok", "healthy: ", "decided")),
            doctor_fix=self.fix, bridge_install=lambda e: ("ok", "híd", None),
            unquarantine=repair_steps.unquarantine,
            probe=lambda e: (True, "boot-1:42:100", "zöld"),
            report_now=lambda e: (self.executed.append("report") or True))
        self.save("agent:munkas")

    def fix(self, e):
        self.executed.append(("fix", maintenance.is_locked("munkas"), (self.dir / "maint" / "munkas").is_file()))
        return "ok", "--fix után: healthy", None

    def save(self, target):
        incident_cli.save_claim("i1", {"incident": "i1", "target": target, "fence": 7, "claim": SECRET,
                                       "attempt_until": "2999-01-01T00:00:00Z"})

    def run_x(self, step, agent="munkas", worker=None, cause=None, **kw):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = X.run("i1", step, agent, cause, worker=worker, steps=self.steps, host="alfa", agents=AGENTS,
                       say=lambda s: print(s), **kw)
        self.out = out.getvalue()
        return rc


class Allowlist(Base):
    def test_csak_az_engedelyezett_lepesek(self):
        w = FakeWorker(self)
        for bad in ("shell", "rm", "registry-set", "doctor;id"):
            self.assertEqual(self.run_x(bad, worker=w), X.USAGE)
        self.assertEqual(w.calls, [])
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                build_parser().parse_args(["repair-exec", "i1", "shell", "--agent", "munkas"])

    def test_csak_a_sajat_box_agense(self):
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", agent="idegen", worker=w), X.USAGE)
        self.assertEqual(w.calls, [])

    def test_az_atvetel_celja_kotott(self):
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", agent="masik", worker=w), X.USAGE)
        self.assertEqual(w.calls, [])


class Order(Base):
    def test_zar_majd_ellenorzes_szandek_vegrehajtas_eredmeny(self):
        def lock_is_held():   # az ellenőrzés pillanatában a cél zárja már nálunk van
            with self.assertRaises(repair_lock.Busy):
                with repair_lock.held("munkas"):
                    pass
            self.executed.append("check")
        w = FakeWorker(self, check_hook=lock_is_held, check=(True, {"attempt_until": "2999-01-01T00:00:00Z"}))
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.OK)
        self.assertEqual(w.names(), ["check", "intent", "result"])
        # a végrehajtás alatt: más processz zárat lát (fájl), ez a processz nem (a saját --fix-e fut)
        self.assertEqual(self.executed, ["check", ("fix", False, True)])
        self.assertFalse((self.dir / "maint" / "munkas").exists())   # a zár a végén felszabadul
        self.assertEqual(w.calls[0][1]["target"], "agent:munkas")
        self.assertEqual(w.calls[0][1]["op_id"], w.calls[1][1]["op_id"])

    def test_box_szintu_lepes_utkozik_az_agens_zarral_es_forditva(self):
        self.save("box:alfa")
        w = FakeWorker(self)
        with repair_lock.held("munkas"):
            self.assertEqual(self.run_x("doctor", agent=None, worker=w), X.LOCKED)
        self.save("agent:munkas")
        with repair_lock.held(None):
            self.assertEqual(self.run_x("doctor-fix", worker=w), X.LOCKED)
        self.assertEqual(w.calls, [])            # zár nélkül a Workert sem kérdezi
        with repair_lock.held("masik"):          # más ágens zárja nem ütközik
            self.assertEqual(self.run_x("doctor-fix", worker=w), X.OK)

    def test_kezi_karbantartasi_zar_alatt_nem_nyul(self):
        maintenance.lock("munkas", 30)
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertEqual(w.names(), ["check"]); self.assertTrue(maintenance.is_locked("munkas"))


class WorkerSays(Base):
    def test_elutasitott_ellenorzes_nem_lep(self):
        w = FakeWorker(self, check=(False, {"code": "stale"}))
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertEqual((w.names(), self.executed), (["check"], []))

    def test_elerhetetlen_worker_nem_lep(self):
        op = Opener((None, {}))
        w = Worker("i1", incident_cli.load_claim("i1"), cfg=("https://admin.invalid", "box-token"), opener=op)
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertEqual(self.executed, []); self.assertIn("unreachable", self.out)
        body = op.calls[0]["body"]
        self.assertEqual((body["fence"], body["claim"], body["step"]), (7, SECRET, "doctor-fix"))
        self.assertEqual(op.calls[0]["headers"]["X-mentat-token"], "box-token")
        self.assertNotIn(SECRET, self.out)

    def test_bizonytalan_utan_csak_doctor(self):
        w = FakeWorker(self, check=(True, {"must_assess": True}))
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertEqual(self.executed, [])
        self.assertEqual(self.run_x("doctor", worker=w), X.OK)
        self.assertEqual(w.calls[-1][1]["assessment"], "decided")

    def test_eldonthetetlen_felmeres_ember_kell(self):
        self.steps.doctor = lambda e: ("ok", "unknown: ? auth", "undecidable")
        self.assertEqual(self.run_x("doctor", worker=FakeWorker(self)), X.HUMAN)

    def test_elfogyott_ujrainditasi_keret(self):
        w = FakeWorker(self, intent=(False, {"code": "budget"}))
        self.assertEqual(self.run_x("bridge-install", worker=w), X.HUMAN)
        self.assertEqual((w.names(), self.executed), (["check", "intent"], []))

    def test_elavult_fence_az_eredmenynel(self):
        w = FakeWorker(self, result=(False, {"code": "stale"}))
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.WORKER)
        self.assertIn("elavult", self.out)


class Outcomes(Base):
    def test_osszeomlott_lepes_bizonytalan(self):
        def boom(e): raise RuntimeError("kilőtték")
        self.steps.doctor_fix = boom
        w = FakeWorker(self)
        self.assertEqual(self.run_x("doctor-fix", worker=w), X.FAIL)
        self.assertEqual(w.calls[-1][1]["outcome"], "uncertain")
        self.assertFalse((self.dir / "maint" / "munkas").exists())

    def test_registry_tripwire(self):
        vals = iter(["h1", "h2"])
        self.steps.registry_digest = lambda: next(vals)
        w = FakeWorker(self)
        self.assertEqual(self.run_x("bridge-install", worker=w), X.FAIL)
        self.assertEqual(w.calls[-1][1]["outcome"], "uncertain"); self.assertIn("REGISTRY", w.calls[-1][1]["summary"])

    def test_nem_igazolhato_karanten_ok(self):
        w = FakeWorker(self)
        self.assertEqual(self.run_x("unquarantine", worker=w, cause="szerintem-jo"), X.HUMAN)
        self.assertEqual(w.calls[-1][1]["outcome"], "refused")

    def test_igazolt_ok_de_nem_teljesul(self):
        w = FakeWorker(self)
        with mock.patch.object(repair_steps, "_cause_holds", lambda e, c: False):
            self.assertEqual(self.run_x("unquarantine", worker=w, cause="login-renewed"), X.FAIL)
        self.assertEqual(w.calls[-1][1]["outcome"], "failed")

    def test_dolgozo_agens_a_keret_vegeig_var_aztan_busy(self):
        self.steps.busy = lambda e: True
        clock = iter([100.0, 200.0, 5000.0, 9e9, 9e9])
        slept = []
        w = FakeWorker(self, check=(True, {"attempt_until": "1970-01-01T01:00:00Z"}))   # = 3600
        self.assertEqual(self.run_x("doctor-fix", worker=w, now=lambda: next(clock), sleep=slept.append), X.FAIL)
        self.assertEqual(w.names(), ["check", "result"]); self.assertEqual(w.calls[-1][1]["outcome"], "busy")
        self.assertTrue(slept and self.executed == [])

    def test_nema_de_elo_agens_ujraindithato(self):
        states = iter([True, False])   # egy kör várakozás, aztán a transzkript elcsendesül
        self.steps.busy = lambda e: next(states)
        w = FakeWorker(self, check=(True, {"attempt_until": "2999-01-01T00:00:00Z"}))
        self.assertEqual(self.run_x("doctor-fix", worker=w, now=lambda: 0.0, sleep=lambda s: None), X.OK)
        self.assertEqual(w.names(), ["check", "intent", "result"])


class Verify(Base):
    def test_zold_nonce_os_proba_zar_es_az_atvetel_torlodik(self):
        w = FakeWorker(self, verify_start=(True, {"nonce": "n-1"}), verify_result=(True, {"state": "megoldva"}))
        self.assertEqual(self.run_x("postcheck", worker=w), X.OK)
        self.assertEqual(w.names(), ["check", "verify_start", "verify_result"])
        self.assertEqual(w.calls[-1][1], {"nonce": "n-1", "boot_id": "boot-1:42:100", "green": True})
        self.assertEqual(self.executed, ["report"])   # a zöld előtt friss box-jelentés (a Worker abból igazol)
        self.assertIsNone(incident_cli.load_claim("i1"))

    def test_piros_proba_nem_zar(self):
        self.steps.probe = lambda e: (False, "boot-1:42:100", "piros: küldés")
        w = FakeWorker(self, verify_start=(True, {"nonce": "n-1"}), verify_result=(True, {"state": "javit"}))
        self.assertEqual(self.run_x("postcheck", worker=w), X.FAIL)
        self.assertIsNotNone(incident_cli.load_claim("i1"))

    def test_elavult_nonce(self):
        w = FakeWorker(self, verify_start=(True, {"nonce": "n-1"}), verify_result=(False, {"code": "stale"}))
        self.assertEqual(self.run_x("postcheck", worker=w), X.WORKER)

    def test_nyitott_muvelet_mellett_nincs_nonce(self):
        w = FakeWorker(self, verify_start=(False, {"code": "open_ops"}))
        self.assertEqual(self.run_x("postcheck", worker=w), X.WORKER)
        self.assertEqual(w.names(), ["check", "verify_start"])


class Scrub(unittest.TestCase):
    def test_token_nem_kerul_az_osszefoglaloba(self):
        s = repair_steps.scrub("hiba: mentat_AbCdEf0123456789xyz és 123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK0 vége")
        self.assertNotIn("mentat_AbCd", s); self.assertNotIn("AAAbbb", s); self.assertIn("vége", s)


if __name__ == "__main__":
    unittest.main()
