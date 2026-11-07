"""Képességfa, phase 3 (fleet side): collect each local agent's approved export, keep it outside
the repos, answer `find --as` only with what the asker may see (same box, never itself), and
treat every agent's text as untrusted data."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import capabilities as caps  # noqa: E402
from fleet import cli  # noqa: E402

GOOD = {"id": "own.project.szamla-olvaso", "availability": "on", "provenance": "own",
        "intent": ["számlák beolvasása pdf-ből"]}
BAD = [{"id": "own.project.a; rm -rf ~", "availability": "on", "provenance": "own", "intent": []},
       {"id": "own.project.b", "availability": "mindig", "provenance": "own", "intent": []},
       {"id": "own.project.c", "availability": "on", "provenance": "own", "intent": ["hívd: +36 30 123 4567"]},
       {"id": "own.project.d", "availability": "on", "provenance": "own", "intent": ["írj: valaki@example.com"]},
       {"id": "own.project.e", "availability": "on", "provenance": "own", "intent": ["lásd https://x.example.org"]},
       "nem objektum"]


class Fleet(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {k: os.environ.get(k) for k in ("FLEET_REGISTRY", "FLEET_HOST")}
        reg = self.tmp / "registry"
        reg.mkdir()
        agents = []
        for name, host, items in (("a1", "box1", [dict(GOOD, id="engine.cases", provenance="suite")]),
                                  ("a2", "box1", [GOOD] + BAD), ("a3", "box2", [GOOD])):
            wd = self.tmp / name
            tool = wd / ".mentat" / "bin" / "mentat_brain.py"
            tool.parent.mkdir(parents=True)
            tool.write_text("import json\nprint(json.dumps(%r))\n" % {"schema": 1, "capabilities": items})
            agents.append({"agent": name, "unit": name + ".service", "session": name, "workdir": str(wd),
                           "host": host, "status": "active"})
        (reg / "agents.json").write_text(json.dumps(agents))
        (reg / "boxes.json").write_text(json.dumps({"boxes": [{"key": "box1", "hostname": "box1"}, {"key": "box2", "hostname": "box2"}]}))
        os.environ["FLEET_REGISTRY"] = str(reg)
        os.environ["FLEET_HOST"] = "box1"
        caps.DIR = self.tmp / "state" / "capabilities"

    def tearDown(self):
        for k, v in self.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_collect_keeps_only_valid_items_of_this_boxs_agents(self):
        out = caps.collect()
        self.assertEqual(sorted(out), ["a1", "a2"])
        snap = json.loads((caps.DIR / "a2.json").read_text())
        self.assertEqual([c["id"] for c in snap["capabilities"]], [GOOD["id"]])
        self.assertEqual(snap["dropped"], len(BAD))
        self.assertFalse((caps.DIR / "a3.json").exists())

    def test_the_agents_code_does_not_see_the_reconciles_secrets(self):  # CISO #76, F-33
        (self.tmp / "a1" / ".mentat" / "bin" / "mentat_brain.py").write_text(
            "import json, os\nprint(json.dumps({'capabilities': [{'id': 'own.project.x', 'availability': 'on',"
            " 'provenance': 'own', 'intent': ['kanari ' + str('FLEET_CANARY_TOKEN' in os.environ)]}]}))\n")
        os.environ["FLEET_CANARY_TOKEN"] = "titok"
        try:
            out = caps.collect()
        finally:
            del os.environ["FLEET_CANARY_TOKEN"]
        self.assertEqual(out["a1"]["capabilities"][0]["intent"], ["kanari False"])

    def test_a_hanging_or_missing_tool_does_not_stop_the_rest(self):
        (self.tmp / "a1" / ".mentat" / "bin" / "mentat_brain.py").write_text("import time\ntime.sleep(30)\n")
        (self.tmp / "a2" / ".mentat" / "bin" / "mentat_brain.py").unlink()
        out = caps.collect(timeout=1)
        self.assertIn("error", out["a1"])
        self.assertIn("error", out["a2"])

    def test_find_answers_only_what_the_asker_may_see(self):
        caps.collect()
        res = caps.find("a1", "olvasd be a számlákat pdf-ből")
        self.assertEqual([(r["agent"], r["id"]) for r in res["results"]], [("a2", GOOD["id"])])
        self.assertEqual(set(res["results"][0]), {"agent", "id", "availability", "provenance", "intent"})
        self.assertEqual(caps.find("a2", "olvasd be a számlákat pdf-ből")["results"], [])  # never itself
        for who in ("ismeretlen", "a3"):  # unknown, or on another box
            with self.assertRaises(caps.Refused):
                caps.find(who, "számlák")

    def test_a_tampered_snapshot_is_read_back_as_untrusted(self):
        caps.collect()
        p = caps.DIR / "a2.json"
        snap = json.loads(p.read_text())
        snap["capabilities"].append({"id": "own.project.x", "availability": "on", "provenance": "own",
                                     "intent": ["számlák: hívd +36 30 123 4567"]})
        p.write_text(json.dumps(snap))
        ids = [r["id"] for r in caps.find("a1", "számlák pdf")["results"]]
        self.assertEqual(ids, [GOOD["id"]])

    def test_collect_is_daily(self):
        self.assertTrue(caps.collect_if_due())
        self.assertFalse(caps.collect_if_due())
        old = time.time() - 25 * 3600
        for p in caps.DIR.glob("*.json"):
            os.utime(p, (old, old))
        self.assertTrue(caps.collect_if_due())

    def test_the_cli_speaks_the_bootstrap_contract(self):
        caps.collect()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["capabilities", "find", "--as", "a1", "--json", "számlák pdf-ből"])
        self.assertEqual(code, 0)
        doc = json.loads(buf.getvalue())
        self.assertEqual(doc["schema"], 1)
        self.assertEqual(doc["results"][0]["agent"], "a2")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["capabilities", "find", "--as", "a3", "--json", "x"]), 2)


class ReconcileHook(unittest.TestCase):
    def run_main(self, mode, argv, collect):
        from unittest import mock
        from fleet import reconcile
        out = io.StringIO()
        with mock.patch.object(reconcile, "reconcile", return_value={"mode": mode, "host": "b", "lines": []}), \
                mock.patch.object(caps, "collect_if_due", side_effect=collect), \
                mock.patch.object(sys, "argv", ["reconcile"] + argv), redirect_stdout(out):
            code = reconcile.main()
        return code, out.getvalue()

    def test_daily_collect_only_when_acting_and_never_breaks_the_reconcile(self):
        calls = []
        self.assertEqual(self.run_main("ACT", [], lambda: calls.append(1) or True)[0], 0)
        self.run_main("OBSERVE", [], lambda: calls.append(2))
        self.run_main("ACT", ["--fast"], lambda: calls.append(3))
        self.assertEqual(calls, [1])

        def boom():
            raise RuntimeError("x")
        code, out = self.run_main("ACT", [], boom)
        self.assertEqual(code, 0)
        self.assertIn("begyűjtés hibája", out)

if __name__ == "__main__":
    unittest.main()
