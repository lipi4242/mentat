"""`blokk`: the AGENTS.md block says where each repo is and how to search and refresh.

KJ 0.3.0 h1 16 (Opus): 8 sessions, half the calls orientation — every session
looked for the repo again (`find / -name zoldag-web`) and re-read the role file.
h1 17: 5 of 11 calls found the refresh command. The block is always in context.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import shutil
import unittest

from _bekotes_repo import bk, make_agent


class BlokkUtak(unittest.TestCase):
    def setUp(self):
        self.root = make_agent()
        self.addCleanup(shutil.rmtree, self.root, True)
        r = bk(self.root, "elokeszit", "--business", "zoldag")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = bk(self.root, "blokk", "--repo", ".", "--business", "zoldag")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.text = (self.root / "AGENTS.md").read_text(encoding="utf-8")

    def test_a_repo_line_names_its_local_path(self):
        self.assertIn("- zoldag-web (repo): elérhető — munka/zoldag-web", self.text)

    def test_a_non_repo_source_gets_no_path(self):
        self.assertIn("- levelezes (mail): tiltott — csak kérésre", self.text)
        self.assertNotIn("munka/linear.json", self.text)

    def test_search_and_refresh_commands_are_in_the_block(self):
        self.assertIn("python3 .mentat/bin/bekotes/bekotes.py olvas grep", self.text)
        self.assertIn("python3 -m anytime_bekotes.frissit --begin", self.text)


if __name__ == "__main__":
    unittest.main()
