#!/usr/bin/env python3
"""`import-linear`: the cli hands the command line to linear_import.main, and
says so plainly (exit 2) when that module is not in this copy of the pack.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _work_fixture import WorkCase  # noqa: E402

FAKE = "SEEN = []\n\ndef main(argv):\n    SEEN.append(argv)\n    return 7\n"


class TestDispatch(WorkCase):
    def plant(self, text: str) -> None:
        (self.root / "anytime_todo" / "linear_import.py").write_text(text)
        sys.modules.pop("anytime_todo.linear_import", None)

    def test_missing_module_is_a_plain_message(self):
        (self.root / "anytime_todo" / "linear_import.py").unlink(missing_ok=True)
        sys.modules.pop("anytime_todo.linear_import", None)
        rc, out = self.cli("import-linear", "export.json", "--map", "map.json")
        self.assertEqual(rc, 2)
        self.assertIn("not in this copy of the pack", out)
        self.assertEqual(self.srv.calls, [])

    def test_the_rest_of_the_line_is_handed_over(self):
        self.plant(FAKE)
        rc, _ = self.cli("import-linear", "export.json", "--map", "map.json", "--dry-run")
        self.assertEqual(rc, 7)
        self.assertEqual(sys.modules["anytime_todo.linear_import"].SEEN,
                         [["export.json", "--map", "map.json", "--dry-run"]])

    def test_a_broken_module_is_not_hidden(self):
        self.plant("import anytime_todo_no_such_dependency\n")
        with self.assertRaises(ModuleNotFoundError):
            self.mod("cli_import").run([])


if __name__ == "__main__":
    unittest.main()
