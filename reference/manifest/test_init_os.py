"""The install on every OS: hooks run where Claude Code runs them, and a missing tool gets
the official one-line install for THIS system (0.3.1, one-prompt install).

Claude Code runs a hook command with `sh -c` on macOS/Linux and with Git Bash on Windows
(PowerShell only when Git Bash is missing, and the guard hook is POSIX shell): so on Windows
the brain needs Git Bash, and `python3` must answer inside the hook shell, not only here.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mentat_init_checks as checks  # noqa: E402
import mentat_init_os as osx  # noqa: E402


class HookShell(unittest.TestCase):
    def test_posix_is_sh(self):
        with mock.patch.object(osx, "system", return_value="mac"):
            self.assertEqual(osx.hook_shell({}), ["/bin/sh", "-c"])

    def test_windows_is_the_git_bash_next_to_git(self):
        git = pathlib.Path(tempfile.mkdtemp()) / "Git"
        (git / "cmd").mkdir(parents=True)
        (git / "bin").mkdir()
        (git / "cmd" / "git.exe").write_text("")
        (git / "bin" / "bash.exe").write_text("")
        with mock.patch.object(osx, "system", return_value="windows"), \
                mock.patch.object(osx.shutil, "which", return_value=str(git / "cmd" / "git.exe")):
            self.assertEqual(osx.hook_shell({}), [str(git / "bin" / "bash.exe"), "-c"])

    def test_windows_honours_the_claude_code_setting(self):
        bash = pathlib.Path(tempfile.mkdtemp()) / "bash.exe"
        bash.write_text("")
        with mock.patch.object(osx, "system", return_value="windows"), \
                mock.patch.object(osx.shutil, "which", return_value=None):
            self.assertEqual(osx.hook_shell({"CLAUDE_CODE_GIT_BASH_PATH": str(bash)}), [str(bash), "-c"])

    def test_windows_without_git_bash_is_none_not_wsl_bash(self):
        # C:\Windows\System32\bash.exe is WSL: Claude Code never runs hooks there
        with mock.patch.object(osx, "system", return_value="windows"), \
                mock.patch.object(osx.shutil, "which", side_effect=lambda n: "C:/Windows/System32/bash.exe"
                                  if n == "bash" else None):
            self.assertIsNone(osx.hook_shell({}))

    def test_a_script_runs_through_bash_on_windows_only(self):
        with mock.patch.object(osx, "hook_shell", return_value=["C:/Git/bin/bash.exe", "-c"]), \
                mock.patch.object(osx, "system", return_value="windows"):
            self.assertEqual(osx.script("x/sync-to.sh"), ["C:/Git/bin/bash.exe", "x/sync-to.sh"])
        with mock.patch.object(osx, "system", return_value="linux"):
            self.assertEqual(osx.script("x/sync-to.sh"), ["x/sync-to.sh"])


class Hints(unittest.TestCase):
    def test_each_system_gets_its_official_install(self):
        want = {("git", "windows"): "winget install --id Git.Git", ("git", "mac"): "xcode-select --install",
                ("git", "linux"): "sudo apt install git", ("python3", "windows"): "winget install 9NQ7512CXL7T",
                ("python3", "mac"): "xcode-select --install", ("python3", "linux"): "sudo apt install python3"}
        for (tool, system), text in want.items():
            with mock.patch.object(osx, "system", return_value=system):
                self.assertIn(text, osx.hint(tool), (tool, system))

    def test_windows_python_is_not_the_store_stub_package(self):
        # Python.Python.3.x has no python3.exe: the hook would hit the Microsoft Store stub
        with mock.patch.object(osx, "system", return_value="windows"):
            self.assertNotIn("Python.Python", osx.hint("python3"))


class Preflight(unittest.TestCase):
    def test_windows_without_git_bash_stops_before_anything(self):
        with mock.patch.object(osx, "hook_shell", return_value=None), \
                mock.patch.object(osx, "system", return_value="windows"):
            lines, problem = checks.preflight(False, True)
        self.assertIn("Git Bash", problem)
        self.assertIn("winget", problem)

    def test_python3_must_answer_in_the_hook_shell(self):
        with mock.patch.object(osx, "hook_shell", return_value=["/bin/sh", "-c"]), \
                mock.patch.object(checks, "_run", side_effect=lambda cmd, **kw: None if "python3" in cmd[-1]
                                  else checks.subprocess.CompletedProcess(cmd, 0, "2.1.309", "")):
            lines, problem = checks.preflight(False, True)
        self.assertIn("python3", problem or "")


class EndToEnd(unittest.TestCase):
    def test_a_python3_stub_in_the_hook_path_stops_the_install(self):
        import test_init
        base = test_init.InitBase("run_init")
        base.setUp()
        test_init.fake_bin(base.bin, "python3", "echo 'Python was not found; run without arguments' >&2; exit 9009")
        r = base.run_init()
        self.assertIn("MENTAT-INIT HIBA", r.stdout)
        self.assertIn("python3", r.stdout.splitlines()[-1])
        self.assertFalse((base.root / "AGENTS.md").exists(), "nothing done before the preflight passes")


if __name__ == "__main__":
    unittest.main()
