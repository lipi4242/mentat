"""flotta-menedzser: a managers.json — validálás (a Workerrel azonos szabály), a lánc előnézete (elsőbbség,
rang, döntetlen név szerint, egy handle egyszer), és a kiadás: külön config-tokennel, a token sehol
nem látszik, az elavult verziót a Worker elutasítja, és ez érthetően kiíródik."""
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fleet import managers_cli as C, managers_file as M
from _flotta_fake import Opener

TOK = "mentat_HAMIS_config_token_0123456789abcdef"
DOC = {"schema": 1, "version": 3, "fleet": "default", "managers": [
    {"handle": "vezeto", "scope": "*", "rank": 1}, {"handle": "helyettes", "scope": "*", "rank": 2},
    {"handle": "alfa-gondnok", "scope": "box:alfa", "rank": 1}, {"handle": "b-ember", "scope": "*", "rank": 2},
    {"handle": "helyettes", "scope": "agent:munkas", "rank": 5}]}


class Validate(unittest.TestCase):
    def test_ervenyes_es_az_agent_alapbol_a_handle(self):
        norm, probs = M.validate(DOC)
        self.assertEqual(probs, [])
        self.assertEqual(norm["managers"][0], {"handle": "vezeto", "agent": "vezeto", "scope": "*", "rank": 1})

    def test_hibak(self):
        bad = {"schema": 2, "version": 0, "managers": [
            {"handle": "a", "scope": "alfa", "rank": 1}, {"handle": "a b", "scope": "*", "rank": True},
            {"handle": "x", "scope": "box:", "rank": 1}, {"handle": "y", "scope": "*", "rank": 1},
            {"handle": "y", "scope": "*", "rank": 2}], "extra": 1}
        _, probs = M.validate(bad)
        text = "\n".join(probs)
        for want in ("schema", "version", "managers[0].scope", "managers[1].handle", "managers[1].rank",
                     "managers[2].scope", "ismétlődő (handle, scope): y *", "ismeretlen mező: extra"):
            self.assertIn(want, text)

    def test_tul_hosszu_lista(self):
        _, probs = M.validate({"schema": 1, "version": 1, "managers": [{"handle": f"m{i}", "scope": "*", "rank": 1} for i in range(51)]})
        self.assertTrue(any("legfeljebb 50" in p for p in probs))


class Chain(unittest.TestCase):
    def test_elsobbseg_rang_dontetlen_es_dedupe(self):
        ms = M.validate(DOC)[0]["managers"]
        got = [(m["handle"], m["scope"]) for m in M.chain(ms, "munkas", "alfa")]
        # agent > box > *; a *-on belül rang, döntetlennél név (b-ember < helyettes); helyettes csak egyszer
        self.assertEqual(got, [("helyettes", "agent:munkas"), ("alfa-gondnok", "box:alfa"), ("vezeto", "*"), ("b-ember", "*")])

    def test_box_celnal_nincs_agent_hatokor(self):
        ms = M.validate(DOC)[0]["managers"]
        self.assertEqual([m["handle"] for m in M.chain(ms, None, "beta")], ["vezeto", "b-ember", "helyettes"])


class Publish(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.dir, True)
        self.file = self.dir / "managers.json"; self.file.write_text(json.dumps(DOC))
        p = mock.patch.object(C, "CONFIG_ENV", self.dir / "flotta-config.env"); p.start(); self.addCleanup(p.stop)

    def run_cli(self, opener, dry=False):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = C.cmd_publish(SimpleNamespace(file=str(self.file), dry_run=dry), opener)
        return rc, out.getvalue()

    def configure(self):
        (self.dir / "flotta-config.env").write_text(f"FLOTTA_URL=https://admin.invalid/\nFLOTTA_CONFIG_TOKEN={TOK}\n")

    def test_kiadas_a_config_tokennel_put_managers(self):
        self.configure()
        op = Opener((200, {"version": 3, "unchanged": False}))
        rc, out = self.run_cli(op)
        self.assertEqual(rc, 0, out); self.assertIn("v3 kiadva", out)
        c = op.calls[0]
        self.assertEqual((c["method"], c["url"]), ("PUT", "https://admin.invalid/api/flotta/v1/managers"))
        self.assertEqual(c["headers"]["X-mentat-token"], TOK)
        self.assertEqual(c["body"]["version"], 3); self.assertEqual(len(c["body"]["managers"]), 5)
        self.assertNotIn(TOK, out)

    def test_elavult_verzio_elutasitva(self):
        self.configure()
        rc, out = self.run_cli(Opener((409, {"error": "stale version", "code": "stale", "current": 4})))
        self.assertEqual(rc, 1); self.assertIn("elavult verzió (v3)", out); self.assertIn("v4", out)
        self.assertNotIn(TOK, out)

    def test_box_token_nem_ir_konfigot(self):
        self.configure()
        rc, out = self.run_cli(Opener((403, {"error": "forbidden"})))
        self.assertEqual(rc, 1); self.assertIn("flotta:config", out)

    def test_nem_elerheto_worker(self):
        self.configure()
        rc, out = self.run_cli(Opener((None, {})))
        self.assertEqual(rc, 1); self.assertIn("nem érhető el", out)

    def test_beallitas_nelkul_nem_kuld_dry_run_nem_kuld(self):
        op = Opener()
        self.assertEqual(self.run_cli(op)[0], 2)
        self.configure()
        rc, out = self.run_cli(op, dry=True)
        self.assertEqual((rc, op.calls), (0, [])); self.assertIn("semmi nem ment el", out)

    def test_hibas_fajl_nem_megy_ki(self):
        self.configure()
        self.file.write_text(json.dumps({**DOC, "version": "3"}))
        op = Opener()
        self.assertEqual(self.run_cli(op)[0], 2); self.assertEqual(op.calls, [])

    def test_validate_a_registry_mellett(self):
        rdir = self.dir / "registry"; rdir.mkdir()
        self.assertEqual(C.validate_problems(rdir), [])          # a managers.json a registry mellett: ép
        self.file.write_text("{")
        self.assertTrue(C.validate_problems(rdir)[0].startswith("managers.json:"))


if __name__ == "__main__":
    unittest.main()
