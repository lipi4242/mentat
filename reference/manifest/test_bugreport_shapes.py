"""Every shape a secret or an id takes in a log, through the real CLI: the dummy value never
appears in the draft or in what goes to GitHub; residue() flags each shape unredacted; and the
CLI stops (exit 2, nothing written) when redaction misses something. Dummy values only, built
at run time where a literal would trip the release scrub."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "mentat_bugreport.py"
sys.path.append(str(HERE))
import mentat_bugreport as cli  # noqa: E402
import mentat_bugreport_redact as red  # noqa: E402

# (shape, text, the dummy value that must never leave)
SHAPES = [
    ("json double quote", '{"password": "dmyPw0001"}', "dmyPw0001"),
    ("json no space", '{"api_key":"dmyKey0002"}', "dmyKey0002"),
    ("json single quote", "{'token' : 'dmyTok0003'}", "dmyTok0003"),
    ("json chat id", '{"chat_id": "12345678"}', "12345678"),
    ("json numeric id", '{"user_id": 4242424}', "4242424"),
    ("escaped json", '{\\"client_secret\\":\\"dmySec0004\\"}', "dmySec0004"),
    ("multi-line quoted", 'password="dmyLine0005\ndmyLine0006"', "dmyLine0006"),
    ("yaml", "db:\n  password: dmyYaml0007\n", "dmyYaml0007"),
    ("env", "export MY_SERVICE_TOKEN=dmyEnv0008", "dmyEnv0008"),
    ("query string", "GET /cb?code=1&access_token=dmyQs0009&x=2", "dmyQs0009"),
    ("authorization header", "Authorization: Basic dmyHdr0010", "dmyHdr0010"),
    ("cookie header", "Cookie: theme=dark; sid=dmyCk0011", "dmyCk0011"),
    ("api key header", "X-Api-Key: dmyXk0012", "dmyXk0012"),
    ("flag", "fleet login --password dmyFl0013", "dmyFl0013"),
    ("prose en", "it says the password is dmyProse0014 there", "dmyProse0014"),
    ("prose hu", "a jelszó: dmyHu0015", "dmyHu0015"),
    ("handle key", 'handle: "@dmyhandle16"', "dmyhandle16"),
    ("short id prose", "sent to chat 1234567 then failed", "1234567"),
    ("id key short", "chat_id=987", "987"),
    ("ipv4", "connect " + ".".join(["10", "11", "12", "13"]), ".".join(["10", "11", "12", "13"])),
    ("ipv6", "connect 2a01:4f8:c0c:" + "beef::1", "2a01:4f8"),
    ("ipv6 brackets", "http://[fe80::1ff:fe23:" + "4567:890a]:8080/", "fe80::1ff"),
    ("root path", "open /root/dmyproj17/x.py", "dmyproj17"),
    ("home path", "open /ho" + "me/dmyuser18/x.py", "dmyuser18"),
    ("users path", "open /Us" + "ers/dmyuser19/x.py", "dmyuser19"),
    ("tilde user", "open ~dmyuser20/x.py", "dmyuser20"),
    ("windows path", "open C:\\Users\\dmyuser21\\x", "dmyuser21"),
    # Codex adversarial pass on the redactor (11-08)
    ("placeholder prefix", "password=<redacted>dmyPh0022", "dmyPh0022"),
    ("array value", 'password=["dmyArr0023","dmyArr0024"]', "dmyArr0024"),
    ("short basic", "header: Basic YTpi", "YTpi"),
    ("unicode e-mail", "mail \u03b4\u03bf\u03ba@example" + ".test", "\u03b4\u03bf\u03ba@"),
    ("quoted e-mail", '"dmy q25"@example' + ".test", "dmy q25"),
    ("path with space", "/Us" + "ers/Dmy Spaceuser26/app.py", "Spaceuser26"),
    ("labelled short id", "user id 1234", "1234"),
    ("id flag", "--tenant-id 12345678", "12345678"),
    ("embedded ipv6", "x2001:4860:4860::" + "8888", "4860:4860"),
    ("camel key", 'apiKey: "dmyCamel0027"', "dmyCamel0027"),
    # security re-check (11-09): short, human-chosen passwords in key-shaped input
    ("double-escaped json", r'{\\\"password\\\": \\\"Tavasz2026!\\\"}', "Tavasz2026!"),
    ("plural key array", '{"tokens": ["Nyar2026x"]}', "Nyar2026x"),
    ("plural key json", '"passwords": "Osz2026x"', "Osz2026x"),
    ("plural key yaml", "secrets: Tel2026x", "Tel2026x"),
    ("name/value json", '{"name": "API_KEY", "value": "Rozsa77"}', "Rozsa77"),
    ("name/value yaml", "env:\n  - name: DB_PASSWORD\n    value: Kerti55\n", "Kerti55"),
]


class Shapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        cls.repo = cls.tmp / "agent"
        cls.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(cls.repo)], check=True)
        cls.env = dict(os.environ, HOME=str(cls.tmp / "home"), PATH="/usr/bin:/bin")

    def test_redact_removes_every_shape_and_leaves_no_residue(self):
        for shape, text, value in SHAPES:
            with self.subTest(shape):
                out = red.redact(text)[0]
                self.assertNotIn(value, out)
                self.assertEqual(red.residue(out), [], out)

    def test_residue_flags_every_shape_unredacted(self):
        for shape, text, _ in SHAPES:
            with self.subTest(shape):
                self.assertNotEqual(red.residue(text), [], text)

    def test_through_the_cli_no_value_reaches_the_draft(self):
        error = "\n".join(t for _, t, _ in SHAPES)
        r = subprocess.run([sys.executable, "-I", str(TOOL), "draft", "--summary", "doctor fails",
                            "--error", error, "--offline", "--repo", str(self.repo)],
                           capture_output=True, text=True, timeout=60, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = pathlib.Path([l.split(" ", 1)[1] for l in r.stdout.splitlines() if l.startswith("DRAFT ")][0])
        sent = (d / "draft.md").read_text() + json.loads((d / "draft.json").read_text())["body"]
        for shape, _, value in SHAPES:
            self.assertNotIn(value, sent, shape)

    def test_the_cli_stops_when_redaction_misses(self):
        repo = pathlib.Path(tempfile.mkdtemp()) / "agent"
        repo.mkdir()
        out = io.StringIO()
        with mock.patch.object(cli.red, "redact", lambda text, names=(): (text, {})), \
                contextlib.redirect_stdout(out):
            rc = cli.main(["draft", "--summary", "x", "--error", '{"password": "dmyMiss0099"}',
                           "--offline", "--repo", str(repo)])
        self.assertEqual(rc, 2, out.getvalue())
        self.assertIn("STOP", out.getvalue())
        self.assertFalse((repo / ".mentat").exists(), "nothing may be written")



FAMILY_MAIL = "dmyowner" + "@" + "example-family.com"
PROVIDER_MAIL = "dmyowner" + "@" + "gmail.com"


class RealInstallNames(unittest.TestCase):
    """A real install has an agent name and a git e-mail (the 0.6.0 false stop): a PART of a name
    that is an ordinary word ("agent"), a TLD ("com") or a mail provider must not stop the report,
    while the whole name, the domain's own label and the mailbox name are still removed."""

    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp()) / "media-agent"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for key, value in (("user.name", "Dmy Kovaxa"), ("user.email", FAMILY_MAIL)):
            subprocess.run(["git", "-C", str(self.repo), "config", key, value], check=True)
        (self.repo / "mentat.json").write_text(json.dumps({"schema": 1, "agent": {"name": "media-agent"}}))
        self.env = dict(os.environ, HOME=str(self.repo.parent / "home"), PATH="/usr/bin:/bin")

    def test_unit_parts_rule(self):
        self.assertEqual(red.residue(cli.shape.FOOTER, ["media-agent"]), [])
        self.assertEqual(red.residue("see github.com/lipi4242/mentat", [FAMILY_MAIL]), [])
        self.assertIn("private name", red.residue("by media-agent", ["media-agent"]))
        self.assertIn("private name", red.residue("the example-family domain", [FAMILY_MAIL]))
        self.assertIn("private name", red.residue("hi dmyowner", [PROVIDER_MAIL]))

    def test_draft_goes_through_and_still_hides_the_names(self):
        r = subprocess.run([sys.executable, "-I", str(TOOL), "draft", "--summary", "media-agent tick fails",
                            "--error", "run by Dmy Kovaxa (dmyowner) for example-family, see github.com docs",
                            "--offline", "--repo", str(self.repo)],
                           capture_output=True, text=True, timeout=60, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = pathlib.Path([l.split(" ", 1)[1] for l in r.stdout.splitlines() if l.startswith("DRAFT ")][0])
        sent = (d / "draft.md").read_text()
        for private in ("media-agent", "Dmy Kovaxa", "Kovaxa", "dmyowner", "example-family"):
            self.assertNotIn(private, sent, private)
        self.assertIn("Mentat agent", sent)      # the footer survives
        self.assertIn("github.com", sent)        # a TLD part is not a name

if __name__ == "__main__":
    unittest.main()
