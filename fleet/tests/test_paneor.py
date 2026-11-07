"""F-17 proxy a doctorban (CISO 10-24): a futó claude bináris tartalmazza-e a híd pane-őrének
mintáit; a minták a bridge/lib/pane-guard.mjs-hez kötve. Production code: paneor, doctor."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("FLEET_MAINTENANCE_DIR", tempfile.mkdtemp(prefix="fleet-test-locks-"))

from fleet import doctor, paneor  # noqa: E402
from test_truthful_health import _entry, _m  # noqa: E402
from test_hook_fail_open_n123 import KW  # noqa: E402


def fake_bin(content: bytes) -> Path:
    p = Path(tempfile.mkdtemp()) / "claude"
    p.write_bytes(b"\x7fELF" + os.urandom(64) + content + os.urandom(64))
    return p


GOOD = b'..children:"Do you want to proceed?"},..{label:"Yes",value:"yes"}..'


class PaneOr(unittest.TestCase):
    def test_megvannak(self):
        self.assertEqual(paneor.missing(fake_bin(GOOD)), [])
        self.assertIsNone(paneor.problem(fake_bin(GOOD)))

    def test_hianyzik_proxy_jelzes(self):
        p = fake_bin(b'children:"Would you like to proceed?"},{label:"Yes"}')
        msg = paneor.problem(p)
        self.assertIn("PROXY", msg)
        self.assertIn("QUESTION", msg)
        self.assertNotIn("YES_OPTION", msg)
        self.assertIn("YES_OPTION", paneor.problem(fake_bin(b"Do you want to x? {label:'Igen'}")))

    def test_nem_olvashato_nem_duplaz(self):
        self.assertIsNone(paneor.missing(Path("/nincs/ilyen/claude")))
        self.assertIsNone(paneor.problem(Path("/nincs/ilyen/claude")))
        empty = Path(tempfile.mkdtemp()) / "claude"
        empty.write_bytes(b"")
        self.assertIsNone(paneor.problem(empty))  # 0 bájt: mmap hiba → nem mérhető, nem riasztás

    def test_symlink_es_cache(self):
        real = fake_bin(GOOD)
        link = real.parent / "link"
        link.symlink_to(real)
        self.assertEqual(paneor.missing(link), [])
        real.write_bytes(b"semmi")  # új tartalom, új méret → új mérés
        self.assertEqual(len(paneor.missing(link)), 2)

    def test_a_hid_mintaihoz_kotve(self):
        """Ha valaki a pane-guard.mjs mintáit átírja, ez a proxy is igazítandó."""
        js = (ROOT / "bridge" / "lib" / "pane-guard.mjs").read_text()
        q = re.search(r"const QUESTION = /(.*)/;", js).group(1)
        y = re.search(r"const YES_OPTION = /(.*)/m;", js).group(1)
        self.assertTrue(q.startswith(paneor.MINTAK[0][0].decode()), q)
        self.assertIn("Yes", y)
        self.assertIn(b"Yes", paneor.MINTAK[1][0])

    def test_doctor_jelzi(self):
        msg = paneor.problem(fake_bin(b"semmi"))
        r = doctor.assess(_entry(), _m(), {}, hook_problems=[msg], **KW)
        self.assertFalse(r["ok"])
        self.assertTrue(any("PROXY" in p for p in r["problems"]))

    def test_doctor_bekotes(self):
        """A doctor() a unit binárisát méri, és a jelzés minden ágens sorába bekerül."""
        e = _entry()
        with mock.patch.object(doctor, "load_agents", return_value=[e]), \
                mock.patch.object(doctor, "local_host", return_value="probe-host"), \
                mock.patch.object(doctor, "load_state", return_value={"quarantined": False}), \
                mock.patch.object(doctor, "_sysctl_prop", return_value="active"), \
                mock.patch("fleet.signals.measure", return_value=_m()), \
                mock.patch("fleet.envjel.check", return_value=(None, None)), \
                mock.patch("fleet.hookguard.claude_version", return_value="2.1.310 (Claude Code)"), \
                mock.patch.object(paneor, "problem", return_value="PROXY: teszt") as pp:
            out = doctor.doctor(agent=e["agent"])
        pp.assert_called_once()
        self.assertTrue(any("PROXY: teszt" in p for p in out[-1]["problems"]), out)


if __name__ == "__main__":
    unittest.main()
