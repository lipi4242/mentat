"""CISO-mellékmegállapítás (2026-10-29): a hid-atallas env-írása a `KULCS=érték` sort a `bash -c`
argv-jébe tette (látszik a /proc-ban, a `ps`-ben). Most a stdin-en megy."""
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import subprocess
import unittest
from unittest import mock

from fleet import hid_atallas_env as E, hid_atallas_remote as R

VALUE = "HAMIS-TITOK-ERTEK-42"


class SetEnvStdin(unittest.TestCase):
    def test_ertek_nincs_az_argvben(self):
        rem = R.Remote("box", "rili")
        seen = {}

        def fake_run(cmd, input=None, **kw):
            seen["argv"], seen["stdin"] = cmd, input
            return subprocess.CompletedProcess(cmd, 0, "OK\n", "")

        with mock.patch.object(R.subprocess, "run", side_effect=fake_run):
            E.set_env(rem, [("WEBHOOK_TOKEN", VALUE)], "20261029-000000")
        self.assertNotIn(VALUE, " ".join(seen["argv"]))
        self.assertIn(f"WEBHOOK_TOKEN={VALUE}\n", seen["stdin"])

    def test_tobbsoros_ertek_es_rossz_kulcs_elutasitva(self):
        rem = R.Remote("box", "rili")
        for pairs in ([("A", "x\ny")], [("A B", "x")], [("A;rm", "x")]):
            with mock.patch.object(R.subprocess, "run") as run, self.assertRaises(RuntimeError) as cm:
                E.set_env(rem, pairs, "20261029-000000")
            run.assert_not_called()
            self.assertNotIn("x\ny", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
