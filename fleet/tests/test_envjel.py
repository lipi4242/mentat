"""nemakad-jel a doctorban (CISO 10-24): ha a futó claude környezetéből hiányzik a
FLEET_AGENT/THUFIR_AGENT/MENTAT_HEADLESS, az probléma; olvashatatlan environ = nem mérhető;
az értékek (tokenek) soha nem kerülnek a jelentésbe. Production code: envjel, doctor.
"""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, envjel  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402
from test_hook_fail_open_n123 import KW  # noqa: E402

TOKEN = "sk-ant-oat01-TITKOS"


def fake_proc(pid, raw):
    d = Path(tempfile.mkdtemp())
    (d / str(pid)).mkdir()
    (d / str(pid) / "environ").write_bytes(raw)
    return d


class EnvJel(unittest.TestCase):
    def test_nevek_ertek_nelkul(self):
        raw = b"PATH=/bin\0CLAUDE_CODE_OAUTH_TOKEN=" + TOKEN.encode() + b"\0FLEET_AGENT=rili\0URES=\0\xff\xfe=x\0"
        names = envjel.env_names(raw)
        self.assertIn("FLEET_AGENT", names)
        self.assertNotIn("URES", names)  # üres érték nem jel
        self.assertFalse(any(TOKEN in n for n in names))

    def test_itelet(self):
        for jel in envjel.JELEK:
            self.assertEqual(envjel.verdict({"PATH", jel}), (None, None), jel)
        prob, unk = envjel.verdict({"PATH", "CLAUDE_CODE_OAUTH_TOKEN"})
        self.assertIn("MENTAT_HEADLESS=1", prob)
        self.assertIsNone(unk)
        self.assertEqual(envjel.verdict(None)[0], None)
        self.assertIn("nem olvasható", envjel.verdict(None)[1])

    def test_proc_olvasas(self):
        p = fake_proc(4242, b"THUFIR_AGENT=kata\0")
        self.assertEqual(envjel.check(4242, p), (None, None))
        p = fake_proc(4243, b"PATH=/bin\0SECRET=" + TOKEN.encode() + b"\0")
        prob, _ = envjel.check(4243, p)
        self.assertTrue(prob)
        self.assertNotIn(TOKEN, prob)
        self.assertIsNotNone(envjel.check(9999, p)[1])  # nincs ilyen pid: nem mérhető
        self.assertIsNotNone(envjel.check(None, p)[1])

    def test_doctor_jelzi(self):
        ok = doctor.assess(_entry(), _m(), {}, env_check=(None, None), **KW)
        self.assertTrue(ok["ok"], ok)
        bad = doctor.assess(_entry(), _m(), {}, env_check=envjel.verdict({"PATH"}), **KW)
        self.assertFalse(bad["ok"])
        self.assertTrue(any("FLEET_AGENT" in p for p in bad["problems"]), bad)
        unk = doctor.assess(_entry(), _m(), {}, env_check=envjel.verdict(None), **KW)
        self.assertFalse(unk["ok"])
        self.assertTrue(any("environ" in u for u in unk["unknown"]), unk)

    def test_alapertelmezes_nem_valtoztat(self):
        """A régi hívók (env_check nélkül) ugyanazt kapják."""
        self.assertTrue(doctor.assess(_entry(), _m(), {}, **KW)["ok"])


if __name__ == "__main__":
    unittest.main()
