"""One command instead of three (mérés 11): `close --next` closes and sets the
next step; `status` says whether the admin answers and what happens when it
does not (instead of the agent reading the CLI's source)."""
import unittest

try:
    import pytest  # noqa: F401
except ImportError:  # pragma: no cover
    pytest = None

from _fixture import GAZ_ID, Repo
from test_admin import AdminRepo


class TestCloseNext(Repo):
    def test_closes_the_occurrence_and_sets_the_next_step_in_one_run(self):
        out = self.cli("close", GAZ_ID, "--next", "Várni a novemberi számlát").stdout
        self.assertIn("closed: Gázszámla", out)
        self.assertIn("next step: Várni a novemberi számlát", out)
        shown = self.js("show", GAZ_ID)
        self.assertEqual(shown["next_action"], "Várni a novemberi számlát")
        self.assertEqual(shown["due_at"], "2026-11-10")

    def test_without_next_the_step_is_left_alone(self):
        before = self.js("show", GAZ_ID)["next_action"]
        self.cli("close", GAZ_ID)
        self.assertEqual(self.js("show", GAZ_ID)["next_action"], before)

    def test_an_empty_next_clears_it(self):
        self.cli("close", GAZ_ID, "--next", "")
        self.assertIsNone(self.js("show", GAZ_ID)["next_action"])


class TestCloseNextAdmin(AdminRepo):
    def test_same_through_the_api(self):
        self.seed()
        self.cli("close", GAZ_ID, "--next", "Új lépés")
        self.assertEqual(self.store.cases[GAZ_ID]["next_action"], "Új lépés")


class TestStatus(AdminRepo):
    def test_admin_up_says_answering_and_what_offline_means(self):
        out = self.cli("status").stdout
        self.assertIn("— answering", out)
        for want in ("exit 3", "nothing written", "no queue", "no fall-back"):
            self.assertIn(want, out)

    def test_admin_down_says_so(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.srv = None
        self.assertIn("NOT answering", self.cli("status").stdout)


class TestStatusMarkdown(Repo):
    def test_markdown_mode_has_no_offline_story(self):
        out = self.cli("status").stdout
        self.assertIn("cases.backend: markdown", out)
        self.assertNotIn("admin is down", out)


if __name__ == "__main__":
    unittest.main()
