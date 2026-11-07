"""status shows whether the role guard is installed when roles are declared."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

CLI = pathlib.Path(__file__).resolve().parent / "mentat_cli.py"


def run(root, *args):
    env = {k: v for k, v in os.environ.items() if k != "MENTAT_ROLE"}
    return subprocess.run([sys.executable, str(CLI), *args, "--repo", str(root)],
                          capture_output=True, text=True, env=env)


class GuardStatus(unittest.TestCase):
    def make(self, lang):
        root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        run(root, "init-brain", "--name", "Bob", "--language", lang, "--brain-root", "agy",
            "--version", "0.2.0")
        return root

    def test_missing_then_installed_hu(self):
        root = self.make("hu")
        self.assertNotIn("szerep-őr", run(root, "status").stdout)  # no roles: no line
        run(root, "roles", "--default", "asszisztens", "--install", "fejleszto")
        self.assertIn("szerep-őr: NINCS TELEPÍTVE", run(root, "status").stdout)
        guard = root / ".mentat/bin/bekotes/szerep_guard.py"
        guard.parent.mkdir(parents=True)
        guard.write_text("# guard\n")
        out = run(root, "status").stdout
        self.assertIn("szerep-őr: telepítve (asszisztens)", out)
        self.assertNotIn("NINCS", out)

    def test_missing_en(self):
        root = self.make("en")
        run(root, "roles", "--default", "fejleszto")
        self.assertIn("role guard: NOT INSTALLED", run(root, "status").stdout)


if __name__ == "__main__":
    unittest.main()
