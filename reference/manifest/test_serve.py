"""A local page, form or dev server never blocks the turn (failure class: a long-running process
started in the foreground or with run_in_background; the USER waited for a reply that never came).

mentat_serve.py start returns at once with a URL that answers, the process lives in its own
session with a bounded lifetime, and status/stop find it again. --secret is a one-time hidden
form that writes the value into a git-ignored 0600 env file, never into the output or the log.
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
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_serve.py"


def run(root, *args):
    return subprocess.run([sys.executable, "-I", str(TOOL), "--repo", str(root), *args],
                          capture_output=True, text=True, timeout=60)


def url_of(out):
    return next(ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("URL "))


class Serve(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".env\n.env.*\n.mentat/\n")
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text("<h1>szia</h1>")
        self.addCleanup(run, self.root, "stop", "--all")

    def test_start_returns_at_once_with_an_answering_url(self):
        t = time.time()
        r = run(self.root, "start", "lap", "--dir", "site", "--minutes", "5")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(time.time() - t, 20)
        url = url_of(r.stdout)
        self.assertTrue(url.startswith("http://127.0.0.1:"), url)
        self.assertIn("szia", urllib.request.urlopen(url, timeout=5).read().decode())
        self.assertIn("lap", run(self.root, "status").stdout)
        self.assertIn("STOPPED lap", run(self.root, "stop", "lap").stdout)
        time.sleep(0.5)
        with self.assertRaises(OSError):
            urllib.request.urlopen(url, timeout=2)

    def test_it_stops_by_itself_after_its_lifetime(self):
        r = run(self.root, "start", "rovid", "--dir", "site", "--seconds", "2")
        url = url_of(r.stdout)
        time.sleep(4)
        with self.assertRaises(OSError):
            urllib.request.urlopen(url, timeout=2)
        self.assertIn("stopped", run(self.root, "status", "rovid").stdout)

    def test_a_command_is_wrapped_and_probed_on_its_port(self):
        port = "18%03d" % (os.getpid() % 1000)
        cmd = [sys.executable, "-m", "http.server", port, "--bind", "127.0.0.1", "--directory", "site"]
        r = run(self.root, "start", "dev", "--port", port, "--minutes", "5", "--", *cmd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("szia", urllib.request.urlopen(url_of(r.stdout), timeout=5).read().decode())
        run(self.root, "stop", "dev")
        time.sleep(0.5)
        with self.assertRaises(OSError):
            urllib.request.urlopen(url_of(r.stdout), timeout=2)

    def test_a_command_that_never_listens_is_not_started(self):
        r = run(self.root, "start", "rossz", "--port", "18999", "--wait", "2", "--",
                sys.executable, "-c", "print('nem figyelek'); import time; time.sleep(30)")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT STARTED", r.stdout)
        self.assertIn("nem figyelek", r.stdout)  # the log's tail, so the agent sees why

    def test_secret_form_writes_a_0600_ignored_env_line_and_never_prints_the_value(self):
        (self.root / ".env").write_text("OTHER=1\nCF_TOKEN=old\n")
        r = run(self.root, "start", "kulcs", "--secret", "CF_TOKEN")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        url = url_of(r.stdout)
        page = urllib.request.urlopen(url, timeout=5).read().decode()
        self.assertIn('type=password', page)
        body = urllib.parse.urlencode({"value": "  s3cr3t-value  "}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=5).read()
        time.sleep(0.5)
        env = self.root / ".env"
        self.assertEqual(env.read_text(), "OTHER=1\nCF_TOKEN=s3cr3t-value\n")
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        st = run(self.root, "status", "kulcs").stdout
        self.assertIn("received", st)
        logs = "".join(p.read_text() for p in (self.root / ".mentat/state/serve").iterdir())
        self.assertNotIn("s3cr3t", logs + st + r.stdout)
        with self.assertRaises(OSError):  # one save, then the form is gone
            urllib.request.urlopen(url, timeout=2)

    def test_secret_refuses_an_env_file_git_would_commit(self):
        r = run(self.root, "start", "kulcs", "--secret", "CF_TOKEN", "--env", "keys.txt")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT STARTED", r.stdout)
        self.assertFalse((self.root / "keys.txt").exists())

    def test_a_foreign_host_header_is_refused(self):
        url = url_of(run(self.root, "start", "lap", "--dir", "site").stdout)
        req = urllib.request.Request(url, headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(e.exception.code, 403)

    def test_stop_never_kills_a_process_it_did_not_start(self):
        state = self.root / ".mentat/state/serve"
        state.mkdir(parents=True)
        (state / "idegen.json").write_text(json.dumps({"name": "idegen", "pid": os.getpid()}))
        r = run(self.root, "stop", "idegen")
        self.assertIn("not running", r.stdout)


    def test_state_and_log_are_private_to_the_owner(self):  # CISO M1: the token is in the state file
        run(self.root, "start", "kulcs", "--secret", "CF_TOKEN")
        d = self.root / ".mentat/state/serve"
        self.assertEqual(d.stat().st_mode & 0o777, 0o700)
        for f in d.iterdir():
            self.assertEqual(f.stat().st_mode & 0o077, 0, f.name)

    def test_dir_mode_never_serves_dot_files_symlinks_out_or_a_folder_outside(self):  # CISO M2
        (self.root / ".env").write_text("X=1\n")
        (self.root / "site" / "link").symlink_to(self.root / ".env")
        url = url_of(run(self.root, "start", "gyoker", "--dir", ".").stdout)
        for path in (".env", "%2Eenv", ".git/config", ".mentat/state/serve/gyoker.json", "site/link"):
            with self.assertRaises(urllib.error.HTTPError, msg=path) as e:
                urllib.request.urlopen(url + path, timeout=5)
            self.assertEqual(e.exception.code, 404, path)
        self.assertIn("szia", urllib.request.urlopen(url + "site/", timeout=5).read().decode())
        self.assertEqual(run(self.root, "start", "kint", "--dir", "..").returncode, 1)

    def test_head_gets_the_same_host_check_and_no_files_in_secret_mode(self):  # CISO M3
        url = url_of(run(self.root, "start", "kulcs", "--secret", "CF_TOKEN").stdout)
        base = url.rsplit("/", 1)[0] + "/"
        for target, host in ((base + "site/index.html", None), (url, "evil.example")):
            req = urllib.request.Request(target, method="HEAD", headers={"Host": host} if host else {})
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(req, timeout=5)

    def test_after_the_save_the_process_ends_and_a_second_post_is_refused(self):  # CISO K3
        url = url_of(run(self.root, "start", "kulcs", "--secret", "CF_TOKEN").stdout)
        body = urllib.parse.urlencode({"value": "elso"}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=5).read()
        time.sleep(1.5)
        self.assertIn("stopped", run(self.root, "status", "kulcs").stdout)
        self.assertIn("CF_TOKEN=elso", (self.root / ".env").read_text())


    def test_a_command_without_a_port_runs_detached_and_bounded(self):  # a watcher, not a server
        r = run(self.root, "start", "figyelo", "--seconds", "3", "--",
                sys.executable, "-c", "import time\nwhile True: print('tick', flush=True); time.sleep(0.2)")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("URL ", r.stdout)
        self.assertIn("RUNNING figyelo", r.stdout)
        self.assertIn("running", run(self.root, "status", "figyelo").stdout)
        time.sleep(4)
        self.assertIn("stopped", run(self.root, "status", "figyelo").stdout)

    def test_a_portless_command_that_dies_at_once_is_not_started(self):
        r = run(self.root, "start", "hibas", "--", sys.executable, "-c", "raise SystemExit('rossz')")
        self.assertEqual(r.returncode, 1)
        self.assertIn("rossz", r.stdout)


if __name__ == "__main__":
    unittest.main()
