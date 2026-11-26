"""Windows Python ships no IANA time-zone database: the install and the upgrade put the tzdata
package next to it, say so in one line, and when that fails say what will not work and the exact
command, without stopping. On macOS and Linux nothing changes (no pip call at all)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_init_os as osx  # noqa: E402


class FakeRun:
    """Answers the probe and the pip call in order; records every argv."""

    def __init__(self, *codes):
        self.codes, self.calls = list(codes), []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        code = self.codes.pop(0)
        if isinstance(code, BaseException):
            raise code
        code, out = code if isinstance(code, tuple) else (code, "")
        return subprocess.CompletedProcess(argv, code, out, "")


PY = "C:/Py/python.exe"


class Tzdata(unittest.TestCase):
    def tz(self, system, run, lang="hu"):
        with mock.patch.object(osx, "system", return_value=system):
            return osx.ensure_tzdata(lang, run=run, py=PY)

    def test_mac_and_linux_never_call_pip(self):
        for s in ("mac", "linux"):
            run = FakeRun()
            self.assertIsNone(self.tz(s, run))
            self.assertEqual(run.calls, [])

    def test_windows_with_the_database_does_nothing(self):
        run = FakeRun(0)
        self.assertIsNone(self.tz("windows", run))
        self.assertEqual(len(run.calls), 1)  # the probe only

    def test_windows_without_it_installs_and_says_so_in_one_line(self):
        run = FakeRun(1, 0, 0)  # probe: missing, pip: ok, probe: present
        line = self.tz("windows", run)
        self.assertEqual(run.calls[1][:4], [PY, "-m", "pip", "install"])
        self.assertIn("tzdata", run.calls[1])
        self.assertNotIn("--user", run.calls[1])  # the tools run with -I: a user site is invisible to them
        self.assertIn("-I", run.calls[2])  # the re-probe sees what the tools will see
        self.assertIn("tzdata", line)
        self.assertNotIn("\n", line)

    def test_a_failed_install_names_what_breaks_and_the_command_and_does_not_raise(self):
        cases = ([1, 1], [1, OSError("no pip")], [1, 0, 1], [1, subprocess.TimeoutExpired("pip", 1)])
        for codes in cases:
            for lang, word in (("hu", "határid"), ("en", "deadline")):
                line = self.tz("windows", FakeRun(*codes), lang)
                self.assertIn('"%s" -m pip install tzdata' % PY, line, (codes, lang))
                self.assertIn(word, line)
                self.assertNotIn("\n", line)

    def test_an_all_users_python_says_run_it_as_administrator(self):
        # Program Files is not writable: pip falls back to the user site, which -I hides, so the
        # re-probe fails and the plain command would fail the same way
        outs = ((0, "Defaulting to user installation because normal site-packages is not writeable\n"),
                (1, "ERROR: Could not install packages due to an OSError: [WinError 5] Access is denied"))
        for pip in outs:
            for lang, word in (("hu", "rendszergazda"), ("en", "administrator")):
                line = self.tz("windows", FakeRun(1, pip, 1), lang)
                self.assertIn(word, line, (pip, lang))
                self.assertIn('"%s" -m pip install tzdata' % PY, line)
                self.assertNotIn("\n", line)

    def test_a_plain_failure_does_not_blame_permissions(self):
        line = self.tz("windows", FakeRun(1, (1, "ERROR: No matching distribution found for tzdata")))
        self.assertNotIn("rendszergazda", line)


class Wired(unittest.TestCase):
    def test_install_and_upgrade_both_call_it(self):
        for tool in ("mentat_init.py", "mentat_upgrade.py"):
            self.assertIn(".ensure_tzdata(", (HERE / tool).read_text(encoding="utf-8"), tool)


if __name__ == "__main__":
    unittest.main()
