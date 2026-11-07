"""Done means verified: one pre-close check instead of the agent's own impression.

Failure classes: half-done work reported as done; a scheduled output claimed to have run
without a check. mentat_done.py checks what can be checked from here: the address or file
the USER was given, the last scheduled tick, unsaved work, and pages still running.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent


def done(root, *args):
    return subprocess.run([sys.executable, "-I", str(HERE / "mentat_done.py"), "--repo", str(root), *args],
                          capture_output=True, text=True, timeout=60)


def serve(root, *args):
    return subprocess.run([sys.executable, "-I", str(HERE / "mentat_serve.py"), "--repo", str(root), *args],
                          capture_output=True, text=True, timeout=60)


class Done(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(self.root / ".gc"))
        for cmd in (["init", "-q"], ["config", "user.name", "A"], ["config", "user.email", "a@example.com"]):
            subprocess.run(["git", "-C", str(self.root), *cmd], check=True, env=env)
        (self.root / ".gitignore").write_text(".mentat/\n.gc\n")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "x"], check=True, env=env)
        self.addCleanup(serve, self.root, "stop", "--all")

    def test_nothing_checked_is_not_verified_and_a_local_address_is_local_only(self):
        r = done(self.root)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("DONE-CHECK NOT VERIFIED", r.stdout)
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text("ok")
        url = next(ln[4:] for ln in serve(self.root, "start", "lap", "--dir", "site").stdout.splitlines()
                   if ln.startswith("URL "))
        r = done(self.root, "--url", url)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("DONE-CHECK LOCAL ONLY", r.stdout)
        (self.root / "lista.csv").write_text("a\n")
        self.assertIn("DONE-CHECK GREEN", done(self.root, "--file", "lista.csv").stdout)

    def test_a_missing_or_empty_file_and_a_dead_address_are_red(self):
        (self.root / "ures.csv").write_text("")
        r = done(self.root, "--file", "ures.csv", "--file", "nincs.md", "--url", "http://127.0.0.1:1/")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(sum(ln.startswith("RED ") for ln in r.stdout.splitlines()), 3, r.stdout)
        self.assertIn("do not call it done", r.stdout)

    def test_a_given_address_that_answers_and_a_real_file_are_ok(self):
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text("ok")
        (self.root / "lista.csv").write_text("a,b\n")
        url = next(ln[4:] for ln in serve(self.root, "start", "lap", "--dir", "site").stdout.splitlines()
                   if ln.startswith("URL "))
        r = done(self.root, "--url", url, "--file", "lista.csv")
        self.assertIn("OK address answers", r.stdout)
        self.assertIn("OK file lista.csv", r.stdout)
        self.assertIn("WARN still running: lap", r.stdout)  # the USER hears it is running and until when

    def test_unsaved_work_is_named(self):
        (self.root / "jegyzet.md").write_text("x")
        r = done(self.root)
        self.assertIn("WARN not committed: 1", r.stdout)

    def test_a_schedule_claim_needs_a_recent_tick(self):
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 1)
        self.assertIn("has not run here", r.stdout)
        tick = self.root / "data" / "state" / "last-tick.json"
        tick.parent.mkdir(parents=True)
        tick.write_text(json.dumps({}))
        old = time.time() - 3 * 86400
        os.utime(tick, (old, old))
        self.assertIn("RED the last scheduled tick", done(self.root, "--scheduled").stdout)
        os.utime(tick, None)
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK last scheduled tick", r.stdout)


    def tick(self, actions=1, errors=(), age=0):
        st = self.root / "data" / "state"
        st.mkdir(parents=True, exist_ok=True)
        (st / "last-tick.json").write_text(json.dumps({"trigger": "hourly", "actions": actions}))
        (st / "last-summary.json").write_text(json.dumps({"planned": [], "skipped": {}, "errors": list(errors)}))
        when = time.time() - age
        os.utime(st / "last-tick.json", (when, when))
        comp = {"engine": {"path": "anytime_engine", "delivery": {"channel": "file"}}}
        (self.root / "mentat.json").write_text(json.dumps({"schema": 1, "components": comp}))

    def test_a_tick_that_planned_work_but_wrote_no_output_is_red(self):  # the job's output, not the timer
        self.tick(actions=2)
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no output", r.stdout)
        out = self.root / "data" / "outbox" / "2026-10-25.md"
        out.parent.mkdir(parents=True)
        out.write_text("Ma esedékes: 1\n")
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK the scheduled output", r.stdout)

    def test_a_degraded_tick_is_red_even_when_it_landed(self):
        self.tick(actions=0, errors=["cases: the cases folder is unreadable"])
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unreadable", r.stdout)

    def test_an_own_jobs_output_must_be_newer_than_the_last_tick(self):
        self.tick(actions=0)
        rep = self.root / "riport.md"
        rep.write_text("x")
        old = time.time() - 5 * 3600
        os.utime(rep, (old, old))
        self.assertIn("RED output riport.md", done(self.root, "--scheduled", "--output", "riport.md").stdout)
        os.utime(rep, None)
        self.assertEqual(done(self.root, "--scheduled", "--output", "riport.md").returncode, 0)


    def commit_file(self, rel, text):
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text)
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(self.root / ".gc"))
        subprocess.run(["git", "-C", str(self.root), "add", "-f", rel], check=True, env=env)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", rel], check=True, env=env)

    def test_a_credential_in_a_tracked_file_must_be_told_never_shown(self):
        key = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"
        self.commit_file("config/settings.py", "DEBUG = True\nOPENAI = '%s'\n" % key)
        self.commit_file(".env", "X=1\n")
        self.commit_file(".env.example", "API_KEY=<your key>\n")
        r = done(self.root)
        self.assertIn("TELL credential (API key) in a file git keeps: config/settings.py:2", r.stdout)
        self.assertIn("TELL credential (secret file) in a file git keeps: .env", r.stdout)
        self.assertNotIn(".env.example", r.stdout)
        self.assertNotIn(key, r.stdout)
        self.assertIn("first tell the USER", r.stdout)


    def page(self, code, location=None):
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(code)
                if location:
                    self.send_header("Location", location)
                self.end_headers()
                self.wfile.write(b"ok")
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return "http://127.0.0.1:%d/" % srv.server_address[1]

    def test_a_page_that_should_be_protected_must_send_unsigned_visitors_to_the_sign_in(self):
        r = done(self.root, "--protected", self.page(200))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("anyone can open it", r.stdout)
        gate = self.page(302, "https://team.cloudflareaccess.com/cdn-cgi/access/login/x?redirect_url=%2F")
        r = done(self.root, "--protected", gate)
        self.assertIn("OK protected", r.stdout)
        self.assertNotIn("redirect_url", r.stdout)

    def test_a_scheduled_output_must_hold_what_the_job_promised(self):
        self.tick(actions=1)
        out = self.root / "data" / "outbox" / "2026-10-25.md"
        out.parent.mkdir(parents=True)
        out.write_text("Ma esedékes: 2 ügy\n")
        r = done(self.root, "--scheduled", "--expect", "Hívd fel:")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("lacks what the job promised: 'Hívd fel:'", r.stdout)
        out.write_text("Ma esedékes: 2 ügy\nHívd fel: Kovács Anna\n")
        self.assertEqual(done(self.root, "--scheduled", "--expect", "Hívd fel:").returncode, 0)


    def test_the_jobs_stored_promise_is_checked_without_being_passed(self):  # engine setup --expect
        self.tick(actions=1)
        doc = json.loads((self.root / "mentat.json").read_text())
        doc["components"]["engine"]["delivery"]["expect"] = ["Hívd fel:"]
        (self.root / "mentat.json").write_text(json.dumps(doc))
        out = self.root / "data" / "outbox" / "2026-10-25.md"
        out.parent.mkdir(parents=True)
        out.write_text("Ma esedékes: 2 ügy\n")
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("lacks what the job promised: 'Hívd fel:'", r.stdout)


    def test_a_stopped_schedule_says_how_to_fix_it_and_a_manual_run_is_not_a_contradiction(self):
        self.tick(actions=1, age=3 * 86400)  # the timer stopped three days ago
        out = self.root / "data" / "outbox" / "2026-10-25.md"
        out.parent.mkdir(parents=True)
        out.write_text("Ma esedékes: 1\n")  # a manual run just now
        r = done(self.root, "--scheduled")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fix it now", r.stdout)
        self.assertIn("setup --doctor", r.stdout)
        self.assertIn("a manual run left", r.stdout)


if __name__ == "__main__":
    unittest.main()
