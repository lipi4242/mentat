"""After an install that did not complete, the files say which Mentat parts are missing.

Failure class: a core part was missing (the install stopped) and the agent built its own
scheduled script + timer instead, without asking. `mentat_init.py --parts` (and every HIBA)
names each missing part, how to install it, and the rule: a hand-built replacement only on the
USER's yes to that replacement.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_init_parts as mp  # noqa: E402


def init_parts(root, lang="en"):
    return subprocess.run([sys.executable, "-I", str(HERE / "mentat_init.py"), "--parts", "--repo", str(root),
                           "--lang", lang], capture_output=True, text=True, timeout=60)


class Parts(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())

    def brain(self):
        (self.root / "AGENTS.md").write_text("<!-- mentat:managed:start reference-manual -->\nx\n")
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text('{"hooks": "python3 .mentat/bin/bekotes/szerep_guard.py"}')
        (self.root / ".mentat" / "bin" / "bekotes").mkdir(parents=True)
        (self.root / ".mentat" / "bin" / "bekotes" / "szerep_guard.py").write_text("")
        comp = {"brain": {"root": "brain"}}
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": comp}))

    def test_an_empty_folder_misses_every_part_and_gets_the_rule(self):
        r = init_parts(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PARTS brain MISSING · guard MISSING · engine MISSING", r.stdout)
        self.assertIn("MISSING brain — to install it: INSTALL.md step 2", r.stdout)
        self.assertIn("RULE", r.stdout)
        self.assertIn("is not that yes", r.stdout)
        self.assertIn("jónak látod", init_parts(self.root, "hu").stdout)

    def test_a_brain_without_the_engine_names_the_engine_command(self):
        self.brain()
        out = "\n".join(mp.lines(self.root))
        self.assertIn("brain ok · guard ok · engine MISSING", out)
        self.assertIn("--engine --tz", out)

    def test_everything_present_has_no_rule(self):
        self.brain()
        (self.root / "anytime_engine").mkdir()
        (self.root / "anytime_engine" / "tick.py").write_text("")
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"] = {"path": "anytime_engine"}
        (self.root / "mentat.json").write_text(json.dumps(doc))
        self.assertEqual(mp.lines(self.root), ["PARTS brain ok · guard ok · engine ok"])

    def test_a_declared_engine_whose_files_are_gone_is_missing(self):
        self.brain()
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"] = {"path": "anytime_engine"}
        (self.root / "mentat.json").write_text(json.dumps(doc))
        self.assertIn("files are gone", "\n".join(mp.lines(self.root)))


if __name__ == "__main__":
    unittest.main()
