"""11-08: a todo-ébresztés egészsége a képesség-próbában és a központi jelentésben.

A híd health-fájljából: az utolsó sikeres todo-poll kora, az ébresztés késése, a feldolgozatlan
ébresztések. Piros → `todo-ebresztes` kulcs a flotta-jelentésben → a #53 rendes útján incidens."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import json
import time
import unittest

from _essentials_box import entry, make_box
from fleet import flotta_report as F, kepesseg_todo as T

NOW = 1_800_000_000.0


class TodoWake(unittest.TestCase):
    def setUp(self):
        self.home = make_box(self)
        (self.home / ".config/todo").mkdir(parents=True)
        (self.home / ".config/todo/env").write_text("TODO_API=https://admin.example/api/todo/v1\n")
        self.e = entry("vilma")
        self.hp = self.home / ".config/vilma/telegram-state/health.json"
        self.hp.parent.mkdir(parents=True)

    def run_check(self, health=None):
        if health is not None:
            self.hp.write_text(json.dumps(health))
        out = {"red": [], "unknown": [], "ok": []}
        T.check(self.e, self.home, out, now=NOW)
        return out

    def test_friss_poll_zold_kesessel(self):
        out = self.run_check({"todo_wake": "on", "todo_last_poll_ok": (NOW - 15) * 1000, "todo_last_wake_latency_ms": 41_000,
                              "todo_unhandled": 0})
        self.assertEqual(out["red"], [])
        self.assertEqual(out["ok"], ["todo-ébresztés (poll 15 s ezelőtt, utolsó késés 41 s)"])

    def test_leallt_poll_piros_es_incidens_kulcsot_kap(self):
        out = self.run_check({"todo_wake": "on", "todo_last_poll_ok": (NOW - 900) * 1000,
                              "todo_last_error": "todo API elérhetetlen (timeout)"})
        self.assertEqual(len(out["red"]), 1, out)
        self.assertIn("15 perce nincs sikeres todo-poll", out["red"][0])
        self.assertIn("timeout", out["red"][0])
        rep = F.build({"vilma": {"at": NOW, **out}}, ["vilma"], "box", self.home)
        self.assertEqual([r["check"] for r in rep["agents"][0]["red"]], ["todo-ebresztes"])

    def test_soha_nem_pollozott_piros(self):
        out = self.run_check({"todo_wake": "on"})
        self.assertIn("∞ perce", out["red"][0])

    def test_feldolgozatlan_ebresztes_piros(self):
        out = self.run_check({"todo_wake": "on", "todo_last_poll_ok": (NOW - 5) * 1000, "todo_unhandled": 2})
        self.assertIn("2 ébresztés feldolgozatlan", out["red"][0])
        self.assertIn("delivery.mjs", out["red"][0])

    def test_ki_okkal_piros_ok_nelkul_ismeretlen(self):
        self.assertIn("KI: todo token", self.run_check({"todo_wake": "off: todo token /x másnak is olvasható"})["red"][0])
        self.assertEqual(self.run_check({"todo_wake": "off"})["red"], [])

    def test_regi_hid_es_hianyzo_health_ismeretlen_nem_piros(self):
        out = self.run_check({"last_poll_ok": 1})
        self.assertEqual(out["red"], [])
        self.assertIn("fleet bridge install vilma", out["unknown"][0])
        self.hp.unlink()
        out = self.run_check()
        self.assertEqual(out["red"], [])
        self.assertTrue(out["unknown"])

    def test_todo_nelkuli_box_vagy_hid_nelkuli_agens_nem_mert(self):
        (self.home / ".config/todo/env").unlink()
        self.assertEqual(self.run_check({"todo_wake": "on"}), {"red": [], "unknown": [], "ok": []})
        (self.home / ".config/todo/env").write_text("TODO_API=x\n")
        self.e = entry("vilma", bridge=None)
        self.assertEqual(self.run_check({"todo_wake": "on"}), {"red": [], "unknown": [], "ok": []})


if __name__ == "__main__":
    unittest.main()
