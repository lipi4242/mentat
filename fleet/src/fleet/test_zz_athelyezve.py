"""Helyőrző: a src/fleet tesztjei a fleet/tests/ alá költöztek (11-08).

Csak azért van itt, mert a bin/gate `discover -s src/fleet` sora üres könyvtáron
exit 5-tel bukna. A bin/gate sor törlése (külön, kapu-recept sávos PR) után ez a fájl
is törlődik, és a fleet/tests/test_zz_tmp_clean.py őre üres listát vár.
"""
import unittest


class Athelyezve(unittest.TestCase):
    def test_only_this_placeholder_is_left(self):
        from pathlib import Path
        here = Path(__file__).resolve().parent
        self.assertEqual(sorted(p.name for p in here.glob("test_*.py")), [Path(__file__).name])


if __name__ == "__main__":
    unittest.main()
