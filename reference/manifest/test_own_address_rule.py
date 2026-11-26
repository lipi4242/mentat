"""The USER's own account address never stands literally in a tool call's input: the agent
reads it from config or env and references it. Measured: an always-on agent wrote it into a mail script's
From header in a shell command, Claude Code's built-in privacy check asked for confirmation in
the headless pane, and the agent stood there until the owner noticed."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
RULE = {"hu": "parancsba szó szerint sem írod", "en": "no command holds it literally"}
REF = {"hu": "konfigból/env-ből olvasd", "en": "read it from config/env"}


class OwnAddressRule(unittest.TestCase):
    def test_always_loaded_in_both_languages(self):
        for lang in RULE:
            text = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
            managed = text.split("<!-- mentat:managed:end intake -->")[0]
            self.assertIn(RULE[lang], managed, lang)
            self.assertIn(REF[lang], managed, lang)

    def test_gmail_helper_never_writes_from(self):
        src = (HERE / "google_mail.py").read_text(encoding="utf-8")
        self.assertNotIn('msg["From"]', src)


if __name__ == "__main__":
    unittest.main()
