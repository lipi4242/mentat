"""A flotta tick-unitja ne írja felül a mentat.json rögzített végrehajtóját
(motor #22: `--exec` nélkül a tick a `components.engine.exec`-et
futtatja). A TERMELŐ join → tick_schedule.take_over utat hívja."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import sys
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_join_mentat import Base  # noqa: E402
from fleet.tick_schedule import strip_exec  # noqa: E402


class TestFleetTickHonoursEngineExec(Base):
    def with_exec(self):
        self.mentat["components"]["engine"]["exec"] = "python3 -m anytime_cases.deliver"
        (self.repo / "mentat.json").write_text(json.dumps(self.mentat))

    def svc(self):
        return (self.ud / "fleet-tick-probe.service").read_text()

    def test_engine_exec_in_mentat_json_drops_carried_exec_flag(self):
        self.with_exec()
        self.engine_timer()
        self.join()
        self.assertIn("ExecStart=/opt/venv/bin/python -m anytime_engine.tick hourly\n", self.svc())
        self.assertNotIn("--exec", self.svc())

    def test_without_engine_exec_the_carried_flag_stays(self):
        self.engine_timer()
        self.join()
        self.assertIn('"--exec" "run-agent"', self.svc())

    def test_already_taken_over_unit_is_cleaned_on_rejoin(self):
        self.engine_timer()
        self.join()
        self.assertIn("--exec", self.svc())
        self.with_exec()
        r = self.join()
        self.assertNotIn("--exec", self.svc())
        self.assertTrue(any("--exec kivéve" in n for n in r["notes"]), r["notes"])
        before = self.svc()
        self.join()
        self.assertEqual(self.svc(), before)          # idempotens

    def test_strip_keeps_other_args_and_systemd_escapes(self):
        line = 'ExecStart=/usr/bin/python3 -m anytime_engine.tick hourly --exec="claude -p x" --foo "a b" 100%%'
        self.assertEqual(strip_exec(line), 'ExecStart=/usr/bin/python3 -m anytime_engine.tick hourly --foo "a b" 100%%')


if __name__ == "__main__":
    unittest.main()
