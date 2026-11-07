"""mentat_brain.py: compact due, mv, commit, where, find's due marker."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_brain.py"
TODAY = datetime.date.today()
ISO = lambda n: (TODAY + datetime.timedelta(days=n)).isoformat()  # noqa: E731


class Base(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", "hu",
                        "--repo", str(self.root), "--base", "https://x/"], capture_output=True)

    def run_tool(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.root), *args],
                              capture_output=True, text=True, input=stdin)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@x",
                               *args], capture_output=True, text=True)


class Due(Base):
    def test_default_is_at_most_eight_lines_and_full_shows_all(self):
        for i in range(12):
            self.run_tool("new", "todo", "Teendo %02d" % i, "--due", ISO(1 + i % 5))
        short = self.run_tool("due").stdout.splitlines()
        self.assertLessEqual(len(short), 8)
        self.assertIn("--full", short[-1])
        self.assertIn("+5", short[-1])
        self.assertEqual(len(self.run_tool("due", "--full").stdout.splitlines()), 12)

    def test_few_items_have_no_trailer(self):
        self.run_tool("new", "todo", "Egy", "--due", ISO(1))
        self.assertNotIn("--full", self.run_tool("due").stdout)

    def test_find_marks_an_upcoming_deadline(self):
        self.run_tool("new", "todo", "Kostolo", "--due", ISO(3))
        self.assertIn("[due %s]" % ISO(3), self.run_tool("find", "kostolo").stdout)


class BrainDump(Base):
    def test_no_empty_open_questions_header(self):
        r = self.run_tool("new", "brain-dump", "d", "--body", "-", stdin="nyers")
        self.assertNotIn("Nyitott kérdések", (self.root / r.stdout.strip()).read_text())


class Mv(Base):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.old = self.run_tool("new", "case", "Tábor a lányoknak", "--tags", "csalad").stdout.strip()
        self.run_tool("new", "todo", "Befizetés", "--body", "Lásd: [ügy](../cases/tabor-a-lanyoknak.md)")
        self.git("add", "-A"); self.git("commit", "-qm", "x")

    def test_mv_with_title_renames_rewrites_links_and_index(self):
        r = self.run_tool("mv", self.old, "--title", "Tábor Marcinak és Lilinek")
        self.assertEqual(r.returncode, 0, r.stderr)
        new = self.root / "agy/cases/tabor-marcinak-es-lilinek.md"
        self.assertTrue(new.exists())
        self.assertFalse((self.root / self.old).exists())
        self.assertIn("title: Tábor Marcinak és Lilinek", new.read_text())
        self.assertIn("tabor-marcinak-es-lilinek.md", (self.root / "agy/todos/befizetes.md").read_text())
        meta = (self.root / "agy/cases/_meta.md").read_text()
        self.assertIn("[Tábor Marcinak és Lilinek](tabor-marcinak-es-lilinek.md)", meta)
        self.assertNotIn("lanyoknak", meta)
        self.assertIn("R", self.git("status", "--short").stdout)  # git mv, not delete+add
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)

    def test_mv_by_plain_new_name_and_refuses_overwrite(self):
        self.assertEqual(self.run_tool("mv", "tabor-a-lanyoknak.md", "tabor.md").returncode, 0)
        self.assertTrue((self.root / "agy/cases/tabor.md").exists())
        self.run_tool("new", "case", "Masik")
        r = self.run_tool("mv", "tabor.md", "masik.md")
        self.assertEqual(r.returncode, 1)
        self.assertTrue((self.root / "agy/cases/tabor.md").exists())

    def test_dry_run_changes_nothing(self):
        self.run_tool("mv", self.old, "x.md", "--dry-run")
        self.assertTrue((self.root / self.old).exists())


class Commit(Base):
    def test_commits_the_brain_and_refuses_env(self):
        self.git("init", "-q")
        # A real install sets this repo's identity (mentat_init); a bare Linux box has none.
        self.git("config", "user.name", "t"); self.git("config", "user.email", "t@x")
        self.run_tool("new", "todo", "Egy")
        r = self.run_tool("commit", "agy: egy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(), "agy: egy")
        self.assertIn("nothing", self.run_tool("commit", "agy: semmi").stdout)
        (self.root / ".gitignore").write_text("")
        (self.root / "agy" / ".env").write_text("K=v")
        r = self.run_tool("commit", "agy: env")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.git("log", "-1", "--format=%s").stdout.strip(), "agy: egy")


class Where(Base):
    def test_where_reads_the_manifest_and_says_none_for_the_rest(self):
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "agent": {"name": "t"},
            "components": {"brain": {"root": "agy"}, "engine": {"path": "anytime_engine"}}}))
        (self.root / "data/state").mkdir(parents=True)
        (self.root / "data/state/last-tick.json").write_text("{}")
        out = self.run_tool("where").stdout
        self.assertLessEqual(len(out.splitlines()), 8)
        self.assertRegex(out, r"(?m)^agy: agy/")
        self.assertRegex(out, r"(?m)^motor: .*anytime_engine.*last-tick")
        self.assertRegex(out, r"(?m)^flotta: NINCS")
        self.assertRegex(out, r"(?m)^admin: NINCS")
        (self.root / ".mentat").mkdir()
        (self.root / ".mentat/local.json").write_text(json.dumps({"schema": 1,
            "fleet": {"agent_id": "t-1", "host": "box"}, "admin": {"url": "http://localhost:8787"}}))
        out = self.run_tool("where").stdout
        self.assertIn("fleet doctor t-1", out)
        self.assertIn("http://localhost:8787", out)


if __name__ == "__main__":
    unittest.main()
