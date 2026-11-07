"""mentat_web.py deploy: going live only with the USER's explicit yes, then say where it is.

Class of error: an irreversible step taken on the agent's own initiative (h2-6: deployed
without being asked). A sentence in a prompt can be skipped; the wrapper cannot: without
--approved it runs nothing and prints what it would run."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "mentat_web.py"


class WebDeploy(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.flag = self.tmp / "deployed"
        self.cmd = [sys.executable, "-c",
                    "import pathlib; pathlib.Path(%r).write_text('x'); "
                    "print('Deployed to https://demo.acct.workers.dev')" % str(self.flag)]

    def deploy(self, *args):
        return subprocess.run([sys.executable, str(TOOL), "deploy", *args, "--", *self.cmd],
                              capture_output=True, text=True)

    def test_without_an_explicit_yes_nothing_runs(self):
        for extra in ((), ("--approved", ""), ("--approved", "  ")):
            r = self.deploy(*extra)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertFalse(self.flag.exists(), extra)
            self.assertIn("NOT DEPLOYED", r.stdout)

    def test_with_the_users_yes_it_runs_and_says_where(self):
        r = self.deploy("--approved", "igen, mehet élesbe")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.flag.exists())
        self.assertIn("LIVE https://demo.acct.workers.dev", r.stdout)

    def test_a_failed_deploy_says_not_live(self):
        r = subprocess.run([sys.executable, str(TOOL), "deploy", "--approved", "yes", "--",
                            sys.executable, "-c", "raise SystemExit(3)"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)
        self.assertIn("NOT LIVE", r.stdout)


if __name__ == "__main__":
    unittest.main()
