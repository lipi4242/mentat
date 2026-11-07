"""onboarding friction (0.3.1): asked to onboard into an existing business, a fresh agent never
found BEKOTES and read the whole HOME instead, other Claude memories included. The
always-loaded intake block names BEKOTES and forbids reading outside the working folder
until then; the README says how to start it.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REL = HERE.parent.parent
RULE = {"hu": ["Meglévő business", "reference/bekotes/BEKOTES.hu.md", "0. lépés", "minden feladatnál",
               "munkamappán kívül", "nem listázol", "kulcsneveit", "~/.claude", "AskUserQuestion-nel soha"],
        "en": ["Existing business", "reference/bekotes/BEKOTES.en.md", "step 0", "for every task",
               "outside the working folder", "list nothing", "key names", "~/.claude", "never AskUserQuestion"]}
README = {"README.hu.md": ["## Meglévő business bekötése", "reference/bekotes/BEKOTES.hu.md", "Úgy van utasítva"],
          "README.md": ["## Onboarding an existing business", "reference/bekotes/BEKOTES.en.md", "It is instructed"]}
OVERCLAIM = ["máshol nem kutat", "does not search the rest"]


class BekotesDiscoverable(unittest.TestCase):
    def intake(self, lang):
        root, home = pathlib.Path(tempfile.mkdtemp()), tempfile.mkdtemp()
        env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.path.join(home, "gitconfig"))
        r = subprocess.run([sys.executable, str(HERE / "mentat_scaffold.py"), "--lang", lang,
                            "--repo", str(root), "--base", "https://example.com/kit/v9.9.9/"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (root / "AGENTS.md").read_text(encoding="utf-8")
        return text[text.find("<!-- mentat:managed:start intake -->"):
                    text.find("<!-- mentat:managed:end intake -->")]

    def test_intake_names_bekotes_and_the_boundary(self):
        for lang, phrases in RULE.items():
            block = self.intake(lang)
            for p in phrases:
                self.assertIn(p, block, "%s: %s" % (lang, p))

    def test_readme_says_how_to_start_it(self):
        for name, phrases in README.items():
            text = (REL / name).read_text(encoding="utf-8")
            for p in phrases:
                self.assertIn(p, text, "%s: %s" % (name, p))
            for bad in OVERCLAIM:  # no promise the code does not enforce yet (CISO, #52)
                self.assertNotIn(bad, text, "%s: %s" % (name, bad))
            self.assertTrue((REL / phrases[1]).is_file(), phrases[1])


if __name__ == "__main__":
    unittest.main()
