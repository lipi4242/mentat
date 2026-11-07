"""mentat_google_auth.py: the official sign-in flow, a bounded wait, one place for the secret.

Class of error (holdout, 0.3.0): the agent wrote its own OAuth callback server instead of the
library's, a background process expired during 20 silent minutes, and the connector note named
.env while the secret actually lay elsewhere.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import stat
import subprocess
import tempfile
import unittest

from _contract_fixture import brain, write
from _google_fixture import run, token
from _google_flow_fake import install
from _google_fake import Fake

CLIENT = {"installed": {"client_id": "cid", "client_secret": "csecret", "redirect_uris": ["http://localhost"]}}


class Auth(unittest.TestCase):
    def setUp(self):
        self.root = brain()
        self.log = os.path.join(tempfile.mkdtemp(), "flow.log")
        self.env = {"PYTHONPATH": install(tempfile.mkdtemp()), "FAKE_FLOW_LOG": self.log}

    def auth(self, *args, env=None):
        return run(self.root, None, *args, tool="mentat_google_auth.py", extra_env=env or self.env)

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def secret(self, name):
        return self.root / ".secrets" / "google" / name

    def client(self):
        r = self.auth("import-client", str(write(self.root, "dl.json", CLIENT)))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_client_file_goes_to_one_private_ignored_place(self):
        r = self.auth("import-client", str(write(self.root, "web.json", {"web": CLIENT["installed"]})))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Desktop app", r.stdout)
        self.client()
        self.assertEqual(stat.S_IMODE(self.secret("client.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.secret("client.json").parent.stat().st_mode), 0o700)
        self.assertIn(".secrets/", (self.root / ".gitignore").read_text().split())

    def test_a_tracked_secrets_folder_stops_everything(self):
        self.client()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "-f", ".secrets/google/client.json"], check=True)
        r = self.auth("login")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("tracked by git", r.stdout)

    def test_a_missing_library_says_what_to_install(self):
        self.client()
        r = self.auth("login", env={"PYTHONPATH": install(tempfile.mkdtemp(), broken=True)})
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("pip install", r.stdout)
        self.assertIn("google-auth-oauthlib", r.stdout)

    def test_local_sign_in_uses_the_library_server_with_a_bounded_wait(self):
        self.client()
        r = self.auth("login", "--no-browser", "--port", "8765", "--timeout", "120")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.calls()[0]
        self.assertEqual((call["call"], call["port"], call["open_browser"], call["timeout_seconds"]),
                         ("run_local_server", 8765, False, 120))
        self.assertIn("ssh -L 8765:localhost:8765", r.stdout)
        self.assertEqual(stat.S_IMODE(self.secret("token.json").stat().st_mode), 0o600)
        note = (self.root / "brain" / "connectors" / "google.md").read_text()
        self.assertIn(".secrets/google/token.json", note)
        self.assertIn("calendar", note)
        for leak in ("csecret", "a-good", "r-1"):
            self.assertNotIn(leak, r.stdout + note)

    def test_a_timeout_says_so_and_saves_nothing(self):
        self.client()
        r = self.auth("login", "--timeout", "5", env=dict(self.env, FAKE_FLOW_TIMEOUT="1"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("5 s", r.stdout)
        self.assertFalse(self.secret("token.json").exists())

    def test_remote_sign_in_in_two_steps_without_a_server(self):
        self.client()
        r = self.auth("login", "--remote", "--port", "8765")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("https://accounts.example.com/o/oauth2/auth", r.stdout)
        self.assertEqual(stat.S_IMODE(self.secret("pending.json").stat().st_mode), 0o600)
        r = self.auth("finish", "http://localhost:8765/?state=s-1&code=c-1&scope=x")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fetch = [c for c in self.calls() if c["call"] == "fetch_token"][0]
        self.assertEqual((fetch["url"][:8], fetch["verifier"], fetch["state"]), ("https://", "v-123", "s-1"))
        self.assertFalse(self.secret("pending.json").exists())
        self.assertTrue(self.secret("token.json").exists())

    def test_an_expired_remote_sign_in_starts_again(self):
        self.client()
        self.auth("login", "--remote")
        p = json.loads(self.secret("pending.json").read_text())
        self.secret("pending.json").write_text(json.dumps(dict(p, expires=0)))
        r = self.auth("finish", "http://localhost:8765/?state=s-1&code=c-1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("start again", r.stdout)


class Token(unittest.TestCase):
    def setUp(self):
        self.fake, self.root = Fake(), brain()

    def tearDown(self):
        self.fake.close()

    def test_an_expired_token_is_refreshed_and_kept(self):
        path = token(self.root, self.fake, expiry="2000-01-01T00:00:00Z", value="a-old")
        r = run(self.root, self.fake, "calendar", "create", "--title", "Dentist", "--start",
                "2026-11-07T09:00:00", "--end", "2026-11-07T10:00:00", "--tz", "Europe/Budapest", "--notify", "none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.fake.calls[0][3]["grant_type"], "refresh_token")
        self.assertEqual(json.loads(path.read_text())["token"], "a-new")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_no_token_says_how_to_sign_in(self):
        r = run(self.root, self.fake, "drive", "read", "f1")
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertIn("mentat_google_auth.py login", r.stdout)


if __name__ == "__main__":
    unittest.main()
