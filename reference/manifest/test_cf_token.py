"""mentat_cf_token: the token set-up as a step-by-step tool that checks after every step."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

from _cf_fake import TOKEN, Fake

TOOL = pathlib.Path(__file__).resolve().parent.parent / "web" / "mentat_cf_token.py"


class CfToken(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        (self.dir / ".gitignore").write_text("node_modules/\n")

    def run_tool(self, fake, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLOUDFLARE_")}
        env["CLOUDFLARE_API_BASE"] = fake.base
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                              env=env, cwd=self.dir)

    def fake(self, **kw):
        f = Fake(**kw)
        self.addCleanup(f.close)
        return f

    def test_first_step_prepares_a_private_env_and_says_one_thing(self):
        r = self.run_tool(self.fake(), "next")
        env = self.dir / ".env"
        self.assertTrue(env.is_file())
        self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
        self.assertIn(".env", (self.dir / ".gitignore").read_text())
        self.assertIn("STEP", r.stdout)
        self.assertLessEqual(r.stdout.count("STEP"), 1)  # one step per message
        self.assertEqual(r.returncode, 3)  # waiting for the USER

    def test_missing_permission_is_the_next_step_and_named(self):
        (self.dir / ".env").write_text("CLOUDFLARE_API_TOKEN=%s\n" % TOKEN)
        r = self.run_tool(self.fake(perms=("workers",)), "next")
        self.assertEqual(r.returncode, 3)
        self.assertIn("D1", r.stdout)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)

    def test_all_good_records_the_account_and_check_is_green(self):
        (self.dir / ".env").write_text("CLOUDFLARE_API_TOKEN=%s\n" % TOKEN)
        f = self.fake()
        r = self.run_tool(f, "next")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID=acc1", (self.dir / ".env").read_text())
        r = self.run_tool(f, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)

    def test_bad_token_says_so(self):
        (self.dir / ".env").write_text("CLOUDFLARE_API_TOKEN=nope\n")
        r = self.run_tool(self.fake(), "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid", r.stdout)
        self.assertNotIn("nope", r.stdout)


if __name__ == "__main__":
    unittest.main()
