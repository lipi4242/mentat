"""The contract and acceptance tools are wired in: one always-loaded sentence, the steps on demand.

The always-loaded rule only names the two tools and the reference file (it is paid for in every
turn); the how-to lives in reference/contract.<lang> and is read when a list, export or send is
agreed. The installer fetches every module the two tools import.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import unittest

from test_init_doc import DOCS, imports

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent
RULE = {"en": ["mentat_contract.py", "mentat_accept.py", "reference/contract.md"],
        "hu": ["mentat_contract.py", "mentat_accept.py", "reference/contract.hu.md"]}
GUIDE = {"en": REF / "contract.md", "hu": REF / "contract.hu.md"}
GUIDE_WORDS = ["draft", "approve", "--quote", "--version", "show", "diff", "check-write",
               "mentat_accept.py", "--recipients", "guestsCanSeeOtherGuests", "bcc", "tz"]


def intake(lang):
    text = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
    return text[text.find("<!-- mentat:managed:start intake -->"):text.find("<!-- mentat:managed:end intake -->")]


class ContractRule(unittest.TestCase):
    def test_the_always_loaded_rule_names_the_tools_and_the_guide(self):
        for lang, words in RULE.items():
            block = intake(lang)
            for w in words:
                self.assertIn(w, block, (lang, w))

    def test_the_guide_covers_every_command(self):
        for lang, path in GUIDE.items():
            text = path.read_text(encoding="utf-8")
            for w in GUIDE_WORDS:
                self.assertIn(w, text, (lang, w))
        self.assertIn("igen", GUIDE["hu"].read_text(encoding="utf-8"))

    def test_the_installer_fetches_both_tools_and_their_imports(self):
        need = {n + ".py" for n in imports("mentat_contract") | imports("mentat_accept")}
        self.assertIn("mentat_contract_terms.py", need)
        for lang, path in DOCS.items():
            text = path.read_text(encoding="utf-8")
            line = next(ln for ln in text.splitlines() if '-o ".mentat/bin/#1"' in ln)
            got = set(line.split("/reference/manifest/{", 1)[1].split("}", 1)[0].split(","))
            self.assertTrue(need <= got, (lang, need - got))

    def test_the_index_says_when_to_read_the_guide(self):
        self.assertIn("reference/contract.md", (REF / "_index.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
