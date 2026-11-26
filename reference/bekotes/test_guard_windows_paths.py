"""Guard: on Windows the working-folder boundary sees C:\\Users\\x, C:/Users/x and /c/Users/x.

A Windows run showed it: the boundary compared paths by "/", but Windows gives "C:\\Users\\x"
(and expanduser a mixed "C:\\Users\\x/.claude/…"), so a read of another project's memory
outside the folder was allowed, and mentat_init's own selftest stopped on it.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import ntpath
import os
import unittest
from unittest import mock

import szerep_bash
import szerep_kint


class WinPath(unittest.TestCase):
    def test_every_windows_spelling_is_one_slash_path(self):
        for raw in ("C:\\Users\\demo\\x.md", "C:/Users/demo/x.md", "/c/Users/demo/x.md",
                    "C:\\Users\\demo/x.md"):
            self.assertEqual(szerep_bash.win_path(raw, nt=True), "C:/Users/demo/x.md", raw)

    def test_posix_paths_are_untouched(self):
        for raw in ("/c/Users/demo", "a\\b", "/Users/demo/x.md"):
            self.assertEqual(szerep_bash.win_path(raw, nt=False), raw)

    def test_a_drive_root_and_a_plain_letter_folder(self):
        self.assertEqual(szerep_bash.win_path("/d", nt=True), "D:/")
        self.assertEqual(szerep_bash.win_path("/data/x", nt=True), "/data/x")


class WindowsZone(unittest.TestCase):
    """With Windows path rules (ntpath), the users folder and HOME are in the zone, by "/"."""

    def setUp(self):
        for p in (mock.patch.object(szerep_kint, "NT", True), mock.patch.object(szerep_bash, "NT", True),
                  mock.patch.object(szerep_kint.os, "path", ntpath),
                  mock.patch.dict(os.environ, {"HOME": "C:\\Users\\demo", "SystemDrive": "C:"})):
            p.start()
            self.addCleanup(p.stop)

    def test_another_projects_memory_is_in_the_zone(self):
        f = szerep_kint.real("C:\\Users\\demo/.claude/projects/other/memory/notes.md")
        self.assertEqual(f, "c:/users/demo/.claude/projects/other/memory/notes.md")
        self.assertTrue(any(szerep_kint.under(f, z) for z in szerep_kint._zone()))

    def test_another_users_folder_is_in_the_zone(self):
        f = szerep_kint.real("/c/Users/alpha/x.txt")
        self.assertTrue(any(szerep_kint.under(f, z) for z in szerep_kint._zone()), f)



class OtherWindowsForms(unittest.TestCase):
    def test_a_grep_ancestor_compares_by_slash(self):
        import szerep_tiltott
        with mock.patch.object(szerep_bash, "NT", True), mock.patch.object(szerep_tiltott.os, "path", ntpath):
            self.assertEqual(szerep_tiltott._forms("C:\\Users\\demo\\munka"), {"c:/users/demo/munka"})

    def test_a_drive_path_in_any_tool_is_judged(self):
        self.assertEqual(szerep_kint._pathlike({"a": "C:\\Users\\x", "b": "d:/y", "c": "plain"}),
                         ["C:\\Users\\x", "d:/y"])


    def test_a_glob_with_a_drive_pattern_is_judged_where_it_points(self):
        with mock.patch.object(szerep_kint, "NT", True), mock.patch.object(szerep_bash, "NT", True), \
                mock.patch.object(szerep_kint.os, "path", ntpath):
            got = [p for p, _ in szerep_kint.paths("Glob", {"pattern": "C:\\Users\\x\\business/**"}, "D:\\repo")]
        self.assertTrue(any(p.replace("\\", "/").lower().startswith("c:/users/x/business") for p in got), got)

    def test_a_windows_user_gate_command_is_recognised(self):
        import szerep_id_felhasznaloi as f
        for cmd in ("C:\\Users\\x\\identitas-kapu\\current\\kapu.py --hook",
                    "py -I C:/Users/x/identitas-kapu/current/kapu.py --hook", "/home/x/identitas-kapu/current/kapu.py --hook"):
            self.assertTrue(f.USER_GATE.search(cmd), cmd)
        self.assertTrue(f.PLUGIN_GATE.search('python3 "C:\\p\\hooks\\identitas\\kapu.py" --hook'))


    def test_a_drive_path_inside_inline_code_is_read(self):
        with mock.patch.object(szerep_bash, "NT", True), mock.patch.object(szerep_bash.os, "path", ntpath):
            for code in ("python3 -c \"print(open('C:\\Users\\x\\.claude\\m.md').read())\"",
                         "python3 -c \"print(open('C:/Users/x/.claude/m.md').read())\"",
                         "cat 'C:\\Users\\x\\.claude\\m.md'"):
                got = [p.replace("\\", "/").lower() for p in szerep_bash.analyse(code, "D:\\repo")[0]]
                self.assertIn("c:/users/x/.claude/m.md", got, code)


if __name__ == "__main__":
    unittest.main()
