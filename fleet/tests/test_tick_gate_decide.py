"""a kapu döntése (munka / nincs munka / foglalt / hiba / korlát / nyugta) és a munka-definíció."""
import _hermetic  # noqa: F401
import unittest
from datetime import datetime, timezone

from fleet import release_work as rw
from fleet import tick_gate as tg
from fleet import tick_gate_decide as dec

H = 3600
NOW = datetime(2026, 11, 8, 13, 0, tzinfo=timezone.utc).timestamp()   # 14:00 Budapest
CFG = tg.config({"agent": "r", "tick_gate": {"tick_cmd": "python3 entry.py --trigger hourly", "daily_at": ["10:04"]}})


def obs(reasons=(), activity=None, error=None, commit=None, busy=None):
    return {"reasons": list(reasons), "activity": bool(reasons) if activity is None else activity,
            "error": error, "commit": commit or {}, "busy": busy}


def d(gate, o, last=None, now=NOW):
    return dec.decide(CFG, gate, o, now=now, last_tick_at=last, busy=None)


class Decide(unittest.TestCase):
    def test_nincs_munka_tetlen_es_a_commit_lep(self):
        r = d({}, obs(commit={"seen": ["a#1@x:-:-"]}), last=NOW - 60)
        self.assertEqual(r["action"], "idle")
        self.assertEqual(r["state"]["seen"], ["a#1@x:-:-"])
        self.assertEqual(r["interval_s"], 3600)                       # sosem volt munka → óránként

    def test_munka_beküld_és_30_percre_áll(self):
        r = d({}, obs(["új/változott PR: a#1"], commit={"seen": ["a#1@x:-:-"]}), last=NOW - 2 * H)
        self.assertEqual(r["action"], "inject")
        self.assertEqual((r["interval_s"], r["state"]["day_count"]), (1800, 1))
        self.assertEqual(r["state"]["await_ack"]["prev"], {"seen": None})

    def test_aktivitas_beküldés_nélkül_is_sűrűn_tart(self):
        r = d({}, obs(activity=True), last=NOW - 60)                  # pl. 👍-ra váró PR
        self.assertEqual((r["action"], r["interval_s"]), ("idle", 1800))
        r2 = d({"last_activity_at": NOW - 3 * H}, obs(), last=NOW - 60)
        self.assertEqual(r2["interval_s"], 3600)                       # 3 óra munka nélkül → 60

    def test_napi_kör_nem_tartja_sűrűn(self):
        r = d({"last_activity_at": NOW - 4 * H}, obs(["napi kör esedékes (10:04)"], activity=False), last=NOW - 5 * H)
        self.assertEqual((r["action"], r["interval_s"]), ("inject", 3600))

    def test_foglalt_nem_kuld_es_a_commit_nem_lep(self):
        r = d({"seen": []}, obs(["új PR"], commit={"seen": ["a#1@x:-:-"]}, busy="lease él"))
        self.assertEqual(r["action"], "busy")
        self.assertEqual(r["state"]["seen"], [])
        self.assertEqual(r["next_due_at"], NOW + 1800)                 # a következő tüzelésnél újra
        self.assertEqual(r["state"]["pending_since"], NOW)

    def test_halozati_hiba_friss_ticknel_kimarad(self):
        r = d({}, obs(error="github: URLError"), last=NOW - 10 * 60)
        self.assertEqual(r["action"], "error")

    def test_halozati_hiba_regi_ticknel_beküld_visszalépő_küszöbbel(self):
        self.assertEqual(d({}, obs(error="github: x"), last=NOW - 2 * H)["action"], "inject")
        # 3. egymást követő hiba: a küszöb 4 óra — 2 órás tick még nem elég
        self.assertEqual(d({"errors": 2}, obs(error="github: x"), last=NOW - 2 * H)["action"], "error")
        self.assertEqual(d({"errors": 2}, obs(error="github: x"), last=NOW - 5 * H)["action"], "inject")

    def test_hurok_korlat_min_tavolsag_es_napi_plafon(self):
        self.assertEqual(d({"injected_at": NOW - 600}, obs(["x"]))["action"], "capped")
        self.assertEqual(d({"day": "2026-11-08", "day_count": 48}, obs(["x"]))["action"], "capped")
        self.assertEqual(d({"day": "2026-11-07", "day_count": 48}, obs(["x"]))["action"], "inject")


