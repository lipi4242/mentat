"""Before a Cloudflare deploy: every token permission THIS project needs, named at once.

Failure class: a deploy that never went live — a 403 from the API, the token's permissions
never checked against what the project binds (KV, R2, D1), no live address, no protection.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from _cf_fake import Fake

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
HERE = pathlib.Path(__file__).resolve().parent
TOML = 'name = "lista"\n[[d1_databases]]\nbinding = "DB"\n[[kv_namespaces]]\nbinding = "KV"\nid = "x"\n'


class Need(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        (self.dir / "wrangler.toml").write_text(TOML)
        (self.dir / ".env").write_text("CLOUDFLARE_API_TOKEN=t-good\n")
        os.chmod(self.dir / ".env", 0o600)

    def env(self, fake, path=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLOUDFLARE_")}
        env["CLOUDFLARE_API_BASE"] = fake.base
        if path:
            env["PATH"] = path + os.pathsep + env.get("PATH", "")
        return env

    def fake(self, perms):
        f = Fake(perms=perms)
        self.addCleanup(f.close)
        return f

    def test_every_missing_permission_of_this_project_is_named_with_the_step(self):
        r = subprocess.run([sys.executable, str(WEB / "mentat_cf_token.py"), "--check", "--for", "wrangler.toml"],
                           capture_output=True, text=True, cwd=self.dir, env=self.env(self.fake(("workers", "access"))))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("D1", r.stdout)
        self.assertIn("Workers KV Storage", r.stdout)
        self.assertNotIn("R2", r.stdout)
        self.assertIn("Update token", r.stdout)
        ok = subprocess.run([sys.executable, str(WEB / "mentat_cf_token.py"), "--check", "--for", "wrangler.toml"],
                            capture_output=True, text=True, cwd=self.dir,
                            env=self.env(self.fake(("workers", "access", "d1", "kv"))))
        self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_a_plain_check_judges_the_project_here_not_a_fixed_list(self):  # a false RED before
        (self.dir / "wrangler.toml").write_text('name = "x"\n[[kv_namespaces]]\nbinding = "KV"\nid = "y"\n')
        r = subprocess.run([sys.executable, str(WEB / "mentat_cf_token.py"), "--check"], capture_output=True,
                           text=True, cwd=self.dir, env=self.env(self.fake(("workers", "access", "kv"))))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_deploy_stops_before_wrangler_runs_when_the_token_is_short(self):
        bin_dir = pathlib.Path(tempfile.mkdtemp())
        marker = self.dir / "wrangler-ran"
        (bin_dir / "wrangler").write_text("#!/bin/sh\ntouch %s\necho https://lista.acc.workers.dev\n" % marker)
        os.chmod(bin_dir / "wrangler", 0o755)
        args = [sys.executable, str(HERE / "mentat_web.py"), "deploy", "--approved", "igen", "--", "wrangler", "deploy"]
        r = subprocess.run(args, capture_output=True, text=True, cwd=self.dir,
                           env=self.env(self.fake(("workers", "access")), str(bin_dir)))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("NOT DEPLOYED", r.stdout)
        self.assertFalse(marker.exists(), "wrangler must not run with a short token")
        r = subprocess.run(args, capture_output=True, text=True, cwd=self.dir,
                           env=self.env(self.fake(("workers", "access", "d1", "kv")), str(bin_dir)))
        self.assertIn("LIVE https://lista.acc.workers.dev", r.stdout)
        self.assertIn("mentat_done.py --protected https://lista.acc.workers.dev", r.stdout)


class BaseUrl(unittest.TestCase):
    """Failure class: the product's tool ignored the standard environment setting wrangler honors
    (CLOUDFLARE_API_BASE_URL: a gateway, a proxy, a mock) and went to the public API (403)."""

    def run_check(self, env_extra):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / ".env").write_text("CLOUDFLARE_API_TOKEN=t-good\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLOUDFLARE_")}
        env.update(env_extra)
        return subprocess.run([sys.executable, str(WEB / "mentat_cf_token.py"), "--check"],
                              capture_output=True, text=True, cwd=d, env=env, timeout=60)

    def test_the_standard_variable_is_honoured_and_wins(self):
        f = Fake()
        self.addCleanup(f.close)
        r = self.run_check({"CLOUDFLARE_API_BASE_URL": f.base})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_check({"CLOUDFLARE_API_BASE_URL": f.base, "CLOUDFLARE_API_BASE": "http://127.0.0.1:9"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_check({"CLOUDFLARE_API_BASE": f.base})  # the old name still works
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_token_never_goes_to_a_foreign_host(self):  # CISO B2
        r = self.run_check({"CLOUDFLARE_API_BASE_URL": "https://evil.example/client/v4"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not sent", r.stdout + r.stderr)
        r = self.run_check({"CLOUDFLARE_API_BASE_URL": "http://cfapi:9/client/v4", "MENTAT_CF_API_ALLOW_HOST": "cfapi"})
        self.assertNotIn("not sent", r.stdout + r.stderr, "a host a person allowed is used")


if __name__ == "__main__":
    unittest.main()
