"""`fleet hold-outward` / `release-outward`: a kifelé-tartás jelzője az ágens repójában.

H5 (2026-10): a fejlesztő a fogadó élő tickjét futtatta --dry-run nélkül, és a fogadó
valódi emlékeztetőt küldött a csapat-csoportba építés közben. A jelzőt a motor olvassa
(anytime_engine/hold.py); ezek a tesztek a TERMELŐ kódot hívják (helyben és hamis ssh-n át).
"""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fleet import cli, outward_hold as oh, outward_hold_box as box
from fleet.remote import Target
from fleet import doctor
from test_truthful_health import _entry, _m

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class TestUntil(unittest.TestCase):
    def test_relative_and_iso(self):
        self.assertEqual(oh.parse_until("+4h", NOW), NOW + timedelta(hours=4))
        self.assertEqual(oh.parse_until("+30m", NOW), NOW + timedelta(minutes=30))
        self.assertEqual(oh.parse_until("2026-10-29T18:00:00+00:00", NOW), NOW + timedelta(hours=6))

    def test_past_longer_than_24h_and_garbage_are_refused(self):
        for bad in ("+25h", "+2d", "2026-10-29T11:00:00+00:00", "holnap"):
            with self.assertRaises(ValueError, msg=bad):
                oh.parse_until(bad, NOW)


class _Repo(unittest.TestCase):
    def setUp(self):
        self.home = Path(os.environ["HOME"])
        self.wd = Path(tempfile.mkdtemp(dir=self.home, prefix="vilma-"))
        self.workdir = "%h/" + self.wd.name          # a registry alakja: %h = a box HOME-ja
        self.marker = self.wd / "data" / "state" / "kifele-tartas.json"
        self.resolver = lambda name, ssh=None: ({"agent": name, "workdir": self.workdir},  # noqa: E731
                                                Target(None, "helyben"))

    def engine(self):
        (self.wd / "anytime_engine").mkdir()
        (self.wd / "anytime_engine" / "__init__.py").write_text("")
        (self.wd / "anytime_engine" / "hold.py").write_text("")


class TestHoldRelease(_Repo):
    def test_hold_writes_the_marker_the_engine_reads(self):
        self.engine()
        r = oh.hold("vilma", "+4h", "Vilma építése", resolver=self.resolver)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["engine_knows"])
        doc = json.loads(self.marker.read_text())
        self.assertEqual(doc["reason"], "Vilma építése")
        self.assertIn("fleet hold-outward", doc["set_by"])
        until = datetime.fromisoformat(doc["until"])
        self.assertLess(abs((until - datetime.now(timezone.utc)) - timedelta(hours=4)), timedelta(minutes=1))
        self.assertTrue(r["hold"]["active"])
        self.assertIn("TARTÁS AKTÍV — dry-run, eddig:", oh.line(r["hold"]))

    def test_engine_without_hold_support_is_said_loudly(self):
        r = oh.hold("vilma", "+1h", "x", resolver=self.resolver)
        self.assertTrue(r["ok"])
        self.assertFalse(r["engine_knows"])

    def test_release_removes_it(self):
        oh.hold("vilma", "+1h", "x", resolver=self.resolver)
        r = oh.release("vilma", resolver=self.resolver)
        self.assertEqual((r["ok"], r["removed"], self.marker.exists()), (True, True, False))
        self.assertEqual(oh.line(oh.show(Target(None, "h"), self.workdir)), "kifelé:   nincs tartás")

    def test_missing_repo_writes_nothing(self):
        self.workdir = "%h/nincs-ilyen"
        r = oh.hold("vilma", "+1h", "x", resolver=self.resolver)
        self.assertFalse(r["ok"])
        self.assertFalse((self.home / "nincs-ilyen").exists())

    def test_over_fake_ssh(self):
        fake, log = self.wd.parent / "fake-ssh", self.wd.parent / "ssh-calls"
        fake.write_text('#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done; shift\n'
                        f'echo "$1" >> {log}; shift\nexec sh -c "$1"\n')
        fake.chmod(0o755)
        os.environ["FLEET_SSH"] = str(fake)
        try:
            self.resolver = lambda name, ssh=None: ({"agent": name, "workdir": self.workdir},  # noqa: E731
                                                    Target("agent@box", "box"))
            r = oh.hold("vilma", "+2h", "távoli", resolver=self.resolver)
        finally:
            os.environ.pop("FLEET_SSH")
        self.assertTrue(r["ok"], r)
        self.assertEqual(log.read_text().strip(), "agent@box")
        self.assertEqual(json.loads(self.marker.read_text())["reason"], "távoli")


class TestReadRules(_Repo):
    def put(self, doc, age_h=0.0):
        self.marker.parent.mkdir(parents=True)
        self.marker.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        if age_h:
            t = time.time() - age_h * 3600
            os.utime(self.marker, (t, t))

    def test_expired_is_present_but_not_active(self):
        self.put({"until": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()})
        h = box.read(self.wd)
        self.assertEqual((h["present"], h["active"]), (True, False))
        self.assertIn("lejárt jelző", oh.line(h))

    def test_24h_cap_from_writing(self):
        self.put({"until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}, age_h=25)
        self.assertFalse(box.read(self.wd)["active"])

    def test_unreadable_holds_like_the_engine(self):
        self.put("{nem json")
        h = box.read(self.wd)
        self.assertTrue(h["active"] and h["broken"])


class TestShownInDoctorAndCli(_Repo):
    def test_doctor_names_the_hold_and_it_is_not_a_fault(self):
        hold = {"present": True, "active": True, "until": "2026-10-29T18:00:00+01:00", "reason": "építés"}
        r = doctor.assess(_entry(), _m(), {"quarantined": False}, unit_active="active",
                          unit_enabled="enabled", drop_in=True, bridge_installed=None,
                          bridge_current="x", locked=False, outward=hold)
        self.assertTrue(any("TARTÁS AKTÍV" in f for f in r["facts"]), r["facts"])
        self.assertTrue(r["ok"])

    def test_cli_parses_both_commands(self):
        p = cli.build_parser()
        a = p.parse_args(["hold-outward", "vilma", "--until", "+4h", "--reason", "építés"])
        self.assertEqual((a.fn.__name__, a.until, a.reason), ("cmd_hold", "+4h", "építés"))
        self.assertEqual(p.parse_args(["release-outward", "vilma"]).fn.__name__, "cmd_release")


if __name__ == "__main__":
    unittest.main()
