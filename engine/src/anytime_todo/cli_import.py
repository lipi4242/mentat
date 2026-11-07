"""`import-linear EXPORT --map MAP [--dry-run]` — a thin dispatcher.

The import itself is `linear_import.py` (its own arguments and help). This
only hands the rest of the command line over, and says so plainly when that
module is not part of this copy of the pack.
"""
from __future__ import annotations

import importlib
import sys

NAME = "import-linear"
MODULE = (__package__ or "anytime_todo") + ".linear_import"


def run(argv: list[str]) -> int:
    try:
        mod = importlib.import_module(MODULE)
    except ModuleNotFoundError as e:
        if e.name != MODULE:          # a real import error inside the module: show it
            raise
        print(f"[anytime_todo] {NAME} is not in this copy of the pack ({MODULE} is missing): "
              "re-sync the engine with the todo pack", file=sys.stderr)
        return 2
    return mod.main(argv)
