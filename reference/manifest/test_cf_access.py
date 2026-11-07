"""mentat_cf_access: Access in front of a Worker through the API (idempotent), not by buttons."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from _cf_fake import TOKEN, Fake

TOOL = pathlib.Path(__file__).resolve().parent.parent / "web" / "mentat_cf_access.py"


class CfAccess(unittest.TestCase):
    def run_tool(self, fake, *args, token=TOKEN):
        env = dict(os.environ, CLOUDFLARE_API_BASE=fake.base, CLOUDFLARE_API_TOKEN=token,
                   CLOUDFLARE_ACCOUNT_ID="acc1")
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                              env=env, cwd=tempfile.mkdtemp())

    def fake(self, **kw):
        f = Fake(**kw)
        self.addCleanup(f.close)
        return f

    def test_creates_once_then_is_idempotent(self):
        f = self.fake()
        r = self.run_tool(f, "ensure", "--worker", "lista", "--email", "a@example.com")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(f.created), 1)
        app = f.created[0]
        self.assertEqual(app["type"], "self_hosted")
        self.assertEqual(app["destinations"], [{"type": "worker", "worker_id": "tag123"}])
        self.assertIn({"email": {"email": "a@example.com"}}, app["policies"][0]["include"])
        r = self.run_tool(f, "ensure", "--worker", "lista", "--email", "a@example.com")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(f.created), 1)
        self.assertIn("already", r.stdout)

    def test_dry_run_creates_nothing(self):
        f = self.fake()
        r = self.run_tool(f, "ensure", "--worker", "lista", "--email", "a@example.com", "--dry-run")
        self.assertEqual((r.returncode, f.created), (0, []))
        self.assertIn("would create", r.stdout)

    def test_check_reports_unprotected_worker(self):
        r = self.run_tool(self.fake(), "check", "--worker", "lista")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT protected", r.stdout)

    def test_missing_permission_names_it_and_bad_token_is_clear(self):
        r = self.run_tool(self.fake(perms=("workers",)), "ensure", "--worker", "lista", "--email", "a@example.com")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Access: Apps and Policies", r.stdout + r.stderr)
        r = self.run_tool(self.fake(), "check", "--worker", "lista", token="t-bad")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("t-bad", r.stdout + r.stderr)  # the token is never echoed


if __name__ == "__main__":
    unittest.main()
