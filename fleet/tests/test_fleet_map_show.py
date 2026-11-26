"""`fleet map show`: a flottatérkép ember által olvasható táblában — ágens, szerep (fő + extra),
gazda (az ember, akiben a jelentési lánc végződik), kinek jelent, repók, box (a registry
`host`-ja; a térkép sémája nem bővül), és alatta a felelősség. Csak olvas."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
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

from fleet import cli  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"


class Show(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.reg = self.d / "registry"
        shutil.copytree(EX, self.reg)
        self.old = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(self.reg)

    def tearDown(self):
        os.environ.pop("FLEET_REGISTRY", None) if self.old is None else os.environ.update(FLEET_REGISTRY=self.old)
        shutil.rmtree(self.d, ignore_errors=True)

    def show(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["map", "show", *args])
        return rc, out.getvalue()

    def row(self, out, agent):
        return next(ln for ln in out.splitlines() if ln.startswith(agent + " "))

    def test_the_example_map_as_a_table(self):
        rc, out = self.show()
        self.assertEqual(rc, 0, out)
        head = out.splitlines()[1]
        for col in ("ÁGENS", "SZEREP", "GAZDA", "JELENT", "BOX", "REPÓK"):
            self.assertIn(col, head)
        a = self.row(out, "demo-agent")
        for cell in ("flottamenedzser + asszisztens", "Példa Ede", "demo-box",
                     "example/demo-agent (owns)", "example/demo-helper (contributes)"):
            self.assertIn(cell, a)
        h = self.row(out, "demo-helper")
        for cell in ("segéd + jegyzetelő", "Példa Ede", "demo-agent", "demo-box"):
            self.assertIn(cell, h)
        self.assertIn("A példaflotta felügyelete", out)   # a felelősség, a sor alatt
        self.assertIn("Példa Ede", out.splitlines()[0])   # fejléc: gazda és flottamenedzser

    def test_columns_line_up(self):
        _, out = self.show()
        lines = out.splitlines()
        head, rows = lines[1], [self.row(out, "demo-agent"), self.row(out, "demo-helper")]
        for col in ("SZEREP", "GAZDA", "JELENT", "BOX"):
            self.assertTrue(all(r[head.index(col) - 1] == " " for r in rows), col)

    def test_an_agent_missing_from_the_registry_has_no_box(self):
        agents = json.loads((self.reg / "agents.json").read_text())
        (self.reg / "agents.json").write_text(json.dumps([a for a in agents if a["agent"] != "demo-helper"]))
        rc, out = self.show()
        self.assertEqual(rc, 0, out)
        self.assertIn(" — ", self.row(out, "demo-helper"))

    def test_json_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.reg.iterdir() if p.is_file()}
        rc, out = self.show("--json")
        self.assertEqual(rc, 0)
        rows = {r["agent"]: r for r in json.loads(out)["agents"]}
        self.assertEqual(rows["demo-helper"]["owner"], "Példa Ede")
        self.assertEqual(rows["demo-helper"]["box"], "demo-box")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.reg.iterdir() if p.is_file()})

    def test_a_missing_map_is_exit_2(self):
        (self.reg / "fleet-map.json").unlink()
        self.assertEqual(self.show()[0], 2)


if __name__ == "__main__":
    unittest.main()
