"""A flottatérkép-séma és a `fleet map validate`. Minden szabályra egy
szándékos hiba, megnevezett lelettel; a validálás nem ír."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import cli, fleet_map  # noqa: E402
from fleet.registry import load_agents  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"
GOOD = json.loads((EX / "fleet-map.json").read_text())
AGENTS = load_agents(EX / "agents.json")


def codes(fmap, agents=AGENTS):
    return sorted(f.code for f in fleet_map.validate(fmap, agents))


def mut(fn):
    m = copy.deepcopy(GOOD)
    fn(m)
    return m


class Rules(unittest.TestCase):
    def test_example_is_green(self):
        self.assertEqual(codes(GOOD), [])

    def test_1_unknown_agent(self):
        self.assertEqual(codes(mut(lambda m: m["agents"].update(ghost=dict(m["agents"]["demo-helper"], repos=[])))), ["unknown-agent"])

    def test_2_active_missing_is_error_dormant_is_warning(self):
        fs = fleet_map.validate(mut(lambda m: m["agents"].pop("demo-agent")), AGENTS)
        self.assertIn(("missing-active-agent", "error"), [(f.code, f.severity) for f in fs])
        fs = fleet_map.validate(mut(lambda m: m["agents"].pop("demo-helper")), AGENTS)
        self.assertIn(("missing-dormant-agent", "warning"), [(f.code, f.severity) for f in fs])
        self.assertFalse([f for f in fs if f.severity == "error" and f.code.startswith("missing")])

    def test_3_cycle_and_non_human_end(self):
        def cyc(m):
            m["agents"]["demo-agent"]["reports_to"] = "demo-helper"
        self.assertEqual(codes(mut(cyc)), ["reports-cycle"])

        def dead(m):
            m["agents"]["demo-helper"]["reports_to"] = "nobody"
        self.assertEqual(codes(mut(dead)), ["reports-not-human"])

    def test_4_repo_owners(self):
        def none(m):
            m["agents"]["demo-agent"]["repos"][0]["mode"] = "contributes"
        self.assertEqual(codes(mut(none)), ["repo-no-owner"])

        def two(m):
            m["agents"]["demo-helper"]["repos"].append({"repo": "example/demo-agent", "mode": "owns"})
        self.assertEqual(codes(mut(two)), ["repo-multi-owner"])

        def paths(m):  # azonos repo, külön path: két külön gazda rendben van
            m["agents"]["demo-helper"]["repos"].append({"repo": "example/demo-agent", "path": "x", "mode": "owns"})
        self.assertEqual(codes(mut(paths)), [])

    def test_5_roles(self):
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(main_role="varazslo"))), ["unknown-role"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-helper"].pop("custom_role"))), ["custom-role-missing"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(extra_roles=["custom"]))), ["custom-role-missing"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(extra_roles=["pm", "xx"]))), ["unknown-role"])

    def test_6_missing_or_wrong_type(self):
        for key in ("responsibility", "reports_to", "talks_to", "repos", "home", "lang", "extra_roles", "main_role"):
            with self.subTest(key=key):
                self.assertIn("bad-field", codes(mut(lambda m: m["agents"]["demo-agent"].pop(key))))
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(responsibility=""))), ["bad-field"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(lang="de"))), ["bad-field"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"].update(repos="x"))), ["bad-field"])
        self.assertEqual(codes(mut(lambda m: m.pop("owner"))), ["bad-field"])
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"]["repos"][0].update(mode="rents"))), ["bad-field"])

    def test_7_dangling_refs(self):
        self.assertEqual(codes(mut(lambda m: m["agents"]["demo-agent"]["talks_to"][0].update(agent="ghost"))), ["dangling-ref"])
        self.assertEqual(codes(mut(lambda m: m.update(manager="ghost"))), ["dangling-ref"])


class Io(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        shutil.copytree(EX, self.d / "reg")
        self.reg = self.d / "reg"
        self.old = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(self.reg)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("FLEET_REGISTRY", None)
        else:
            os.environ["FLEET_REGISTRY"] = self.old
        shutil.rmtree(self.d, ignore_errors=True)

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["map", "validate", *args])
        return rc, out.getvalue()

    def test_validate_writes_nothing(self):
        def snap():
            return {str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                    for p in [self.reg, *self.reg.rglob("*")]}
        before = snap()
        self.run_cli()
        self.run_cli("--json")
        self.assertEqual(before, snap())

    def test_exit_codes(self):
        rc, out = self.run_cli()
        self.assertEqual(rc, 0, out)
        rc, out = self.run_cli("--json")
        self.assertEqual((rc, json.loads(out)["ok"]), (0, True))
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["agents"]["demo-agent"]["lang"] = "de"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        rc, out = self.run_cli("--json")
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(out)["findings"][0]["code"], "bad-field")
        (self.reg / "fleet-map.json").write_text("{nem json")
        self.assertEqual(self.run_cli()[0], 2)
        (self.reg / "fleet-map.json").unlink()
        self.assertEqual(self.run_cli()[0], 2)


if __name__ == "__main__":
    unittest.main()
