"""Notes in one call: new / due / find on a scaffolded brain."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"
TODAY = datetime.date.today()
ISO = lambda n: (TODAY + datetime.timedelta(days=n)).isoformat()  # noqa: E731


class Brain(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                        "--repo", str(self.root), "--base", "https://x/"], capture_output=True)

    def run_tool(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True, input=stdin)

    def test_new_case_is_filled_indexed_and_prints_only_the_path(self):
        r = self.run_tool("new", "case", "Gázszámla", "--due", ISO(3), "--tags", "haztartas")
        self.assertEqual(r.stdout.strip(), "agy/cases/gazszamla.md")
        text = (self.root / r.stdout.strip()).read_text()
        self.assertRegex(text, r"case_id: [0-9A-HJKMNP-TV-Z]{26}\n")
        self.assertIn("due_at: %s" % ISO(3), text)
        self.assertIn("tags: [haztartas]", text)
        meta = (self.root / "agy/cases/_meta.md").read_text()
        self.assertIn("- [Gázszámla](gazszamla.md) - case, %s" % ISO(3), meta)

    def test_every_type_lands_in_its_folder_with_frontmatter(self):
        want = {"todo": "agy/todos/x.md", "person": "agy/people/x.md",
                "connector": "agy/connectors/x.md", "case": "agy/cases/x.md",
                "decision": "agy/decisions/%s-x.md" % TODAY,
                "brain-dump": "agy/brain-dumps/%s-x.md" % TODAY}
        for kind, path in want.items():
            r = self.run_tool("new", kind, "x")
            self.assertEqual(r.stdout.strip(), path, kind)
            self.assertIn("type: %s\n" % kind, (self.root / path).read_text())

    def test_never_overwrites_and_body_from_stdin(self):
        self.run_tool("new", "brain-dump", "dump", "--body", "-", stdin="nyers szöveg")
        p = self.root / ("agy/brain-dumps/%s-dump.md" % TODAY)
        self.assertIn("nyers szöveg", p.read_text())
        before = p.read_text()
        r = self.run_tool("new", "brain-dump", "dump")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(p.read_text(), before)

    def test_admin_backed_cases_are_refused(self):
        (self.root / "mentat.json").write_text(json.dumps({"cases": {"backend": "admin"}}))
        r = self.run_tool("new", "case", "x")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.root / "agy/cases/x.md").exists())

    def test_due_lists_overdue_and_soon_not_far_or_closed(self):
        for t, d in (("Lejárt", ISO(-2)), ("Hamarosan", ISO(5)), ("Messze", ISO(40))):
            self.run_tool("new", "todo", t, "--due", d)
        self.run_tool("new", "todo", "Kész", "--due", ISO(1))
        p = self.root / "agy/todos/kesz.md"
        p.write_text(p.read_text().replace("status: open", "status: done"))
        out = self.run_tool("due").stdout
        self.assertRegex(out, r"LEJART .*Lejárt")
        self.assertIn("Hamarosan", out)
        self.assertNotIn("Messze", out)
        self.assertNotIn("Kész", out)
        self.assertLess(out.index("Lejárt"), out.index("Hamarosan"))

    def test_due_shows_time_people_and_source(self):
        """`due` answers "what is on today?" with the time, who is involved and where it came from."""
        self.run_tool("new", "person", "Kiss Anna")
        self.run_tool("new", "todo", "Megbeszélés", "--due", ISO(0),
                      "--body", "Egyeztetés: [Kiss Anna](../people/kiss-anna.md)")
        p = self.root / "agy/todos/megbeszeles.md"
        p.write_text(p.read_text().replace("due: %s" % ISO(0), "due: %s 09:30" % ISO(0)))
        out = self.run_tool("due").stdout
        line = next(ln for ln in out.splitlines() if "Megbeszélés" in ln)
        self.assertIn("09:30", line)
        self.assertIn("Kiss Anna", line)
        self.assertIn("agy/todos/megbeszeles.md", line)

    def test_find_matches_accent_insensitively_and_ranks_title_first(self):
        self.run_tool("new", "todo", "Átutalás", "--body", "gáz")
        self.run_tool("new", "todo", "Más", "--body", "kell átutalás is")
        out = self.run_tool("find", "atutalas").stdout.splitlines()
        self.assertTrue(out[0].startswith("agy/todos/atutalas.md"), out)
        self.assertTrue(re.match(r"2 hit", out[-1]))
        self.assertEqual(self.run_tool("find", "nincsilyen").returncode, 1)


class LocalDay(unittest.TestCase):
    """'Today' is the agent's day (components.engine.timezone), not the box's UTC day."""
    LATE = datetime.datetime(2026, 10, 18, 22, 30, tzinfo=datetime.timezone.utc)   # Budapest: 10-19 00:30

    def test_budapest_day_after_a_utc_evening(self):
        sys.path.insert(0, str(HERE))
        import mentat_brain_types as bt
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "mentat.json").write_text(json.dumps({"components": {"engine": {"timezone": "Europe/Budapest"}}}))
        os.environ.pop("ANYTIME_TZ", None)
        self.assertEqual(bt.local_today(root, self.LATE).isoformat(), "2026-10-19")
        (root / "mentat.json").write_text(json.dumps({"components": {"engine": {"timezone": "UTC"}}}))
        self.assertEqual(bt.local_today(root, self.LATE).isoformat(), "2026-10-18")
        with self.assertRaises(SystemExit):
            os.environ["ANYTIME_TZ"] = "Mars/Olympus"
            try:
                bt.local_today(root, self.LATE)
            finally:
                os.environ.pop("ANYTIME_TZ", None)

    def test_the_tool_names_a_dated_note_by_the_agent_zone(self):
        def dump(tz):
            root = pathlib.Path(tempfile.mkdtemp())
            subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                            "--repo", str(root), "--base", "https://x/"], capture_output=True)
            env = dict(os.environ, ANYTIME_TZ=tz)
            r = subprocess.run([sys.executable, str(TOOL), "--repo", str(root), "new", "brain-dump", "d"],
                               capture_output=True, text=True, env=env)
            return r.stdout.strip()
        # UTC+14 and UTC-12 never share a date
        self.assertGreater(dump("Pacific/Kiritimati"), dump("Etc/GMT+12"))


if __name__ == "__main__":
    unittest.main()
