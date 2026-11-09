"""mentat_bugreport.py: secrets, e-mails, home paths and private names never leave (not in the
draft, not in the duplicate search); nothing is posted without the exact approval code AND a clear
owner yes; duplicates are offered as a comment; security problems and a missing gh never post.
Every secret-shaped fixture is built at run time, so no literal one ships in this file."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_bugreport.py"
sys.path.append(str(HERE))
import mentat_bugreport_redact as red  # noqa: E402

GH_TOKEN = "gh" + "p_" + "aB3dE5gH7jK9" * 3
BOT = "7012345678" + ":" + "AAH" + "x9Yz" * 8
MAIL = "anna.kovacs" + "@" + "corp-mail.hu"
HOME = "/Us" + "ers/annak/agent/.env"
CHAT = "75514" + "17720"
NAME = "Kovacs Anna"
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
open(os.environ["FAKE_GH_LOG"], "a").write(json.dumps(a) + "\n")
if a[:2] == ["auth", "status"]:
    sys.exit(1 if os.environ.get("FAKE_GH_NOAUTH") else 0)
if a[:2] == ["search", "issues"]:
    print(os.environ.get("FAKE_GH_SEARCH", "[]")); sys.exit(0)
if a[:2] in (["issue", "create"], ["issue", "comment"]):
    body = open(a[a.index("--body-file") + 1]).read()
    open(os.environ["FAKE_GH_LOG"], "a").write(json.dumps({"posted_body": body}) + "\n")
    print("https://github.com/lipi4242/mentat/issues/99"); sys.exit(0)
sys.exit(2)
'''


class BugReport(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.tmp / "agent"
        (self.repo / "brain/people").mkdir(parents=True)
        (self.repo / "brain/people/kovacs-anna.md").write_text("x")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.log = self.tmp / "gh.log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_dir, os.environ["PATH"]), HOME=str(self.tmp / "home"),
                        FAKE_GH_LOG=str(self.log))
        for k in ("CLAUDE_CODE_ENTRYPOINT", "CLAUDECODE", "MENTAT_SRC"):
            self.env.pop(k, None)

    def run_tool(self, *args, **env):
        return subprocess.run([sys.executable, "-I", str(TOOL), *args, "--repo", str(self.repo)],
                              capture_output=True, text=True, timeout=60, env=dict(self.env, **env))

    def draft(self, *extra, error=None, **env):
        err = error or ("Traceback: auth failed for %s token=%s bot %s\nchat %s config %s\nby %s"
                        % (MAIL, GH_TOKEN, BOT, CHAT, HOME, NAME))
        r = self.run_tool("draft", "--summary", "fleet doctor crashes on start for %s" % NAME,
                          "--expected", "a report", "--error", err, "--part", "fleet", "--install", "server",
                          *extra, **env)
        out = [l.split(" ", 1)[1] for l in r.stdout.splitlines() if l.startswith("DRAFT ")]
        return r, (pathlib.Path(out[0]) if out else None)

    def gh_calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def code(self, d):
        return json.loads((d / "draft.json").read_text())["digest"]

    def test_nothing_private_leaves_draft_or_search(self):
        r, d = self.draft()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sent = (d / "draft.md").read_text() + (d / "draft.json").read_text() + json.dumps(self.gh_calls())
        for secret in (GH_TOKEN, MAIL, "annak", CHAT, BOT.split(":")[1], "Kovacs", "Anna", "anna"):
            self.assertNotIn(secret, sent, secret)
        self.assertIn("<!-- mentat-bug-report v1 -->", sent)
        self.assertIn("### Error output", sent)

    def test_the_search_query_carries_no_digits_or_secrets(self):
        r, d = self.draft()
        queries = [c[-1] for c in self.gh_calls() if isinstance(c, list) and c[:2] == ["search", "issues"]]
        self.assertEqual(len(queries), 1)
        self.assertFalse(any(ch.isdigit() for ch in queries[0]), queries[0])
        for secret in ("kovacs", "anna", "annak", "corp-mail"):
            self.assertNotIn(secret, queries[0].lower())

    def test_no_post_without_code_and_clear_yes(self):
        r, d = self.draft()
        for code, said in (("000000000000", "igen"), (self.code(d), "no"), (self.code(d), "igen, de várj"),
                           (self.code(d), ""), (self.code(d), "yes, but only save a draft"),
                           (self.code(d)[:12], "yes")):
            p = self.run_tool("post", str(d), "--approve", code, "--owner-said", said)
            self.assertEqual(p.returncode, 3, p.stdout)
        self.assertFalse(any(c[:2] == ["issue", "create"] for c in self.gh_calls() if isinstance(c, list)))

    def test_approved_post_sends_exactly_the_draft(self):
        r, d = self.draft()
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "igen, mehet")
        self.assertEqual(p.returncode, 0, p.stdout)
        posted = [c["posted_body"] for c in self.gh_calls() if isinstance(c, dict)]
        self.assertEqual(posted, [json.loads((d / "draft.json").read_text())["body"]])
        self.assertTrue((d / "approval.json").is_file())

    def test_an_edited_draft_needs_a_new_yes(self):
        r, d = self.draft()
        code = self.code(d)
        j = json.loads((d / "draft.json").read_text())
        j["body"] += "\nsmuggled %s\n" % MAIL
        (d / "draft.json").write_text(json.dumps(j))
        p = self.run_tool("post", str(d), "--approve", code, "--owner-said", "yes")
        self.assertEqual(p.returncode, 3, p.stdout)

    def test_duplicate_is_offered_and_comment_goes_to_it(self):
        dup = json.dumps([{"number": 12, "title": "fleet doctor crashes on start", "state": "OPEN",
                           "url": "https://github.com/lipi4242/mentat/issues/12"}])
        r, d = self.draft(FAKE_GH_SEARCH=dup)
        self.assertIn("POSSIBLE DUPLICATE #12", r.stdout)
        self.assertIn("--comment-on 12", r.stdout)
        r, d = self.draft("--comment-on", "12")
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "ok")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(any(c[:3] == ["issue", "comment", "12"] for c in self.gh_calls() if isinstance(c, list)))

    def test_security_problem_never_goes_public(self):
        r, d = self.draft(error="the bridge leaks the bot token into the log")
        self.assertEqual(r.returncode, 5, r.stdout)
        self.assertIn("security/advisories/new", r.stdout)
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "yes")
        self.assertEqual(p.returncode, 5, p.stdout)

    def test_without_gh_the_draft_stays_for_a_manual_post(self):
        r, d = self.draft(FAKE_GH_NOAUTH="1")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("DUPLICATES: not checked", r.stdout)
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "yes", FAKE_GH_NOAUTH="1")
        self.assertEqual(p.returncode, 4, p.stdout)
        self.assertIn("issues/new", p.stdout)

    def test_dry_run_and_daily_limit(self):
        r, d = self.draft()
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "yes", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertFalse(any(isinstance(c, dict) for c in self.gh_calls()))
        (d.parent / "posted.log").write_text("".join("%sT00:00:00+00:00 x\n" % __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).date().isoformat() for _ in range(3)))
        p = self.run_tool("post", str(d), "--approve", self.code(d), "--owner-said", "yes")
        self.assertEqual(p.returncode, 6, p.stdout)


class Redaction(unittest.TestCase):
    def test_every_kind_is_removed_and_residue_is_empty(self):
        ip = ".".join(["10", "20", "30", "40"])
        uid = "0f8fad5b-d9cb-469f-a165-" + "70867728950e"
        text = ("curl -H 'Authorization: Bearer %s' https://bob:%s@api.example.org --api-key %s\n"
                "PASSWORD=%s ip %s id %s iban %s phone %s %s C:\\Users\\annak\\x %s"
                % ("Zz9" * 6, "hunter2", "q" * 8 + "1" * 8, "pw-" + "s3cr3t", ip, uid,
                   "HU42" + " 1177 3016 1111 1018 0000 0000", "+36 30 " + "123 4567", MAIL, "/ho" + "me/annak/y"))
        out, counts = red.redact(text, [NAME, "annak"])
        for s in ("Zz9Zz9", "hunter2", "s3cr3t", ip, uid, "1177 3016", "123 4567", MAIL, "annak"):
            self.assertNotIn(s, out, s)
        self.assertEqual(red.residue(out, [NAME, "annak"]), [])

    def test_review_findings_stay_fixed(self):
        """Codex review 11-08: each input once slipped through; the value must be ABSENT."""
        user = "ali" + "ce"
        cases = {"password=<violet>": "violet", "chat_id=12345678": "12345678",
                 "chat:123456789": "123456789", "channel=-1001234567890": "1001234567890",
                 "/HO" + "ME/%s/p" % user: user, "C:/Us" + "ers/%s/p" % user: user,
                 "/ho" + "me\\/%s/p" % user: user, "Alice  Smith said": "Smith",
                 "Smith alone": "Smith", 'password="violet\norchid"': "orchid"}
        for text, secret in cases.items():
            with self.subTest(text):
                out = red.redact(text, ["Alice Smith"])[0]
                self.assertNotIn(secret, out)
                self.assertEqual(red.residue(out, ["Alice Smith"]), [])

    def test_residue_catches_what_redaction_missed(self):
        self.assertIn("e-mail", red.residue("contact " + MAIL))
        self.assertIn("private name", red.residue("by %s" % NAME, [NAME]))

    def test_ordinary_text_survives(self):
        text = ("fleet doctor exits 1 on Python 3.12.4, see engine/sync-to.sh line 42\n"
                "KeyError: 'schedule_owner' at 12:34:56; TokenExpiredError: refresh failed\n"
                "monkey=42 author=\"Ada\" valid=True token session.close() at 2026:11:08; e-mail addresses")
        self.assertEqual(red.redact(text)[0], text)


if __name__ == "__main__":
    unittest.main()
