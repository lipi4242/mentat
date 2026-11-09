"""a beépített kiadó-előellenőrző mockolt GitHubbal és todóval — HTTP-hívásszám, nincs LLM-út,
a meglévő konfigurációból olvas, hálózati hiba nem dob."""
import _hermetic  # noqa: F401
import io
import json
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from fleet import precheck_release as pr
from fleet import tick_gate as tg

NOW = datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc).timestamp()


class Fake:
    """`gh` (subprocess) + todo (urlopen) egy helyen; minden hívást számol."""

    def __init__(self, prs=(), events=(), gh_code=0, gh_doc=None, todo_fail=False):
        self.calls, self.prs, self.events = [], list(prs), list(events)
        self.gh_code, self.gh_doc, self.todo_fail = gh_code, gh_doc, todo_fail

    def run(self, argv, **kw):
        self.calls.append(("run", argv[0], argv[1:3]))
        doc = self.gh_doc or {"data": {"search": {"issueCount": len(self.prs), "nodes": self.prs}}}
        return subprocess.CompletedProcess(argv, self.gh_code, json.dumps(doc), "")

    def open(self, req, timeout=None):
        self.calls.append(("http", req.full_url.split("?")[0].rsplit("/", 1)[-1]))
        assert req.headers.get("X-mentat-token") == "tok"
        if self.todo_fail:
            raise urllib.error.URLError("le")
        body = {"id": "p_kiado"} if req.full_url.endswith("/me") else self.events
        return io.BytesIO(json.dumps(body).encode())


def pr_node(n, head="h1"):
    return {"number": n, "isDraft": False, "headRefOid": head, "repository": {"nameWithOwner": "acme/a"},
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]}}


class Precheck(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.home, True)
        cfgdir = self.home / ".config"
        (cfgdir / "todo").mkdir(parents=True)
        (cfgdir / "todo" / "env").write_text("TODO_API=https://todo.example/api/todo/v1\n")
        (cfgdir / "todo" / "kiado.token").write_text("tok\n")
        (cfgdir / "kiado").mkdir()
        (cfgdir / "kiado" / "repos.json").write_text(json.dumps({"repos": [{"slug": "acme/a", "workdir": "~/w/a",
                                                                           "default_branch": "main"}, {"slug": "acme/b"}]}))
        self.cfg = tg.config({"agent": "kiado", "tick_gate": {"tick_cmd": "python3 entry.py --trigger hourly",
                              "release": {"repos_file": "~/.config/kiado/repos.json", "todo_handle": "kiado",
                                          "state_file": "%h/.config/kiado/state.json"}}})

    def observe(self, fake, gate=None, last=NOW - 60):
        import os
        old = os.environ.pop("TODO_API", None)
        try:
            return pr.observe(self.cfg, gate or {}, now=NOW, last_tick_at=last, home=self.home,
                              run=fake.run, opener=fake.open)
        finally:
            if old:
                os.environ["TODO_API"] = old

    def test_ures_ellenorzes_koltsege_es_nincs_llm_ut(self):
        f = Fake()
        t0 = time.monotonic()
        o = self.observe(f, gate={"todo_me": "p_kiado", "todo_seq": 7})
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual((o["reasons"], o["error"], o["activity"]), ([], None, False))
        self.assertEqual([c[0] for c in f.calls], ["run", "http"])          # 1 GitHub + 1 todo
        self.assertEqual(f.calls[0][1:], ("gh", ["api", "graphql"]))         # az egyetlen subprocess a gh
        self.assertNotIn("claude", json.dumps(f.calls))

    def test_elso_futas_me_egyszer_es_a_kurzor_ebresztes_nelkul_a_vegere_all(self):
        f = Fake(events=[{"seq": 41, "actor_id": "p_dev"}, {"seq": 42, "actor_id": "p_dev"}])
        o = self.observe(f)
        self.assertEqual([c for c in f.calls if c[0] == "http"], [("http", "me"), ("http", "changes")])
        self.assertEqual((o["commit"]["todo_me"], o["commit"]["todo_seq"], o["reasons"]), ("p_kiado", 42, []))

    def test_a_meglevo_repos_jsonbol_olvas(self):
        self.assertEqual(pr.repos(self.cfg["release"], self.home), ["acme/a", "acme/b"])
        self.assertIn("repo:acme/a repo:acme/b", pr.search_query(["acme/a", "acme/b"]))
        self.assertIn("label:release:queue", pr.search_query(["x/y"]))
        self.assertEqual(pr.repos({"repos": ["Acme/Mono"]}, self.home), ["acme/mono"])

    def test_uj_pr_munka_majd_valtozatlan_nem(self):
        f = Fake(prs=[pr_node(3)])
        o = self.observe(f, gate={"todo_me": "p_kiado", "todo_seq": 0})
        self.assertEqual(o["reasons"], ["új/változott PR: acme/a#3@h1:SUCCESS:-"])
        o2 = self.observe(Fake(prs=[pr_node(3)]), gate={"todo_me": "p_kiado", "seen": o["commit"]["seen"]})
        self.assertEqual((o2["reasons"], o2["activity"]), ([], True))      # vár, de nem ébreszt

    def test_idegen_todo_esemeny_munka_sajat_nem(self):
        ev = [{"seq": 9, "actor_id": "p_kiado"}, {"seq": 10, "actor_id": "p_dev"}]
        o = self.observe(Fake(events=ev), gate={"todo_me": "p_kiado", "todo_seq": 8})
        self.assertEqual(o["reasons"], ["todo-esemény: 1 db"])
        self.assertEqual(o["commit"]["todo_seq"], 10)
        o2 = self.observe(Fake(events=ev[:1]), gate={"todo_me": "p_kiado", "todo_seq": 8})
        self.assertEqual(o2["reasons"], [])

    def test_halozati_hiba_nem_dob_hanem_error(self):
        o = self.observe(Fake(gh_code=1, todo_fail=True), gate={"todo_me": "p_kiado"})
        self.assertIn("github", o["error"]); self.assertIn("todo", o["error"])
        self.assertNotIn("seen", o["commit"])                                # hiba nem írja felül a látottat

    def test_graphql_reszleges_valasz_hiba(self):
        o = self.observe(Fake(gh_doc={"errors": [{"message": "x"}], "data": {"search": {"nodes": []}}}),
                         gate={"todo_me": "p_kiado"})
        self.assertIn("GraphQL-hiba", o["error"])

    def test_csonka_kereses_hiba(self):
        o = self.observe(Fake(gh_doc={"data": {"search": {"issueCount": 101, "nodes": []}}}), gate={"todo_me": "p_kiado"})
        self.assertIn("100", o["error"])

    def test_lease_foglalt_es_lejaro_jegy_egyszer(self):
        (self.home / ".config" / "kiado" / "state.json").write_text(json.dumps({
            "lease": {"renewed_at": "2026-11-08T13:55:00Z"},
            "repos": {"acme/a": {"approvals": {"4": {"requested_at": "2026-11-07T03:00:00Z"}}}}}))
        o = self.observe(Fake(), gate={"todo_me": "p_kiado"})
        self.assertIn("lease", o["busy"])
        self.assertEqual(o["reasons"], ["lejáró 👍-jegy: acme/a#4"])
        o2 = self.observe(Fake(), gate={"todo_me": "p_kiado", "exp_seen": o["commit"]["exp_seen"]})
        self.assertEqual(o2["reasons"], [])                                  # ugyanarra a kérdésre egyszer


if __name__ == "__main__":
    unittest.main()
