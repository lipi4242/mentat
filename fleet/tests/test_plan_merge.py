"""`fleet plan-merge`: a 2026-10-29-i utólagos sorrend, ahol mérhető, ott mért állapottal."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import subprocess
import unittest

from fleet import plan_merge

GIT_OK = {"behind": 0, "fetched": True, "path": "/x"}
OK = {"reachable": True, "auth": "ok", "problems": [], "fleet": GIT_OK, "registry": {"git": GIT_OK}}
EXPIRED = {"reachable": True, "auth": "expired",
           "problems": ["login lejárt 2026-10-28 óta (3 üzenet kapott hibát) — `fleet login donor`",
                        "fleet-checkout 12 committal az origin mögött (/h/fleet-ops) — `git -C /h/fleet-ops pull`"]}
DONOR = {"agent": "donor", "unit": "donor.service", "status": "active"}


def gh_with(prs, rc=0):
    return lambda args: subprocess.CompletedProcess(args, rc, json.dumps(prs) if rc == 0 else "", "")


def plan(probes, *, donor=DONOR, unit=("active", "enabled"), repos=(), gh=None):
    return {r["id"]: r for r in plan_merge.plan(
        "donor", "vilma", repos=repos, prober=lambda n: probes[n], units=lambda e: unit, gh=gh,
        get_agent=lambda n: donor if n == "donor" else None)}


class TestPlan(unittest.TestCase):
    def test_order_is_the_hindsight_order(self):
        ids = [r["id"] for r in plan_merge.plan(
            "donor", "vilma", prober=lambda n: OK, units=lambda e: None, get_agent=lambda n: None)]
        self.assertEqual(ids, [str(i) for i in range(9)])
        self.assertIn("csak olvas", plan_merge.STEPS[1][1])       # felmérés: semmi nem változik
        self.assertIn("a FOGADÓ írja", plan_merge.STEPS[1][1])    # az interjú válaszát a fogadó írja
        self.assertIn("MIELŐTT", plan_merge.STEPS[3][1])          # leállítás a login-gyógyítás előtt

    def test_stop_points_after_survey_and_before_outward_actions(self):
        stops = [s[0] for s in plan_merge.STEPS if s[3]]
        self.assertEqual(stops, ["2", "7"])
        self.assertIn("EGY üzenet", plan_merge.STEPS[2][1])
        for need in ("Telegram-csoport", "kulcs kié", "ajánlott"):
            self.assertIn(need, plan_merge.STEPS[2][1])
        self.assertIn("a FOGADÓ", plan_merge.STEPS[7][1])          # kifelé ható lépést a fogadó tesz
        rules = "\n".join(plan_merge.RULES)
        for need in ("TE nem teszel", "egy igen = egy lépés", "`fleet secrets copy`", "sosem állítod",
                     "nem törölsz", "`fleet retire`", "dormant"):
            self.assertIn(need, rules)

    def test_expired_login_becomes_a_human_dependency_and_stale_fleet_blocks_platform(self):
        p = plan({"donor": EXPIRED, "vilma": OK})
        self.assertEqual(p["0"]["status"], "teendő")
        self.assertEqual(p["2"]["status"], "teendő")                # a login-kód a STOP-üzenetbe kerül
        self.assertIn("`fleet login donor` — csak a 3. lépés UTÁN", "\n".join(p["2"]["notes"]))
        q = plan({"donor": OK, "vilma": EXPIRED})
        self.assertIn("`fleet login vilma`", "\n".join(q["1"]["notes"]))  # fogadó: az interjú előtt
        self.assertEqual(p["4"]["status"], "teendő")
        self.assertIn("mögött", "\n".join(p["4"]["notes"]))

    def test_all_green_where_measurable(self):
        p = plan({"donor": OK, "vilma": OK}, donor={**DONOR, "status": "dormant"}, unit=("inactive", "disabled"))
        for i in ("0", "3", "4", "8"):
            self.assertEqual(p[i]["status"], "kész", (i, p[i]))
        for i in ("1", "2", "5", "7"):
            self.assertEqual(p[i]["status"], "?", i)                  # ember/ágens dönti el

    def test_running_donor_is_todo_and_unknown_is_question(self):
        self.assertEqual(plan({"donor": OK, "vilma": OK})["3"]["status"], "teendő")
        self.assertEqual(plan({"donor": OK, "vilma": OK}, unit=("inactive", "enabled"))["3"]["status"], "teendő")
        self.assertEqual(plan({"donor": OK, "vilma": OK}, unit=None)["3"]["status"], "?")
        self.assertEqual(plan({"donor": OK, "vilma": OK}, donor=None)["8"]["status"], "?")

    def test_open_prs_writing_the_same_file(self):
        prs = [{"number": 7, "files": [{"path": "entry.py"}, {"path": "a.py"}]},
               {"number": 9, "files": [{"path": "entry.py"}]}]
        p = plan({"donor": OK, "vilma": OK}, repos=["o/vilma"], gh=gh_with(prs))
        self.assertEqual(p["6"]["status"], "teendő")
        self.assertIn("o/vilma: entry.py ← #7, #9", "\n".join(p["6"]["notes"]))
        p = plan({"donor": OK, "vilma": OK}, repos=["o/vilma"], gh=gh_with(prs[:1]))
        self.assertEqual(p["6"]["status"], "kész")
        p = plan({"donor": OK, "vilma": OK}, repos=["o/vilma"], gh=gh_with([], rc=1))
        self.assertEqual(p["6"]["status"], "?")
        self.assertEqual(plan({"donor": OK, "vilma": OK})["6"]["status"], "?")

    def test_format_marks(self):
        txt = plan_merge.format_plan(list(plan({"donor": EXPIRED, "vilma": OK}).values()))
        self.assertIn("[ ] 0.", txt)
        self.assertIn("[?] 5.", txt)
        self.assertIn("miért itt:", txt)
        self.assertTrue(txt.startswith("Szabályok (mindig):"))
        self.assertEqual(txt.count("⛔ ITT MEGÁLLSZ"), 2)


if __name__ == "__main__":
    unittest.main()
