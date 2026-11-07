"""Run the bekotes tests (../bekotes/test_*.py) as part of this directory's gate.

    python3 -m unittest discover -s release/reference/manifest
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import importlib
import pathlib
import sys
import unittest

BEKOTES = pathlib.Path(__file__).resolve().parent.parent / "bekotes"


def load_tests(loader, tests, pattern):
    if str(BEKOTES) not in sys.path:
        sys.path.insert(0, str(BEKOTES))
    suite = unittest.TestSuite()
    for path in sorted(BEKOTES.glob("test_*.py")):
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(path.stem)))
    return suite
