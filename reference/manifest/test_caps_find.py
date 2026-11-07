"""`where --find`: the user's own words, not capability names, land on what already exists.

The requests are the shape the holdouts' users actually wrote (the reinvention cases:
own executor + preview instead of the cases pack, own OAuth server, own web stack).
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from _caps_base import CapsBase

PLANNED = "írj egy új rutint, egy saját concernt"   # engine.concern_template: still planned
REQUESTS = [
    ("küldj nekik meghívót a péntekre", "google.calendar"),
    ("minden reggel írd ki, ki nem fizetett", "engine.cases"),
    ("csinálj egy kis felületet a listához", "web.publish"),
    ("kösd be a Google-táblát", "google.sheets"),
    ("tedd ki a netre", "web.publish"),
    ("mutasd meg, mi menne ki holnap reggel, de ne küldd el", "engine.preview"),
    ("a befizetési határidőket a csv-ből olvasd", "engine.csv_deadlines"),
    ("váltsunk egy olcsóbb modellre", "mentat.model"),
    ("csak a csapat lássa az oldalt", "cf.access"),
    ("jegyezd fel, hogy holnap hívjam fel a könyvelőt", "brain.new"),
    ("mi esedékes a héten?", "brain.due"),
    ("send them an invite for Friday", "google.calendar"),
    ("every morning tell me who has not paid", "engine.cases"),
    ("put the list online so I can see it on my phone", "web.publish"),
]

# Written AFTER the catalog, with other word forms, and never tuned against: a held-out set.
# Measured 2026-10-24: top-1 15/20, top-3 18/20; exact-word matching alone gets top-3 14/20.
UNSEEN = [
    ("küldd ki a meghívókat a csütörtöki megbeszélésre", "google.calendar"),
    ("reggelente szólj, ha valaki még nem fizetett", "engine.cases"),
    ("kellene egy felület, ahol a jelentkezőket látom", "web.publish"),
    ("a google táblázatból dolgozz", "google.sheets"),
    ("élesítsd az oldalt", "web.deploy"),
    ("legyen fent az interneten", "web.publish"),
    ("nézd meg, milyen üzenetet kapnék holnap", "engine.preview"),
    ("emlékeztess a határidők előtt", "engine.cases"),
    ("időzítsd, hogy óránként fusson", "engine.schedule"),
    ("állítsunk át egy olcsóbb modellre", "mentat.model"),
    ("jelszóval védd az oldalt", "cf.access"),
    ("írd fel teendőnek, hogy hívjam a szerelőt", "brain.new"),
    ("vedd át a régi asszisztens jegyzeteit", "takeover"),
    ("mondd el az oldalról, hogy működik-e", "web.check"),
    ("schedule a meeting invite for next week", "google.calendar"),
    ("remind me before the payments are due", "engine.cases"),
    ("make a little web page for the sign-ups", "web.publish"),
    ("connect my google spreadsheet", "google.sheets"),
    ("email them the summary", "google.gmail"),
    ("switch to a cheaper model", "mentat.model"),
]


class Find(CapsBase):
    def test_unseen_paraphrases_land_in_the_top_three(self):
        hits = sum(want in [c["id"] for c in self.find(q)["candidates"][:3]] for q, want in UNSEEN)
        self.assertGreaterEqual(hits / len(UNSEEN), 0.85, "%d/%d" % (hits, len(UNSEEN)))

    def test_original_requests_hit_the_existing_capability_first(self):
        misses = [(q, want, self.top(q)) for q, want in REQUESTS if self.top(q) != want]
        self.assertEqual(misses, [])

    def test_a_hit_carries_entry_steps_limits_extends_and_docs(self):
        c = self.by_id("minden reggel írd ki, ki nem fizetett", "engine.cases")
        for key in ("entry", "enable_steps", "limits", "extends", "docs", "provenance",
                    "availability", "lifecycle", "probe", "observed_at", "requires"):
            self.assertIn(key, c)
        self.assertIn("anytime_cases.new", c["entry"])
        self.assertTrue(c["docs"].startswith("https://"))

    def test_planned_capability_says_not_yet_and_what_to_do_until_then(self):
        c = self.by_id(PLANNED, "engine.concern_template")
        self.assertEqual((c["availability"], c["lifecycle"]), ("off", "planned"))
        self.assertIn("engine.cases", c["interim"])
        self.assertIsNone(c["entry"])

    def test_zero_hits_is_inconclusive_not_permission(self):
        out = self.find("fordítsd le ezt a verset szonettbe")
        self.assertEqual(out["verdict"], "inconclusive")
        self.assertEqual(out["candidates"], [])
        self.assertIsNone(out["recommendation"]["decision"])
        self.assertTrue(out["fallback"]["categories"])
        self.assertIn("next", out["fallback"])

    def test_human_output_names_the_receipt_and_the_decide_command(self):
        r = self.run_where("--find", "tedd ki a netre")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("web.publish", r.stdout)
        self.assertIn("nyugta", r.stdout)
        self.assertIn("where --decide", r.stdout)
        self.assertLessEqual(len(r.stdout.splitlines()), 30)

    def test_english_agent_gets_english_text(self):
        self.lang = "en"
        self.manifest({"components": {"brain": {"root": "brain"}}})
        r = self.run_where("--find", "put it online")
        self.assertIn("receipt", r.stdout)
        self.assertIn("Worker + D1", r.stdout)


if __name__ == "__main__":
    unittest.main()