class Ack(unittest.TestCase):
    def test_elveszett_beküldés_visszaáll(self):
        g = {"seen": ["új"], "injected_at": NOW, "day_count": 2,
             "await_ack": {"at": NOW, "prev": {"seen": ["régi"], "todo_seq": None}}}
        self.assertEqual(dec.settle_ack(g, NOW - 3600, now=NOW + 60), (g, None))   # még korai ítélni
        self.assertEqual(dec.settle_ack(g, None, now=NOW + 60), (g, None))          # mérhetetlen: a nyugta vár
        st, why = dec.settle_ack(g, transcript_mtime=NOW - 3600, now=NOW + 1800)
        self.assertEqual(st["seen"], ["régi"]); self.assertNotIn("todo_seq", st)
        self.assertEqual((st["injected_at"], st["day_count"]), (NOW, 1))          # a napi keret visszajár
        self.assertIn("nem érkezett meg", why)

    def test_megérkezett_beküldés_marad(self):
        g = {"seen": ["új"], "await_ack": {"at": NOW, "prev": {"seen": ["régi"]}}}
        st, why = dec.settle_ack(g, transcript_mtime=NOW + 30, now=NOW + 1800)
        self.assertEqual((st["seen"], why), (["új"], None)); self.assertNotIn("await_ack", st)


class WorkDefinition(unittest.TestCase):
    def pr(self, n, head, draft=False, ci="SUCCESS"):
        return {"number": n, "isDraft": draft, "headRefOid": head, "reviewDecision": None,
                "repository": {"nameWithOwner": "O/R"}, "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": ci}}}]}}

    def test_ujlenyomat_draft_kimarad_ci_valtozas_munka(self):
        fps = rw.fingerprints([self.pr(1, "a"), self.pr(2, "b", draft=True)])
        self.assertEqual(fps, ["o/r#1@a:SUCCESS:-"])
        self.assertEqual(rw.queue_reasons(fps, fps), [])                     # változatlan: nem munka
        pend = rw.fingerprints([self.pr(1, "a", ci="PENDING")])
        self.assertTrue(rw.queue_reasons(fps, pend))                         # CI lefutott, head ugyanaz
        self.assertEqual(rw.queue_reasons([], fps), ["kikerült a sorból: o/r#1"])

    def test_lejaro_jegy_es_lease(self):
        st = {"repos": {"o/r": {"approvals": {"5": {"requested_at": "2026-11-07T02:00:00+00:00"},
                                              "6": {"requested_at": "2026-11-08T12:00:00+00:00"},
                                              "7": {"requested_at": "2026-11-06T00:00:00Z", "consumed": True}}}},
              "lease": {"renewed_at": "2026-11-08T12:50:00Z"}}
        live, exp = rw.approvals(st, NOW, 3600)
        self.assertEqual((live, exp), (2, ["o/r#5@2026-11-07T02:00:00+00:00"]))
        self.assertTrue(rw.lease_held(st, NOW, 25))
        self.assertFalse(rw.lease_held(st, NOW + 30 * 60, 25))

    def test_napi_kor_helyi_idoben(self):
        self.assertEqual(rw.daily_due(["10:04"], "Europe/Budapest", NOW - 5 * H, NOW), "10:04")
        self.assertIsNone(rw.daily_due(["10:04"], "Europe/Budapest", NOW - 60, NOW))
        self.assertIsNone(rw.daily_due([], "Europe/Budapest", None, NOW))

    def test_sajat_todo_iras_nem_munka(self):
        ev = [{"seq": 1, "actor_id": "p_me"}, {"seq": 2, "actor_id": "p_dev"}]
        self.assertEqual([e["seq"] for e in rw.foreign(ev, "p_me")], [2])


if __name__ == "__main__":
    unittest.main()
