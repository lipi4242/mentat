"""memoria.stage: names with personal data become unique, shell-safe placeholders."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import re
import shutil
import tempfile
import unittest

import memoria

SAFE = re.compile(r"^[A-Za-z0-9._-]+\.md$")


class Names(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src, self.stage = self.tmp / "src", self.tmp / "stage"
        self.src.mkdir()
        for n in ("a@example.com.md", "b@example.org.md", "sima.md"):
            (self.src / n).write_text("---\ndescription: d\n---\nx\n")

    def test_unique_shell_safe_placeholders(self):
        memoria.stage(self.src, self.stage)
        staged = sorted(p.name for p in (self.stage / "memoria").iterdir())
        self.assertEqual(len(staged), 3, staged)
        self.assertIn("sima.md", staged)
        for n in staged:
            self.assertRegex(n, SAFE)
            self.assertNotIn("@", n)
        log = json.loads((self.stage / memoria.LOG).read_text())
        self.assertEqual(sorted(e["file"] for e in log), staged)
        out = memoria.lista(self.stage)
        self.assertNotIn("<", out)
        self.assertNotIn("@", out)

    def test_deterministic_across_restage(self):
        memoria.stage(self.src, self.stage)
        first = sorted(p.name for p in (self.stage / "memoria").iterdir())
        memoria.stage(self.src, self.stage)
        self.assertEqual(first, sorted(p.name for p in (self.stage / "memoria").iterdir()))


if __name__ == "__main__":
    unittest.main()
