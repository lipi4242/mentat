"""flotta-menedzser: `fleet incident claim|release` — a menedzser SAJÁT todo-tokenjével vesz át; az átvétel
(fence, titok, keret) 0600-as fájlba kerül, a titok nem jelenik meg; elutasításnál nincs fájl."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fleet import flotta_report, incident_cli as I
from _flotta_fake import Opener

TODO_TOK = "mentat_HAMIS_todo_token_0123456789abc"
SECRET = "claim-titok-abcdef0123456789"


class Claim(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.dir, True)
        todo = self.dir / "xdg" / "todo"; todo.mkdir(parents=True)
        (todo / "handles").write_text("gondnok=gondnok-h\n")
        (todo / "gondnok-h.token").write_text(TODO_TOK + "\n")
        for obj, name, val in ((I, "CLAIMS", self.dir / "claims"), (flotta_report, "config", lambda: ("https://admin.invalid", "box-tok"))):
            p = mock.patch.object(obj, name, val); p.start(); self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.dir / "xdg")}); p.start(); self.addCleanup(p.stop)

    def call(self, fn, op, incident="i1"):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = fn(SimpleNamespace(incident=incident, as_agent="gondnok"), op)
        return rc, out.getvalue()

    def test_atvetel_a_menedzser_tokenjevel_0600_fajl_titok_nelkuli_kimenet(self):
        op = Opener((200, {"incident": "i1", "target": "agent:munkas", "box": "alfa", "fence": 4, "claim": SECRET,
                           "attempt_until": "2026-11-08T10:30:00Z", "state": "atveve"}))
        rc, out = self.call(I.cmd_claim, op)
        self.assertEqual(rc, 0, out)
        self.assertEqual(op.calls[0]["url"], "https://admin.invalid/api/flotta/v1/incidents/i1/claim")
        self.assertEqual(op.calls[0]["headers"]["X-mentat-token"], TODO_TOK)     # nem a box tokenje
        c = I.load_claim("i1")
        self.assertEqual((c["fence"], c["claim"], c["target"]), (4, SECRET, "agent:munkas"))
        self.assertEqual(stat.S_IMODE(I.claim_path("i1").stat().st_mode), 0o600)
        self.assertNotIn(SECRET, out); self.assertNotIn(TODO_TOK, out)

    def test_elutasitott_atvetel_nem_ir_fajlt(self):
        rc, out = self.call(I.cmd_claim, Opener((409, {"code": "not_assignee"})))
        self.assertEqual(rc, 1); self.assertIn("not_assignee", out); self.assertIsNone(I.load_claim("i1"))

    def test_rossz_azonosito_nem_megy_ki(self):
        op = Opener()
        self.assertEqual(self.call(I.cmd_claim, op, incident="../x")[0], 2); self.assertEqual(op.calls, [])

    def test_visszaadas_fence_szel_es_torli_az_atvetelt(self):
        I.save_claim("i1", {"fence": 4, "claim": SECRET, "target": "agent:munkas"})
        op = Opener((200, {"state": "atadva"}))
        rc, out = self.call(I.cmd_release, op)
        self.assertEqual(rc, 0, out)
        self.assertEqual(op.calls[0]["body"], {"fence": 4, "claim": SECRET})
        self.assertIsNone(I.load_claim("i1"))


if __name__ == "__main__":
    unittest.main()
