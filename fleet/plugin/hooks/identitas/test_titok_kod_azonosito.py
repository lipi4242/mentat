"""Titok-kapu, értelmezőnek adott kód: az azonosító alakú literál (`owner_token`) mezőnév, nem fájl
(élő hiba, 2026-11-07: a heartbeat read/write a lease `owner_token` mezője miatt akadt el).
Futtatás: python3 -I -m unittest discover -s fleet/plugin/hooks/identitas -p 'test_titok_kod_azonosito.py' -q
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_titok_kapu import Base  # noqa: E402


class AzonositoNemFajl(Base):
    def test_heartbeat_kod_atmegy(self):
        for cmd in ('''python3 -c "from anytime_engine.heartbeat import read_heartbeat; print(read_heartbeat()['owner_token'])"''',
                    '''python3 -c "import json; d={'owner_token': 'x', 'api_key': None}; print(json.dumps(d))"''',
                    "python3 - <<'PY'\nhb = {'lease_token': 1}\nprint(hb['lease_token'])\nPY",
                    # szabad szöveg egy tételben (élő hiba, 11-07: item new heredocban)
                    "python3 - <<'PY'\nd = {'title': 'A Linear app-token kivezetése', 'ac': ['Kész, ha a régi api-key törölve']}\nPY"):
            self.assertIsNone(self.bash(cmd), cmd)

    def test_fajlnev_tovabbra_is_tilt(self):
        self.put("token", "x\n")      # azonosító alakú, de ilyen fájl VAN a cwd-ben
        for cmd in ('''python3 -c "print(open('token').read())"''',
                    '''python3 -c "print(open('szervezo.env').read())"''',
                    '''python3 -c "print(open('gh.token').read())"''',
                    '''python3 -c "print(open('.env').read())"''',
                    "python3 - <<'PY'\nopen('linear-app.token').read()\nPY"):
            self.assertTrue(self.bash(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
