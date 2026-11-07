"""`fleet login`: URL ki, kód be a fifo-ba stdin-en, próba, takarítás — és a kód sehol nem látszik
(2026-10-29: két lejárt login kézi tmux+fifo gyógyítása lett ebből)."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import subprocess
import unittest

from fleet import login

CODE = "s3cr3t-c0de#xyz"
URL = "https://claude.ai/oauth/authorize?code=true&client_id=abc&state=q"
PROBE_OK = '{"type":"result","subtype":"success","is_error":false,"result":"OK","modelUsage":{"claude-opus-5-5":{"inputTokens":3}}}'


class FakeBox:
    """A box: a scriptek szövegéből játssza el a tmux-sessiont; minden hívást naplóz."""
    label = "box"

    def __init__(self, *, url=URL, login_ok=True, echo_code=False, probe=PROBE_OK):
        self.calls, self.pane, self.alive = [], "", False
        self.url, self.login_ok, self.echo_code, self.probe = url, login_ok, echo_code, probe

    def sh(self, script, stdin=None, timeout=60):
        self.calls.append((script, stdin))
        out, rc = "", 0
        if "tmux new-session" in script:
            self.alive = True
            self.pane = "Opening browser…\n" + (f"If it did not open, visit: {self.url}\n" if self.url else "")
        elif "capture-pane" in script:
            out = self.pane
        elif script.startswith("cat > "):
            if not self.alive:
                rc = 1
            else:
                self.pane += (f"Paste code here: {stdin}" if self.echo_code else "Paste code here: ")
                self.pane += ("Login successful\nFLEET-LOGIN-EXIT=0\n" if self.login_ok else
                              "OAuth error: invalid code\nFLEET-LOGIN-EXIT=1\n")
        elif "claude -p" in script:
            out = self.probe
        elif "kill-session" in script:
            self.alive = False
        return subprocess.CompletedProcess(script, rc, out, "")


NOSLEEP = dict(sleep=lambda s: None)


class TestPure(unittest.TestCase):
    def test_url_prefers_oauth_and_strips_punctuation(self):
        pane = "docs: https://docs.example.com/x\nvisit: " + URL + ".\n"
        self.assertEqual(login.login_url(pane), URL)
        self.assertIsNone(login.login_url("no url here"))

    def test_probe_models(self):
        self.assertEqual(login.probe_models(PROBE_OK), (True, ["claude-opus-5-5"]))
        self.assertEqual(login.probe_models('{"is_error":true,"result":"Login expired"}')[0], False)
        self.assertEqual(login.probe_models("garbage"), (False, []))

    def test_account_name_cannot_escape(self):
        for bad in ("../x", "a b", "a;rm", ""):
            with self.assertRaises(ValueError):
                login.check_account(bad)

    def test_scripts_use_fifo_rw_and_account_dir_and_drop_tokens(self):
        s = login.start_script("acc")
        self.assertIn("mkfifo -m 600", s)
        self.assertIn("exec 3<>", s)
        self.assertIn('CLAUDE_CONFIG_DIR="$HOME/.claude-acc"', s)
        self.assertIn("-u CLAUDE_CODE_OAUTH_TOKEN", s)
        self.assertNotIn("CLAUDE_CONFIG_DIR", login.start_script("shared"))


class TestFlow(unittest.TestCase):
    def test_start_prints_only_url(self):
        box = FakeBox()
        r = login.start(box, "acc", **NOSLEEP)
        self.assertEqual(r, {"ok": True, "url": URL})

    def test_start_without_url_cleans_up(self):
        box = FakeBox(url=None)
        t = iter(range(0, 1000, 30))
        r = login.start(box, "acc", timeout=60, clock=lambda: next(t), **NOSLEEP)
        self.assertFalse(r["ok"])
        self.assertIn("kill-session", box.calls[-1][0])

    def test_finish_success_probe_and_cleanup_code_only_on_stdin(self):
        box = FakeBox()
        login.start(box, "acc", **NOSLEEP)
        r = login.finish(box, "acc", CODE + "\n", "opus", **NOSLEEP)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["models"], ["claude-opus-5-5"])
        self.assertIn("kill-session", box.calls[-1][0])
        self.assertFalse(box.alive)
        sent = [(s, i) for s, i in box.calls if i and CODE in i]
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0][0].startswith("cat > "))
        self.assertFalse(any(CODE in s for s, _ in box.calls), "a kód nem kerülhet parancssorba")
        self.assertNotIn(CODE, repr(r))

    def test_failed_login_redacts_echoed_code_and_cleans_up(self):
        box = FakeBox(login_ok=False, echo_code=True)
        login.start(box, "acc", **NOSLEEP)
        r = login.finish(box, "acc", CODE, "opus", **NOSLEEP)
        self.assertFalse(r["ok"])
        self.assertNotIn(CODE, repr(r))
        self.assertIn("***", repr(r))
        self.assertIn("kill-session", box.calls[-1][0])

    def test_failed_probe_after_login_is_not_ok(self):
        box = FakeBox(probe='{"is_error":true,"result":"Invalid API key"}')
        login.start(box, "acc", **NOSLEEP)
        r = login.finish(box, "acc", CODE, "opus", **NOSLEEP)
        self.assertFalse(r["ok"])
        self.assertIn("claude-auth.env", " ".join(r["notes"]))

    def test_code_without_session_says_restart(self):
        r = login.finish(FakeBox(), "acc", CODE, "opus", **NOSLEEP)
        self.assertFalse(r["ok"])
        self.assertIn("fut még a login-session", r["notes"][0])


if __name__ == "__main__":
    unittest.main()
