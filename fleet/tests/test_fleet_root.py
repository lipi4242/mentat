"""A semleges gyökér-CLAUDE.md generátora és a `fleet map render|check --root`."""
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
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import cli, fleet_root as fr  # noqa: E402

EX = Path(__file__).resolve().parents[1] / "examples" / "registry"
MAP = json.loads((EX / "fleet-map.json").read_text())


class Pure(unittest.TestCase):
    def test_under_ceiling_and_clean(self):
        for lang in (None, "en"):
            m = copy.deepcopy(MAP)
            if lang:
                m["lang"] = lang
            t = fr.render(m)
            self.assertLessEqual(len(t.encode()), 1024)
            self.assertEqual(fr.violations(t, m), [])
            self.assertFalse(re.search(r"(?i)\b(te vagy|you are|host|status|státusz|dormant)\b|\d{4}-\d\d-\d\d", t))

    def test_whole_file_is_one_block(self):
        t = fr.render(MAP)
        self.assertTrue(t.startswith("<!-- mentat:managed:start fleet-root -->\n<!-- fleet-root hash="))
        self.assertTrue(t.endswith("<!-- mentat:managed:end fleet-root -->\n"))
        self.assertEqual(t.count("mentat:managed"), 2)

    def test_over_ceiling_is_error_not_truncation(self):
        m = copy.deepcopy(MAP)
        for i in range(60):
            m["agents"][f"agent-{i:02d}"] = m["agents"]["demo-helper"]
        with self.assertRaises(fr.RootError):
            fr.render(m)

    def test_banned_content_detected(self):
        for bad in ("Te vagy a menedzser", "You are the manager", "host: box1", "2026-11-11", "status: active",
                    "demo-agent: mindig hívd a demo-helper-t"):
            self.assertTrue(fr.violations(bad, MAP), bad)

    def test_banned_content_from_map_blocks_render(self):
        m = copy.deepcopy(MAP)
        m["agents"]["demo-helper"]["custom_role"] = "You are boss"
        with self.assertRaises(fr.RootError):
            fr.render(m)

    def test_root_lines_present(self):
        from fleet import fleet_place
        t = fr.render(MAP)
        for line in fleet_place.root_lines(MAP, "hu"):
            self.assertIn(line, t)
        for n, e in MAP["agents"].items():
            self.assertIn(f"- {n} — ", t)


class Cli(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.reg = self.d / "reg"
        shutil.copytree(EX, self.reg)
        self.repo = self.d / "repo"
        self.repo.mkdir()
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
            rc = cli.main(["map", *a, "--root", "--repo", str(self.repo)])
        return rc, out.getvalue()

    def test_check_red_after_change_green_after_render(self):
        self.assertEqual(self.run_cli("check")[0], 1)  # nincs fájl még: nem zöld
        self.assertEqual(self.run_cli("render")[0], 0)
        self.assertEqual(self.run_cli("check")[0], 0)
        m = json.loads((self.reg / "fleet-map.json").read_text())
        m["owner"] = "Más Ember"
        (self.reg / "fleet-map.json").write_text(json.dumps(m))
        self.assertEqual(self.run_cli("check")[0], 1)
        self.assertEqual(self.run_cli("render")[0], 0)
        self.assertEqual(self.run_cli("check")[0], 0)

    def test_unchanged_render_does_not_write(self):
        self.run_cli("render")
        p = self.repo / "CLAUDE.md"
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
        self.assertEqual(self.run_cli("render")[0], 0)
        self.assertEqual(p.stat().st_mtime_ns, 1_000_000_000)

    def test_missing_map_is_2(self):
        (self.reg / "fleet-map.json").unlink()
        self.assertEqual(self.run_cli("render")[0], 2)

    def test_agent_without_root_still_needs_agent(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["map", "render", "--repo", str(self.repo)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
