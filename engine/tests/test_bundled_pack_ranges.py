"""Every bundled concern pack admits the engine it ships with.

A minor engine step (0.6 -> 0.7) is refused by a pack whose ANYTIME_PLUGIN range stops below it,
and bump.py does not move these ranges: this test is the red light for that release step. In an
agent's vendored selftest only the packs it chose are present; the others are skipped.
"""
import importlib
import importlib.util
import unittest

from anytime_engine import __version__, versions

PACKS = ("anytime_cases", "anytime_todo", "anytime_bekotes")


class BundledPackRanges(unittest.TestCase):
    def test_every_bundled_pack_admits_this_engine(self):
        present = [n for n in PACKS if importlib.util.find_spec(n) is not None]
        if not present:
            self.skipTest("no bundled pack is vendored here")
        for name in present:
            spec = importlib.import_module(name).ANYTIME_PLUGIN["engine"]
            with self.subTest(pack=name):
                self.assertTrue(versions.satisfies(__version__, spec),
                                f"{name} declares engine {spec}, the engine is {__version__}")


if __name__ == "__main__":
    unittest.main()
