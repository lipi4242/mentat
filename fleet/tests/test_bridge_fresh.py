"""#35: a doctor jelzi, ha a futó híd régebbi a telepített fájljainál."""
from __future__ import annotations
import _hermetic  # noqa: F401
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleet import bridge_fresh  # noqa: E402


class R:
    def __init__(self, out): self.stdout = out


class TestBridgeFresh(unittest.TestCase):
    def test_process_older_than_files_is_a_problem(self):
        self.assertIn("régebbi", bridge_fresh.verdict(1000.0, 1010.0))

    def test_fresh_or_unmeasurable_is_none(self):
        self.assertIsNone(bridge_fresh.verdict(1011.0, 1010.0))
        self.assertIsNone(bridge_fresh.verdict(1009.0, 1010.0))   # 2 s-on belül
        self.assertIsNone(bridge_fresh.verdict(None, 1010.0))
        self.assertIsNone(bridge_fresh.verdict(1000.0, None))

    def test_problem_names_the_unit(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "bridge.mjs"
            f.write_text("x")
            os.utime(f, (5000, 5000))
            run = lambda *a, **k: R("42\n")
            p = bridge_fresh.problem("x-telegram-bridge.service", Path(d),
                                     [{"pid": 42, "started_s": 4000}], run=run)
            self.assertIn("x-telegram-bridge.service", p)
            self.assertIsNone(bridge_fresh.problem("x-telegram-bridge.service", Path(d),
                                                   [{"pid": 42, "started_s": 6000}], run=run))
            self.assertIsNone(bridge_fresh.problem("x", Path(d), [], run=lambda *a, **k: R("0\n")))


if __name__ == "__main__":
    unittest.main()
