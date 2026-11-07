"""mentat_web.py check: after a web deploy, one request as the USER sees it.

Class of error: "it works for me" — the agent checks the raw URL or a 302 to a sign-in page
and calls it live, while the signed-in USER gets 403 (h2-5: two models, two live 403s). The
tool follows no redirect (a redirect to sign-in is not "up"), sends the USER's credential
(Access cookie or service token) and never prints it."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import http.server
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "mentat_web.py"
COOKIE, CID, CSECRET = "CF_Authorization=good-cookie-value", "svc-id", "svc-secret-value"


class Fake(http.server.BaseHTTPRequestHandler):
    """A worker behind Access: signed in → 200 with data, otherwise → 302 to the sign-in page."""
    def do_GET(self):
        ok = COOKIE in (self.headers.get("Cookie") or "") or (
            self.headers.get("CF-Access-Client-Id") == CID and self.headers.get("CF-Access-Client-Secret") == CSECRET)
        if ok:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"items: 20")
        else:
            self.send_response(302)
            self.send_header("Location", "https://team.cloudflareaccess.com/login?token=xyz")
            self.end_headers()

    def log_message(self, *a):
        pass


class WebCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/" % cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_tool(self, *args, env=None):
        return subprocess.run([sys.executable, str(TOOL), "check", self.url, *args], capture_output=True,
                              text=True, env=dict(os.environ, **(env or {})))

    def test_unsigned_request_is_not_up(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("FAIL 302"), r.stdout)
        self.assertNotIn("token=xyz", r.stdout + r.stderr)

    def test_signed_in_with_the_cookie_file(self):
        f = pathlib.Path(tempfile.mkdtemp()) / "cookie"
        f.write_text(COOKIE + "\n")
        r = self.run_tool("--cookie-file", str(f), "--contains", "items: 20")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("OK 200"), r.stdout)
        self.assertNotIn("good-cookie-value", r.stdout + r.stderr)

    def test_service_token_from_env_and_contains(self):
        env = {"MY_ID": CID, "MY_SECRET": CSECRET}
        self.assertEqual(self.run_tool("--service-token-env", "MY_ID", "MY_SECRET", env=env).returncode, 0)
        r = self.run_tool("--service-token-env", "MY_ID", "MY_SECRET", "--contains", "items: 21", env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing", r.stdout)
        self.assertNotIn("svc-secret-value", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
