"""J5 held-out set: phrasings written after the tool and not tuned against it.

The bar is safety, not coverage: a phrase may come back `exact` only with the right dates; an
ambiguous one must be `confirm` and never `exact`; anything else may be `unknown` (the agent
then asks). Honest record (2026-10-24): batch 1 was partly tried by hand while building, so it
is not truly unseen (20/20 safe, 19 understood). Batch 2 was written after it and run once
cold: 2 of 14 were unsafe ("after the weekend" read as the weekend itself, "end of next week"
as the whole week); both are fixed and batch 2 is now regression, not fresh evidence. A real
held-out set needs another author.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import unittest

from mentat_dates import resolve

TODAY = datetime.date(2026, 10, 21)  # a Wednesday
# phrase -> the only acceptable exact answer (None: must not be exact) ; unknown always allowed
UNSEEN = {
    "Next Week": None, "the coming week": None, "a következő héten": None, "jövőhéten": None,
    "within two weeks": None, "két héten belül": None, "next weekend": None, "next month": None,
    "a jövő hónapban": None, "within 7 days": None, "last week": None, "end of the month": None,
    "until Friday": ("2026-10-21", "2026-10-23"), "péntekig": ("2026-10-21", "2026-10-23"),
    "the day after tomorrow": ("2026-10-23", "2026-10-23"), "holnapután": ("2026-10-23", "2026-10-23"),
    "hétvégén": ("2026-10-24", "2026-10-25"), "in a fortnight": ("2026-11-04", "2026-11-04"),
    "hét nap múlva": ("2026-10-28", "2026-10-28"), "nächste Woche": None,
    # batch 2
    "by next Tuesday": ("2026-10-21", "2026-10-27"), "in two days": ("2026-10-23", "2026-10-23"),
    "egy hét múlva": ("2026-10-28", "2026-10-28"), "a hét végéig": ("2026-10-21", "2026-10-25"),
    "this coming Thursday": None, "jövő hét elején": None, "mid-November": None, "after the weekend": None,
    "ezen a hétvégén": ("2026-10-24", "2026-10-25"), "két nap múlva": ("2026-10-23", "2026-10-23"),
    "end of next week": None, "by tonight": None, "next 3 days": None, "a következő 3 napban": None,
}


class Unseen(unittest.TestCase):
    def test_never_falsely_precise(self):
        understood = 0
        for phrase, exact in UNSEEN.items():
            r = resolve(phrase, "Europe/Budapest", TODAY)
            spans = [(c["start"], c["end"]) for c in r["candidates"]]
            if r["status"] == "exact":
                self.assertEqual(spans, [exact], phrase)
            if exact is None:
                self.assertNotEqual(r["status"], "exact", phrase)
            understood += r["status"] != "unknown"
        self.assertGreaterEqual(understood, 25)  # coverage floor; safety is the assertion above


if __name__ == "__main__":
    unittest.main()
