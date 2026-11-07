"""The Google tools are wired in: one always-loaded line, the steps on demand, a download that
brings every module the two tools import (beyond what the installer already fetched)."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import pathlib
import re
import tempfile
import unittest

from mentat_caps_probe import Prober

from test_contract_rule import intake
from test_init_doc import DOCS, imports

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent
RULE = {"en": ["mentat_google.py", "mentat_google_auth.py", "own OAuth server", "reference/google.md"],
        "hu": ["mentat_google.py", "mentat_google_auth.py", "saját OAuth-szerver", "reference/google.hu.md"]}
GUIDE = {"en": REF / "google.md", "hu": REF / "google.hu.md"}
WORDS = ["import-client", "login --remote", "finish", "--no-browser", "ssh -L", "--timeout", "Desktop app",
         "--notify", "--guests contract", "visibility", "Bcc", "READ BACK", "7 ", "pip install --user google-auth-oauthlib"]


def fetched(text, folder="manifest"):
    got = set()
    for group in re.findall(r"/reference/%s/\{([^}]*)\}" % folder, text):
        got |= set(group.split(","))
    return got


class GoogleRule(unittest.TestCase):
    def test_the_always_loaded_line(self):
        for lang, words in RULE.items():
            for w in words:
                self.assertIn(w, intake(lang), (lang, w))

    def test_the_guide_covers_the_flows_and_the_calls(self):
        for lang, path in GUIDE.items():
            text = path.read_text(encoding="utf-8")
            for w in WORDS:
                self.assertIn(w, text, (lang, w))

    def test_the_download_brings_every_import(self):
        need = {n + ".py" for n in imports("mentat_google") | imports("mentat_google_auth")}
        for lang, path in GUIDE.items():
            have = fetched(path.read_text(encoding="utf-8")) | fetched(DOCS[lang].read_text(encoding="utf-8"))
            self.assertTrue(need <= have, (lang, need - have))

    def test_the_catalog_says_shipped_and_probes_the_installed_tools(self):
        entries = [e for f in sorted((HERE / "capabilities").glob("*.json")) for e in json.loads(f.read_text())]
        google = [e for e in entries if e["category"] == "google"]
        self.assertTrue(google and all(e["lifecycle"] == "active" for e in google))
        root = pathlib.Path(tempfile.mkdtemp())
        self.assertEqual(Prober(root, entries).state("google.calendar")["availability"], "off")
        (root / ".mentat" / "bin").mkdir(parents=True)
        for tool in ("mentat_google.py", "mentat_google_auth.py", "mentat_contract.py"):
            (root / ".mentat" / "bin" / tool).write_text("")
        self.assertEqual(Prober(root, entries).state("google.calendar")["availability"], "on")

    def test_the_index_row(self):
        self.assertIn("reference/google.md", (REF / "_index.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
