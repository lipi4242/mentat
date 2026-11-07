"""The test suites leave nothing in the temp folder (2026-10-24: ~50 000 tmpXXXX folders on a box,
the shared tmp quota ran out and another repo's gate went red with EDQUOT).

_tmp_run.py points tempfile and the TMPDIR of child processes at one per-run folder and removes
it at exit. This guard proves it on a small run (the module, a child process, a child of a child)
and checks that every test module imports it first, in manifest/ and in bekotes/.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
DIRS = (HERE, HERE.parent / "bekotes")


class TmpClean(unittest.TestCase):
    def test_a_run_and_its_children_leave_nothing(self):
        fresh = tempfile.mkdtemp(prefix="zz-tmp-clean-", dir=_tmp_run.REAL_TMP)
        env = {k: v for k, v in os.environ.items() if not k.startswith("_MENTAT_TEST_")}
        env["TMPDIR"] = fresh
        child = "import sys; sys.path.insert(0, %r); import _tmp_run, tempfile; tempfile.mkdtemp()" % str(HERE)
        code = ("import sys, subprocess; sys.path.insert(0, %r); import _tmp_run, tempfile\n"
                "tempfile.mkdtemp(); tempfile.mkstemp(); tempfile.NamedTemporaryFile(delete=False)\n"
                "subprocess.run([sys.executable, '-c', %r])\n"
                "subprocess.run([sys.executable, '-c', 'import tempfile; tempfile.mkdtemp()'])\n") % (str(HERE), child)
        try:
            r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sorted(os.listdir(fresh)), [])
        finally:
            subprocess.run(["rm", "-rf", fresh])

    def test_every_test_module_imports_it_first(self):
        missing = []
        for d in DIRS:
            for p in sorted(d.glob("test_*.py")):
                imports = re.findall(r"^(?:import|from) (\w+)", p.read_text(encoding="utf-8"), re.M)
                imports = [m for m in imports if m != "__future__"]
                if not imports or imports[0] != "_tmp_run":
                    missing.append("%s/%s" % (d.name, p.name))
        self.assertEqual(missing, [])

    def test_both_copies_are_the_same(self):
        self.assertEqual((HERE / "_tmp_run.py").read_text(), (HERE.parent / "bekotes" / "_tmp_run.py").read_text())


if __name__ == "__main__":
    unittest.main()
