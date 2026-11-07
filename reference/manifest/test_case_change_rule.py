"""Before moving a case's date or changing its status, the agent reads the case's notes and
conditions; on a conflict it asks first and changes only after the answer.

Measured: a case note said the date may not be earlier than a given day, and a date move
went through without a question (h2-6)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TPL = HERE.parent / "templates"
ALWAYS = {"hu": "Ügy dátumának vagy állapotának változtatása előtt olvasd el a jegyzetét",
          "en": "Before you move a case's date or change its status, read its notes"}
DETAIL = {"hu": "## Dátum- vagy állapotváltás előtt", "en": "## Before a date or status change"}


class CaseChangeRule(unittest.TestCase):
    def test_always_loaded_rule(self):
        for lang, phrase in ALWAYS.items():
            text = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertIn(phrase, text, lang)

    def test_template_has_the_detail(self):
        for lang, head in DETAIL.items():
            text = (TPL / ("case.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertIn(head, text, lang)


if __name__ == "__main__":
    unittest.main()
