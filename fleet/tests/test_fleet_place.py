"""A fleet-place blokk és a `fleet map render|check`."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import cli, fleet_place as fp  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"
MAP = json.loads((EX / "fleet-map.json").read_text())
SELF_IMAGE = "<!-- mentat:managed:start self-image -->\nkép\n<!-- mentat:managed:end self-image -->\n"


class Pure(unittest.TestCase):
    def test_size_limits_both_modes(self):
        for agent in MAP["agents"]:
            self.assertLessEqual(len(fp.body(MAP, agent, "inherited").encode()), 300)
            self.assertLessEqual(len(fp.body(MAP, agent, "standalone").encode()), 600)

    def test_over_limit_is_refused(self):
        m = copy.deepcopy(MAP)
        m["agents"]["demo-agent"]["repos"] = [{"repo": f"example/long-repository-name-{i}", "mode": "owns"} for i in range(20)]
        for mode in ("inherited", "standalone"):
            with self.assertRaises(fp.TooBig):
                fp.body(m, "demo-agent", mode)

    def test_no_host_status_date(self):
        m = copy.deepcopy(MAP)
        e = m["agents"]["demo-agent"]
        e.update(host="box9", status="dormant", updated="2026-11-11")
        for mode in fp.MODES:
            t = fp.body(m, "demo-agent", mode)
            self.assertFalse(re.search(r"box9|dormant|active|\d{4}-\d\d-\d\d", t), t)

    def test_talks_cap_five(self):
        m = copy.deepcopy(MAP)
        m["agents"]["demo-agent"]["talks_to"] = [{"agent": "demo-helper", "about": f"t{i}"} for i in range(8)]
        t = fp.body(m, "demo-agent", "standalone")
        line = [l for l in t.splitlines() if l.startswith("Beszél")][0]
        self.assertEqual(line.count("demo-helper ("), 5)
        self.assertIn("+3 további: /fleet:roster", t)

    def test_inherited_plus_root_equals_standalone(self):
        for agent, e in MAP["agents"].items():
            inh = set(fp.body_lines(MAP, agent, "inherited")) | set(fp.root_lines(MAP, e["lang"]))
            self.assertEqual(inh, set(fp.body_lines(MAP, agent, "standalone")))

    def test_lang(self):
        self.assertIn("Otthon:", fp.body(MAP, "demo-agent", "standalone"))
        self.assertIn("Home:", fp.body(MAP, "demo-helper", "standalone"))


class Cli(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.reg = self.d / "reg"
        shutil.copytree(EX, self.reg)
        self.repo = self.d / "repo"
        self.repo.mkdir()
        (self.repo / "AGENTS.md").write_text("# Ágens\n" + SELF_IMAGE + "\nTöbbi\n")
        self.old = os.environ.get("FLEET_REGISTRY")
        os.environ["FLEET_REGISTRY"] = str(self.reg)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("FLEET_REGISTRY", None)
        else:
            os.environ["FLEET_REGISTRY"] = self.old
        shutil.rmtree(self.d, ignore_errors=True)

    def run_cli(self, *a):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["map", *a, "--repo", str(self.repo)])
        return rc, out.getvalue()

    def text(self):
        return (self.repo / "AGENTS.md").read_text()

    def test_block_after_self_image(self):
        for mode in ("standalone", "inherited"):
            self.assertEqual(self.run_cli("render", "demo-agent", "--mode", mode)[0], 0)
            t = self.text()
            self.assertIn(SELF_IMAGE + "<!-- mentat:managed:start fleet-place -->\n<!-- fleet-place agent=demo-agent", t)
            self.assertEqual(t.count("mentat:managed:start fleet-place"), 1)
            self.assertTrue(t.endswith("Többi\n"))

    def test_brain_regex_finds_block(self):
        # a kiadott brain-eszköz mintája (brain/release/reference/bekotes/blokk.py, _rx)
        bid = "fleet-place"
        rx = re.compile(r"<!-- mentat:managed:start %s -->.*?<!-- mentat:managed:end %s -->\n?"
                        % (re.escape(bid), re.escape(bid)), re.S)
        self.run_cli("render", "demo-agent")
        m = rx.search(self.text())
        self.assertTrue(m)
        self.assertEqual(len(rx.findall(self.text())), 1)
        self.assertIn("Otthon:", m.group(0))

    def test_without_self_image_goes_first(self):
        (self.repo / "AGENTS.md").write_text("# Ágens\n")
        self.run_cli("render", "demo-agent")
        self.assertTrue(self.text().startswith("<!-- mentat:managed:start fleet-place"))

    def test_unchanged_render_does_not_touch_file(self):
        self.run_cli("render", "demo-agent")
        p = self.repo / "AGENTS.md"
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
        before = p.stat().st_mtime_ns
        rc, out = self.run_cli("render", "demo-agent")
        self.assertEqual((rc, p.stat().st_mtime_ns), (0, before))

    def test_check_red_after_map_change_green_after_render(self):
        self.run_cli("render", "demo-agent")
        self.assertEqual(self.run_cli("check")[0], 0)
        self.assertEqual(self.run_cli("check", "demo-agent")[0], 0)
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["agents"]["demo-agent"]["reports_to"] = "human:Más Ember"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        rc, out = self.run_cli("check", "demo-agent")
        self.assertEqual(rc, 1)
        self.assertIn("demo-agent", out)
        self.run_cli("render", "demo-agent")
        self.assertEqual(self.run_cli("check", "demo-agent")[0], 0)

    def test_check_no_block_and_missing_map(self):
        self.assertEqual(self.run_cli("check", "demo-agent")[0], 1)
        (self.reg / "fleet-map.json").unlink()
        self.assertEqual(self.run_cli("check", "demo-agent")[0], 2)

    def test_render_refuses_invalid_map(self):
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["agents"]["demo-agent"]["lang"] = "de"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        before = self.text()
        self.assertEqual(self.run_cli("render", "demo-agent")[0], 1)
        self.assertEqual(self.text(), before)


if __name__ == "__main__":
    unittest.main()
