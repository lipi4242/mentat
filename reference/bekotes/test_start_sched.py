"""A new session starts with the last scheduled run's state when it went wrong (failure class: the
agent's own scheduled output not checked at the start of a new session)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import time
import unittest

from test_guard_kint import KintBase


class StartSched(KintBase):
    roles = False

    def start(self):
        r = self.run_guard({"session_id": "s9", "cwd": str(self.root)}, None, args=["--session-start"])
        return (json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else "")

    def engine(self, tick_age_h=None, actions=0):
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"] = {"path": "anytime_engine"}
        (self.root / "mentat.json").write_text(json.dumps(doc))
        if tick_age_h is not None:
            st = self.root / "data" / "state"
            st.mkdir(parents=True, exist_ok=True)
            (st / "last-tick.json").write_text(json.dumps({"actions": actions}))
            old = time.time() - tick_age_h * 3600
            os.utime(st / "last-tick.json", (old, old))

    def test_a_stale_or_missing_run_is_put_in_front_of_the_agent(self):
        self.assertNotIn("ütemezett", self.start(), "no engine: nothing to say")
        self.engine()
        self.assertIn("has not run here", self.start())
        self.engine(tick_age_h=50)
        self.assertIn("not running now", self.start())

    def test_a_good_run_adds_nothing(self):
        self.engine(tick_age_h=1)
        self.assertNotIn("ütemezett", self.start())


    def test_a_run_that_missed_its_stored_promise_is_said_first(self):
        self.engine(tick_age_h=1, actions=1)
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"]["delivery"] = {"channel": "file", "expect": ["Hívd fel:"]}
        (self.root / "mentat.json").write_text(json.dumps(doc))
        out = self.root / "data" / "outbox" / "x.md"
        out.parent.mkdir(parents=True)
        out.write_text("Ma: semmi\n")
        self.assertIn("lacks what the job promised", self.start())


if __name__ == "__main__":
    unittest.main()
