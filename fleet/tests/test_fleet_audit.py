"""`fleet map audit`: minden ellenőrzésre egy szándékos hiba, a cache és az idempotens todo."""
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

from fleet import audit, audit_todo, cli, fleet_map  # noqa: E402
from fleet.audit_cli import cmd_audit  # noqa: E402
from fleet.registry import load_agents  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"
SELF = "<!-- mentat:managed:start self-image -->\nkép\n<!-- mentat:managed:end self-image -->\n"


class FakeSink:
    def __init__(self):
        self.store, self.calls = {}, 0

    def emit(self, key, title, description):
        self.calls += 1
        self.store.setdefault(key, (title, description))


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.reg = self.home / "reg"
        shutil.copytree(EX, self.reg)
        agents = json.loads((EX / "agents.json").read_text())
        for a in agents:
            a["workdir"] = str(self.home / "ws" / a["agent"])
            (self.home / "ws" / a["agent"]).mkdir(parents=True)
            (self.home / "ws" / a["agent"] / "AGENTS.md").write_text("# x\n" + SELF)
        (self.reg / "agents.json").write_text(json.dumps(agents))
        self.old = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(self.reg)
        for n in ("demo-agent", "demo-helper"):
            self.assertEqual(self.main("map", "render", n, "--repo", str(self.ws(n))), 0)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("FLEET_REGISTRY", None)
        else:
            os.environ["FLEET_REGISTRY"] = self.old
        shutil.rmtree(self.home, ignore_errors=True)

    def ws(self, n):
        return self.home / "ws" / n

    def main(self, *a):
        with redirect_stdout(io.StringIO()):
            return cli.main(list(a))

    def fmap(self):
        return json.loads((self.reg / "fleet-map.json").read_text())

    def setmap(self, m):
        (self.reg / "fleet-map.json").write_text(json.dumps(m))

    def codes(self, **kw):
        units = audit.collect(self.fmap(), load_agents(self.reg / "agents.json"), self.reg, home=self.home, **kw)
        return sorted(f.code for _, m in units.values() for f in m() if f.severity == "error")


