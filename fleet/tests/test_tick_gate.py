"""a tick-kapu registry-mezői, a három preset, a timer-render és a 30↔60 váltás."""
import _hermetic  # noqa: F401
import unittest

from fleet import tick_gate as tg
from fleet import tick_gate_units as tu

H = 3600


def entry(**gate):
    return {"agent": "rel", "session": "rel", "workdir": "/tmp/rel",
            "tick_gate": {"tick_cmd": "python3 entry.py --trigger hourly", **gate}}


class Presets(unittest.TestCase):
    def test_rendszeres_az_alap_30_60_3ora(self):
        c = tg.config(entry())
        self.assertEqual((c["preset"], c["active_s"], c["idle_s"], c["idle_after_s"]), ("rendszeres", 1800, 3600, 10800))
        self.assertEqual(tg.problems(c), [])

    def test_mersekelt_ora_3ora(self):
        c = tg.config(entry(preset="mersekelt"))
        self.assertEqual((c["active_s"], c["idle_s"], c["idle_after_s"]), (3600, 10800, 10800))
        self.assertEqual(tg.problems(c), [])
        self.assertEqual(tg.calendars(c), ["OnCalendar=*-*-* 00/1:04:00 Europe/Budapest"])

    def test_reggel_este_ket_fix_idopont_nem_kerek_perc(self):
        c = tg.config(entry(preset="reggel-este"))
        self.assertEqual(c["at"], ["08:07", "18:07"])
        self.assertEqual(tg.calendars(c), ["OnCalendar=*-*-* 08:07:00 Europe/Budapest",
                                           "OnCalendar=*-*-* 18:07:00 Europe/Budapest"])
        self.assertEqual(tg.base_period_s(c), 14 * H)            # 18:07 → 08:07 a leghosszabb rés
        c2 = tg.config(entry(preset="reggel-este", at=["07:41", "19:13"]))
        self.assertEqual(tg.problems(c2), [])

    def test_valasz_szamok_a_presetekre(self):
        self.assertEqual([tg.ANSWERS[k] for k in "123"], ["rendszeres", "mersekelt", "reggel-este"])

    def test_a_kerdes_szovege(self):
        q = tg.QUESTION
        self.assertIn("nagyon olcsó", q); self.assertIn("nem fut AI", q)
        self.assertIn("Rendszeres (aktív fejlesztéshez) (ajánlott)", q)
        self.assertIn("Mérsékelt", q); self.assertIn("Reggel és este", q)
        self.assertEqual(q.count("(ajánlott)"), 1)


class Problems(unittest.TestCase):
    def test_tiltott_tick_cmd_es_ismeretlen_preset(self):
        self.assertTrue(tg.problems(tg.config(entry(tick_cmd="x; rm -rf ~"))))
        self.assertTrue(tg.problems(tg.config(entry(preset="ejjel"))))
        self.assertTrue(tg.problems(tg.config(entry(daily_at=["25:00"]))))
        self.assertTrue(tg.problems(tg.config(entry(active_s=1800, idle_s=2700))))   # nem többszörös
        self.assertTrue(tg.problems(tg.config(entry(check="rm -rf /"))))           # parancs csak argv-lista
        self.assertEqual(tg.problems(tg.config(entry(check=["/usr/bin/true"]))), [])

    def test_kapu_nelkul_nincs_config_es_nincs_unit(self):
        self.assertIsNone(tg.config({"agent": "x"}))
        self.assertEqual(tu.render({"agent": "x"}, "/f"), {})


class Interval(unittest.TestCase):
    def test_30_60_valtas_a_3_oras_hataron(self):
        c, now = tg.config(entry()), 1_000_000.0
        self.assertEqual(tg.interval_s(c, now - 60, now), 1800)
        self.assertEqual(tg.interval_s(c, now - (3 * H - 1), now), 1800)
        self.assertEqual(tg.interval_s(c, now - 3 * H, now), 3600)
        self.assertEqual(tg.interval_s(c, None, now), 3600)          # sosem volt munka: tétlen

    def test_mersekelt_3_ora_utan_3_oranként(self):
        c, now = tg.config(entry(preset="mersekelt")), 1_000_000.0
        self.assertEqual(tg.interval_s(c, now - 2 * H, now), 3600)
        self.assertEqual(tg.interval_s(c, now - 4 * H, now), 3 * H)

    def test_tetlen_modban_a_kozbenso_tuzeles_kimarad(self):
        now = 1_000_000.0
        st = {"next_due_at": now + 3600}
        self.assertFalse(tg.due(st, now + 1800))
        self.assertTrue(tg.due(st, now + 3600 - 60))                  # timer-pontatlanság tűrve
        self.assertTrue(tg.due({}, now))
        self.assertTrue(tg.due({"next_due_at": "romlott"}, now))
        self.assertTrue(tg.due({"next_due_at": now + 9 * 86400}, now))         # visszaugrott óra után sem némul el


class Render(unittest.TestCase):
    def test_timer_es_service(self):
        files = tu.render(entry(offset_min=9), "%h/src/mentat/fleet")
        timer, svc = files["fleet-gate-rel.timer"], files["fleet-gate-rel.service"]
        self.assertIn("OnCalendar=*-*-* *:09,39:00 Europe/Budapest", timer)
        self.assertIn("Persistent=false", timer)
        self.assertIn("ExecStart=%h/src/mentat/fleet/bin/fleet tick-gate run rel", svc)
        self.assertIn("TimeoutStartSec=30", svc)

    def test_hibas_kapu_nem_renderelheto(self):
        with self.assertRaises(ValueError):
            tu.render(entry(tick_cmd="a`b`"), "/f")


if __name__ == "__main__":
    unittest.main()
