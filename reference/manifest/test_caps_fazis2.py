"""Képességfa, phase 2: an expensive check runs only on `where --probe` and is remembered with a
TTL; the day's first look says what changed since the last one; a project without a README is
still described by what it has (the projects/ index line, package.json, pyproject, wrangler)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import time
import unittest

from _caps_base import CapsBase

TOKEN_TOOL = ".mentat/bin/web/mentat_cf_token.py"


class Checks(CapsBase):
    def tool(self, code, line):
        self.write(TOKEN_TOOL, "import sys\nprint(%r)\nsys.exit(%d)\n" % (line, code))

    def test_find_never_runs_a_check_and_probe_remembers_it(self):
        self.write(".env", "CLOUDFLARE_API_TOKEN=x\n")
        self.tool(1, "token invalid")
        c = self.by_id("cloudflare token", "cf.token")
        self.assertEqual((c["availability"], c["verified"]), ("on", None))  # not run by find
        r = self.run_where("--probe", "cf.token")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("token invalid", r.stdout)
        c = self.by_id("cloudflare token", "cf.token")
        self.assertEqual(c["availability"], "degraded")
        self.assertFalse(c["verified"]["ok"])
        self.tool(0, "ready")
        self.assertEqual(self.run_where("--probe", "cf.token").returncode, 0)
        c = self.by_id("cloudflare token", "cf.token")
        self.assertEqual((c["availability"], c["verified"]["ok"], c["verified"]["stale"]), ("on", True, False))

    def test_an_old_check_is_stale_and_no_longer_decides(self):
        self.write(".env", "CLOUDFLARE_API_TOKEN=x\n")
        self.tool(1, "token invalid")
        self.run_where("--probe", "cf.token")
        p = self.root / ".mentat" / "state" / "capability-checks.json"
        doc = json.loads(p.read_text())
        doc["cf.token"]["at"] = time.time() - 3 * 24 * 3600
        p.write_text(json.dumps(doc))
        c = self.by_id("cloudflare token", "cf.token")
        self.assertEqual((c["availability"], c["verified"]["stale"]), ("on", True))

    def test_probe_refuses_what_has_no_check(self):
        r = self.run_where("--probe", "brain.find")
        self.assertEqual(r.returncode, 2)


class DailyChanges(CapsBase):
    def test_the_first_look_of_the_day_says_what_changed(self):
        self.assertNotIn("Változás", self.run_where("--find", "tedd ki a netre").stdout)  # first snapshot
        self.write("projects/lista/README.md", "# Lista\n")
        self.assertNotIn("Változás", self.run_where("--find", "tedd ki a netre").stdout)  # same day
        p = self.root / ".mentat" / "state" / "capability-index.json"
        doc = json.loads(p.read_text())
        doc["at"] = time.time() - 25 * 3600
        p.write_text(json.dumps(doc))
        out = self.run_where("--find", "tedd ki a netre").stdout
        self.assertIn("Változás", out)
        self.assertIn("+ own.project.lista", out)
        self.assertNotIn("Változás", self.run_where("--map").stdout)  # once


class ProjectsWithoutReadme(CapsBase):
    def test_package_json_and_the_index_line_describe_it(self):
        self.write("projects/dashboard/package.json", json.dumps({"name": "dashboard",
                   "description": "Műszerfal a projektek állapotáról"}))
        self.write("projects/tarsas/src/main.py", "")
        self.write("projects/_meta.md", "# Projektek\n- [tarsas](tarsas/) — családi társasjáték szabálykönyve\n")
        self.assertEqual(self.top("kell egy műszerfal a projektjeim állapotáról"), "own.project.dashboard")
        self.assertEqual(self.top("a társasjáték szabályai"), "own.project.tarsas")

    def test_pyproject_and_wrangler_too(self):
        self.write("projects/szamla/pyproject.toml", '[project]\nname = "szamla"\ndescription = "Számlák beolvasása PDF-ből"\n')
        self.write("projects/jelentkezes/wrangler.toml", 'name = "jelentkezesi-urlap"\nmain = "src/index.ts"\n')
        self.assertEqual(self.top("olvasd be a számlákat a pdf-ekből"), "own.project.szamla")
        self.assertIn("own.project.jelentkezes",
                      [c["id"] for c in self.find("jelentkezési űrlap")["candidates"]])


if __name__ == "__main__":
    unittest.main()
