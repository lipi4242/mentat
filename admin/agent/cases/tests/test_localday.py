"""'today' is the agent's day (components.engine.timezone), not the box's UTC day."""
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import CLI, Repo

# 2026-10-18 22:30 UTC is 2026-10-19 00:30 in Budapest (CEST, UTC+2).
LATE = datetime(2026, 10, 18, 22, 30, tzinfo=timezone.utc)


class TestLocalDay(Repo):
    def set_tz(self, name):
        m = self.manifest()
        m["components"]["engine"] = {"timezone": name}
        (self.root / "mentat.json").write_text(__import__("json").dumps(m))

    def test_budapest_day_after_utc_evening(self):
        sys.path.insert(0, str(CLI))
        import localday
        self.set_tz("Europe/Budapest")
        os.environ.pop("ANYTIME_TZ", None)
        self.assertEqual(localday.today(self.root, LATE), "2026-10-19")
        self.set_tz("UTC")
        self.assertEqual(localday.today(self.root, LATE), "2026-10-18")

    def test_env_wins_and_bad_zone_stops(self):
        sys.path.insert(0, str(CLI))
        import localday
        from common import CasesError
        self.set_tz("UTC")
        os.environ["ANYTIME_TZ"] = "Europe/Budapest"
        try:
            self.assertEqual(localday.today(self.root, LATE), "2026-10-19")
            os.environ["ANYTIME_TZ"] = "Mars/Olympus"
            with self.assertRaises(CasesError):
                localday.today(self.root, LATE)
        finally:
            os.environ.pop("ANYTIME_TZ", None)

    def test_cli_default_done_at_follows_the_zone(self):
        """Through the real CLI (no --today, no CASES_TODAY): closing a case stamps the
        agent-zone day. UTC+14 and UTC-12 never share a date, so one of them is not UTC's."""
        import json

        def closed_on(tz, case_file):
            env = {k: v for k, v in os.environ.items() if k not in ("CASES_TODAY", "CASES_T")}
            env["ANYTIME_TZ"] = tz
            cid = [l.split(":", 1)[1].strip().split()[0] for l in self.text(case_file).splitlines()
                   if l.startswith("case_id:")][0]
            p = subprocess.run([sys.executable, str(CLI), "--root", str(self.root), "--json", "close", cid],
                               capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            return [o["done_at"] for o in json.loads(p.stdout)["occurrences"]][-1]

        east = closed_on("Pacific/Kiritimati", "gazszamla.md")
        west = closed_on("Etc/GMT+12", "lakber.md")
        self.assertGreater(east, west)


if __name__ == "__main__":
    unittest.main()
