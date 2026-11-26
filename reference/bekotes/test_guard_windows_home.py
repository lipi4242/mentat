"""Guard: a Windows HOME (C:\\Users\\…) is a path, not a regex template (backslash escapes)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import unittest
from unittest import mock

import szerep_bash


class WindowsHome(unittest.TestCase):
    def test_home_with_backslashes_expands_verbatim(self):
        home = "C:\\Users\\demo"
        with mock.patch.dict(os.environ, {"HOME": home}):
            self.assertEqual(szerep_bash._expand("$HOME/x.txt"), home + "/x.txt")
            self.assertEqual(szerep_bash._expand("${HOME}"), home)
            self.assertEqual(szerep_bash._expand("plain/word"), "plain/word")


if __name__ == "__main__":
    unittest.main()