class Checks(Base):
    def test_clean(self):
        self.assertEqual(self.codes(), [])

    def test_1_schema(self):
        m = self.fmap(); m["agents"]["demo-agent"]["lang"] = "de"; self.setmap(m)
        self.assertIn("bad-field", self.codes())

    def test_2_map_vs_agents(self):
        m = self.fmap(); m["agents"]["ghost"] = copy.deepcopy(m["agents"]["demo-helper"]); m["agents"]["ghost"]["repos"] = []; self.setmap(m)
        self.assertIn("unknown-agent", self.codes())

    def test_3_missing_block(self):
        (self.ws("demo-agent") / "AGENTS.md").write_text("# x\n" + SELF)
        self.assertEqual(self.codes(), ["block-missing"])

    def test_3_order(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        t = p.read_text()
        p.write_text(t.replace(SELF, "") + SELF)
        self.assertEqual(self.codes(), ["block-order"])

    def test_3_size(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        p.write_text(p.read_text().replace("Otthon:", "x" * 700 + "\nOtthon:"))
        self.assertIn("block-size", self.codes())

    def test_3_drift_on_map_change_and_hand_edit(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        p.write_text(p.read_text().replace("Riport:", "Riport: kézzel"))
        self.assertEqual(self.codes(), ["block-drift"])
        self.main("map", "render", "demo-agent", "--repo", str(self.ws("demo-agent")))
        m = self.fmap(); m["agents"]["demo-agent"]["reports_to"] = "human:Más"; self.setmap(m)
        self.assertEqual(self.codes(), ["block-drift"])

    def test_4_dead_link(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        p.write_text(p.read_text().replace("kép\n", "kép [szerep](szerepek/nincs.md)\n"))
        self.assertEqual(self.codes(), ["dead-link"])
        (self.ws("demo-agent") / "szerepek").mkdir()
        (self.ws("demo-agent") / "szerepek" / "nincs.md").write_text("x")
        self.assertEqual(self.codes(), [])

    def test_5_root(self):
        root = self.home / "root"
        (root / ".claude" / "rules").mkdir(parents=True)
        self.assertEqual(self.codes(root=root), ["root-missing"])
        self.assertEqual(self.main("map", "render", "--root", "--repo", str(root)), 0)
        self.assertEqual(self.codes(root=root), [])
        (root / "CLAUDE.md").write_text((root / "CLAUDE.md").read_text() + "Saját szabály.\n")
        self.assertEqual(self.codes(root=root), ["root-foreign-content"])
        self.main("map", "render", "--root", "--repo", str(root))
        (root / ".claude" / "rules" / "x.md").write_text("szabály")
        self.assertEqual(self.codes(root=root), ["root-rules-foreign"])

    def test_6_mac_home(self):
        self.assertEqual(self.codes(mac_home=True), [])
        (self.home / "ws" / "CLAUDE.md").write_text("kóbor")
        (self.home / ".claude" / "rules").mkdir(parents=True)
        c = self.codes(mac_home=True)
        self.assertIn("stray-parent-claude", c)
        self.assertIn("stray-parent-rules", c)

    def test_not_measurable_is_info_not_error(self):
        shutil.rmtree(self.ws("demo-helper"))
        self.assertEqual(self.codes(), [])
        units = audit.collect(self.fmap(), load_agents(self.reg / "agents.json"), self.reg, home=self.home)
        self.assertEqual([f.severity for f in units["agent:demo-helper"][1]()], ["info"])


class CliAndTodo(Base):
    def run_audit(self, *extra, sink=None):
        ns = cli.build_parser().parse_args(["map", "audit", "--state", str(self.home / "st.json"), "--json", *extra])
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_audit(ns, sink)
        return rc, json.loads(out.getvalue())

    def test_existing_error_is_replayed_as_cached_with_exit_1(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        p.write_text("# x\n" + SELF)
        rc, out = self.run_audit()
        self.assertEqual((rc, [(f["code"], f["cached"]) for f in out["findings"]]), (1, [("block-missing", False)]))
        rc, out = self.run_audit()
        self.assertEqual((rc, [(f["code"], f["cached"]) for f in out["findings"]]), (1, [("block-missing", True)]))

    def test_fix_makes_finding_disappear(self):
        p = self.ws("demo-agent") / "AGENTS.md"
        good = p.read_text()
        p.write_text("# x\n" + SELF)
        self.assertEqual(self.run_audit()[0], 1)
        p.write_text(good)
        rc, out = self.run_audit()
        self.assertEqual((rc, out["findings"]), (0, []))

    def test_unchanged_unit_is_not_remeasured(self):
        from unittest import mock
        (self.ws("demo-agent") / "AGENTS.md").write_text("# x\n" + SELF)
        self.run_audit()
        with mock.patch("fleet.audit_blocks.check_repo", side_effect=AssertionError("újramérve")) as m:
            rc, out = self.run_audit()
        self.assertEqual((rc, m.call_count, out["measured_units"]), (1, 0, 0))
        with mock.patch("fleet.audit_blocks.check_repo", return_value=[]) as m:
            self.run_audit("--no-cache")
        self.assertEqual(m.call_count, 2)

    def test_todo_second_run_does_not_duplicate(self):
        (self.ws("demo-agent") / "AGENTS.md").write_text("# x\n" + SELF)
        sink = FakeSink()
        self.run_audit("--todo", "--no-cache", sink=sink)
        keys = set(sink.store)
        self.assertEqual(len(keys), 1)
        self.run_audit("--todo", "--no-cache", sink=sink)
        self.assertEqual(set(sink.store), keys)
        self.assertEqual(sink.calls, 2)  # az idem-kulcs ugyanaz: a sink egy tételt tart
        self.run_audit("--todo", sink=sink)  # cache-sel: az első futás már rögzítette
        self.assertEqual(set(sink.store), keys)

    def test_todo_only_for_errors(self):
        sink = FakeSink()
        self.run_audit("--todo", sink=sink)
        self.assertEqual(sink.store, {})

    def test_exit_2_without_map(self):
        (self.reg / "fleet-map.json").unlink()
        ns = cli.build_parser().parse_args(["map", "audit", "--state", str(self.home / "s.json")])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cmd_audit(ns), 2)

    def test_stable_key(self):
        f = fleet_map.Finding("block-missing", "m", agent="a", subject="/p")
        self.assertEqual(audit_todo.stable_key(f), audit_todo.stable_key(fleet_map.Finding("block-missing", "más szöveg", agent="a", subject="/p")))


if __name__ == "__main__":
    unittest.main()
