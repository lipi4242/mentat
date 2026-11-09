"""flotta-menedzser: a box-jelentés viszi a végrehajtó önpróbáját, és a Worker coverage-válasza a doctor
box-sorába kerül: ember-kell piros; fedetlen, alkalmatlan menedzser, >2 átadás ⚠; a Worker
elérhetetlensége piros + tartalék-fájl, és újra friss jelentésnél a fájl eltűnik."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import unittest
from unittest import mock

from fleet import flotta_coverage as C, flotta_report as F, repair_lock
from test_flotta_report import Base, TOKEN

COV = {"uncovered": [{"target": "box:gondnok", "why": "nincs másik boxon elérő menedzser"}],
       "unfit": [{"agent": "helyettes", "why": "javító-próba piros"}],
       "human_needed": [{"incident": "i1", "target": "agent:vilma"}],
       "handovers": [{"incident": "i2", "target": "agent:szervezo", "handovers": 3},
                     {"incident": "i3", "target": "agent:x", "handovers": 2}]}


class Resp(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Coverage(Base):
    def setUp(self):
        super().setUp()
        for obj, name in ((repair_lock, "ROOT"), ):
            p = mock.patch.object(obj, name, self.dir / "state/repair"); p.start(); self.addCleanup(p.stop)
        self.sent = []

    def opener(self, req, timeout=None):
        self.sent.append((dict(req.header_items()), json.loads(req.data)))
        return Resp(json.dumps({"ok": True, "coverage": COV}).encode())

    def test_a_jelentes_viszi_a_javito_probat_es_megorzi_a_coverage_t(self):
        self.configure("https://admin.invalid")
        with mock.patch.dict("os.environ", {"FLEET_MAINTENANCE_DIR": str(self.dir / "maint")}):
            self.assertEqual(F.maybe_report({}, [], "gondnok", 1e9, opener=self.opener), "sent")
        body = self.sent[0][1]
        self.assertEqual(body["repair"], {"ok": True, "detail": "végrehajtó kész"})
        probs, warn, facts, _ = F.status(1e9 + 60)
        self.assertEqual(len(probs), 1); self.assertIn("ember kell: agent:vilma", probs[0])
        self.assertTrue(any(w.startswith("fedetlen: box:gondnok") for w in warn), warn)
        self.assertTrue(any("alkalmatlan menedzser: helyettes" in w for w in warn), warn)
        self.assertTrue(any("3 átadás" in w for w in warn) and not any("2 átadás" in w for w in warn), warn)
        self.assertNotIn(TOKEN, json.dumps([probs, warn, facts]))

    def test_piros_javito_proba_ha_nem_irhato(self):
        self.configure("https://admin.invalid")
        with mock.patch.object(C, "_writable", lambda d: "repair" not in str(d)):
            r = C.repair_probe()
        self.assertFalse(r["ok"]); self.assertIn("javító-zár", r["detail"])

    def test_elerhetetlen_majd_ujra_friss_a_tartalek_fajl_eltunik(self):
        self.configure("https://admin.invalid")
        self.assertEqual(F.maybe_report({}, [], "gondnok", 1e9, opener=self.opener), "sent")
        probs, _, _, _ = F.status(1e9 + F.STALE_S + 5)
        self.assertTrue(probs[0].startswith("jelentés: elavult") and C.UNREACHABLE.is_file())
        F.maybe_report({}, [], "gondnok", 1e9 + F.STALE_S + 10, opener=self.opener)
        F.status(1e9 + F.STALE_S + 20)
        self.assertFalse(C.UNREACHABLE.exists())

    def test_csendes_ha_nincs_mit_mondani(self):
        self.assertEqual(C.lines({"uncovered": [], "unfit": [], "human_needed": [], "handovers": []}), ([], []))
        self.assertEqual(C.lines(None), ([], []))


if __name__ == "__main__":
    unittest.main()
