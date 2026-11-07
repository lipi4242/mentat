"""J5: mentat_dates.py turns a relative time phrase into dates, or says it is ambiguous.

Class of error (holdout, 0.3.0): "next week" became a 14-day window without a question, and
that wrong window sent a wrong morning list. The tool never picks one reading of an ambiguous
phrase: it lists them (exit 3) and the agent asks; what it does not understand is unknown
(exit 1), never a guess. Today is fixed: Wednesday 2026-10-21.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import subprocess
import sys
import unittest

from _contract_fixture import HERE
from mentat_dates import resolve

TODAY = datetime.date(2026, 10, 21)
NEXT_WEEK = [("2026-10-26", "2026-11-01"), ("2026-10-22", "2026-10-28")]
SEEN = [  # (phrase, status, [(start, end), ...]) — English and Hungarian side by side
    ("next week", "confirm", NEXT_WEEK), ("jövő héten", "confirm", NEXT_WEEK),
    ("due next week", "confirm", NEXT_WEEK), ("a jövő héten esedékes", "confirm", NEXT_WEEK),
    ("tomorrow", "exact", [("2026-10-22", "2026-10-22")]), ("holnap", "exact", [("2026-10-22", "2026-10-22")]),
    ("in 3 days", "exact", [("2026-10-24", "2026-10-24")]), ("3 nap múlva", "exact", [("2026-10-24", "2026-10-24")]),
    ("by the end of the month", "exact", [("2026-10-21", "2026-10-31")]),
    ("a hónap végéig", "exact", [("2026-10-21", "2026-10-31")]),
    ("on Friday", "exact", [("2026-10-23", "2026-10-23")]), ("pénteken", "exact", [("2026-10-23", "2026-10-23")]),
    ("next Friday", "confirm", [("2026-10-23", "2026-10-23"), ("2026-10-30", "2026-10-30")]),
    ("jövő pénteken", "confirm", [("2026-10-23", "2026-10-23"), ("2026-10-30", "2026-10-30")]),
    ("next Monday", "exact", [("2026-10-26", "2026-10-26")]),
    ("this week", "confirm", [("2026-10-19", "2026-10-25"), ("2026-10-21", "2026-10-25")]),
    ("2026-11-05", "exact", [("2026-11-05", "2026-11-05")]),
    ("soonish", "unknown", []), ("majd valamikor", "unknown", []),
]


def spans(r):
    return [(c["start"], c["end"]) for c in r["candidates"]]


class Dates(unittest.TestCase):
    def test_seen_phrases(self):
        for phrase, status, want in SEEN:
            r = resolve(phrase, "Europe/Budapest", TODAY)
            self.assertEqual((r["status"], spans(r)), (status, want), phrase)

    def test_never_a_fourteen_day_next_week(self):
        for phrase in ("next week", "jövő héten", "Next Week"):
            for start, end in spans(resolve(phrase, "UTC", TODAY)):
                days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days + 1
                self.assertEqual(days, 7, phrase)

    def test_the_answer_says_ask_with_timezone_and_bounds(self):
        r = resolve("jövő héten", "Europe/Budapest", TODAY, lang="hu")
        self.assertIn("kérdezd meg", r["say"])
        self.assertIn("Europe/Budapest", r["say"])
        self.assertIn("mindkét nap benne van", r["say"])
        self.assertIn("both ends included", r["boundary"])

    def test_week_start_is_a_choice(self):
        r = resolve("this week", "America/New_York", TODAY, week_start="sun")
        self.assertEqual(spans(r)[0], ("2026-10-18", "2026-10-24"))

    def test_cli_exit_codes(self):
        tool = [sys.executable, str(HERE / "mentat_dates.py"), "--tz", "UTC", "--today", "2026-10-21"]
        codes = [subprocess.run(tool + [p], capture_output=True).returncode for p in ("holnap", "next week", "soonish")]
        self.assertEqual(codes, [0, 3, 1])


class Wiring(unittest.TestCase):
    def test_installed_listed_and_named_where_dates_are_read_back(self):
        import json
        import re
        from test_contract_rule import intake
        from test_init_doc import DOCS, imports
        need = {n + ".py" for n in imports("mentat_dates")}
        for lang, doc in DOCS.items():
            line = next(ln for ln in doc.read_text(encoding="utf-8").splitlines() if '-o ".mentat/bin/#1"' in ln)
            got = set(re.search(r"/manifest/\{([^}]*)\}", line).group(1).split(","))
            self.assertTrue(need <= got, (lang, need - got))
            self.assertIn("mentat_dates.py", intake(lang))
        ids = [e["id"] for e in json.loads((HERE / "capabilities" / "contract.json").read_text())]
        self.assertIn("dates", ids)


if __name__ == "__main__":
    unittest.main()
