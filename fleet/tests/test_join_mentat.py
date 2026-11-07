"""join × mentat.json (LG1 spec 3. pont + 5. szabály) és a tranzakciós
upgrade: hamis systemctl a PATH elején, ideiglenes repó."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401  (repo konvenció: unittest és pytest alatt is fut)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fleet import join, status, __version__  # noqa: E402
from fleet.txn import StepFailed  # noqa: E402
from fakebin import FakeBin  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.fb = FakeBin()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "agent"
        self.ud = Path(self.tmp.name) / "units"
        self.ud.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".gitignore").write_text(".mentat/\n")
        self.mentat = {"schema": 1, "agent": {"name": "probe", "language": "hu"},
                       "components": {"brain": {"root": "agy"},
                                      "engine": {"path": "anytime_engine", "plugins": ["agent.concerns"],
                                                 "schedule_owner": "engine", "x_jovo": 1}}}
        (self.repo / "mentat.json").write_text(json.dumps(self.mentat))
        (self.repo / "AGENTS.md").write_text("# agy\n")
        (self.repo / "CLAUDE.md").write_text("@AGENTS.md\n")

    def tearDown(self):
        self.fb.cleanup(); self.tmp.cleanup()

    def engine_timer(self):
        root = str(self.repo.resolve())
        (self.ud / "anytime-probe-hourly.service").write_text(
            f"[Service]\nType=oneshot\nWorkingDirectory={root}\n"
            f'Environment="ANYTIME_PLUGINS=agent.concerns"\n'
            f'ExecStart=/opt/venv/bin/python -m anytime_engine.tick "hourly" "--exec" "run-agent"\n')
        (self.ud / "anytime-probe-hourly.timer").write_text("[Timer]\nOnCalendar=*:07\nPersistent=true\n")
        self.fb.set_active("anytime-probe-hourly.timer")

    def join(self, **kw):
        return join.join(self.repo, agent="probe", unit_dir=self.ud, host="box1", **kw)

    def doc(self):
        return json.loads((self.repo / "mentat.json").read_text())

    def local(self):
        return json.loads((self.repo / ".mentat" / "local.json").read_text())


class TestJoinWritesOwnKeys(Base):
    def test_fleet_sections_written_others_preserved(self):
        self.join()
        d = self.doc()
        self.assertEqual(d["components"]["fleet"], {})
        self.assertEqual(d["components"]["brain"], {"root": "agy"})
        self.assertEqual(d["components"]["engine"]["x_jovo"], 1)     # ismeretlen mező marad
        self.assertEqual(d["agent"], self.mentat["agent"])
        loc = self.local()
        self.assertEqual(loc["fleet"], {"agent_id": "probe", "host": "box1"})
        self.assertEqual(loc["installed"]["fleet"], __version__)

    def test_no_mentat_json_means_standalone_join(self):
        (self.repo / "mentat.json").unlink()
        r = self.join()
        self.assertIn("önállóan", r["notes"][0])
        self.assertFalse((self.repo / ".mentat").exists())

    def test_newer_schema_is_diagnostics_only(self):
        (self.repo / "mentat.json").write_text(json.dumps(dict(self.mentat, schema=2)))
        r = self.join()
        self.assertIn("csak diagnosztika", r["notes"][0])
        self.assertEqual(self.doc()["schema"], 2)
        self.assertNotIn("fleet", self.doc()["components"])
        self.assertEqual(self.fb.calls(), [])


class TestBrainSynergy(Base):
    def test_missing_include_warns_and_fix_adds_it(self):
        (self.repo / "CLAUDE.md").write_text("# csak persona\n")
        r = self.join()
        self.assertTrue(any("nem tölti be az AGENTS.md" in n for n in r["notes"]), r["notes"])
        self.assertNotIn("@AGENTS.md", (self.repo / "CLAUDE.md").read_text())
        self.join(fix_claude_md=True)
        text = (self.repo / "CLAUDE.md").read_text()
        self.assertTrue(text.startswith("@AGENTS.md\n"))
        self.assertIn("# csak persona", text)


class TestScheduleTakeover(Base):
    def test_takes_over_engine_timer_idempotently(self):
        self.engine_timer()
        self.join()
        svc = (self.ud / "fleet-tick-probe.service").read_text()
        self.assertIn('ExecStart=/opt/venv/bin/python -m anytime_engine.tick "hourly" "--exec" "run-agent"', svc)
        self.assertIn("OnCalendar=*:07", (self.ud / "fleet-tick-probe.timer").read_text())
        self.assertFalse((self.ud / "anytime-probe-hourly.timer").exists())
        calls = self.fb.calls()
        self.assertIn("systemctl --user enable --now fleet-tick-probe.timer", calls)
        self.assertIn("systemctl --user disable --now anytime-probe-hourly.timer", calls)
        self.assertEqual(self.doc()["components"]["engine"]["schedule_owner"], "fleet")
        # másodszor: nincs új írás, az átvett ExecStart megmarad
        self.join()
        self.assertEqual((self.ud / "fleet-tick-probe.service").read_text(), svc)
        self.assertEqual(self.doc()["components"]["engine"]["schedule_owner"], "fleet")

    def test_without_engine_timer_builds_tick_from_mentat_json(self):
        self.join()
        svc = (self.ud / "fleet-tick-probe.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 -m anytime_engine.tick hourly", svc)
        self.assertIn("ANYTIME_PLUGINS=agent.concerns", svc)

    def test_failed_takeover_rolls_everything_back(self):
        self.engine_timer()
        self.fb.fail_on("disable --now anytime-probe-hourly.timer")
        with self.assertRaises(StepFailed):
            self.join()
        self.assertTrue((self.ud / "anytime-probe-hourly.timer").exists())
        self.assertFalse((self.ud / "fleet-tick-probe.timer").exists())
        self.assertEqual(self.doc(), self.mentat)
        self.assertFalse((self.repo / ".claude" / "fleet.json").exists())
        self.assertIn("systemctl --user disable --now fleet-tick-probe.timer", self.fb.calls())


class TestUpgradeIsTruthful(Base):
    def test_rules_left_as_new_does_not_bump_the_version(self):
        join.join(self.repo, agent="probe", unit_dir=self.ud, host="box1")
        mp = self.repo / ".claude" / "fleet.json"
        m = json.loads(mp.read_text()); m["components"]["fleet"] = "1.0.0"; mp.write_text(json.dumps(m))
        loc = self.local(); loc["installed"]["fleet"] = "1.0.0"
        (self.repo / ".mentat" / "local.json").write_text(json.dumps(loc))
        rules = self.repo / ".claude" / "rules" / "fleet.md"
        rules.write_text(rules.read_text() + "\n- saját\n")
        r = join.upgrade(self.repo)
        self.assertFalse(r["ok"])
        self.assertEqual(json.loads(mp.read_text())["components"]["fleet"], "1.0.0")
        self.assertEqual(self.local()["installed"]["fleet"], "1.0.0")


class TestStatus(Base):
    def test_status_names_elements_and_synergies(self):
        self.engine_timer()
        self.join()
        r = status.status("probe", repo=self.repo, unit_dir=self.ud)
        self.assertEqual(r["elements"]["fleet"], f"jelen, telepítve: {__version__}")
        self.assertEqual(r["elements"]["admin"], "nincs jelen")
        self.assertIn("ütemezés: flotta (fleet-tick-probe.timer: active)", r["synergies"]["motor+flotta"])
        self.assertEqual(r["synergies"]["flotta+admin"], "admin: nincs bekötve")
        self.assertIn("betölti", r["synergies"]["agy+flotta"])


if __name__ == "__main__":
    unittest.main()
