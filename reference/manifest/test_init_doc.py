"""The initialization runs mentat_init.py after ONE bundle of questions (measured: 8-12 turns).

The real decisions are asked in one message, step 1 fetches every module mentat_init.py
needs, one call installs, and what the tool now does (git identity, fresh-session probe)
is no longer hand-run by the agent.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import re
import unittest

HERE = pathlib.Path(__file__).resolve().parent
DOCS = {"hu": HERE.parent / "initialization.hu.md", "en": HERE.parent / "initialization.md"}
BUNDLE = {"hu": "egyetlen üzenetben", "en": "in one message"}


def imports(name, seen=None):
    seen = set() if seen is None else seen
    if name in seen or not (HERE / (name + ".py")).is_file():
        return seen
    seen.add(name)
    for m in re.findall(r"^\s*(?:import|from) (\w+)", (HERE / (name + ".py")).read_text(), re.M):
        imports(m, seen)
    return seen


def guard_modules():
    """szerep_guard.py and everything it imports from bekotes/ (CISO, #69: the doc test checks it too)."""
    bk, todo, seen = HERE.parent / "bekotes", ["szerep_guard"], set()
    while todo:
        n = todo.pop()
        if n in seen or not (bk / (n + ".py")).is_file():
            continue
        seen.add(n)
        todo += re.findall(r"^\s*(?:import|from) (\w+)", (bk / (n + ".py")).read_text(), re.M)
    return {n + ".py" for n in seen}


class InitDoc(unittest.TestCase):
    def test_step1_fetches_every_guard_module(self):
        for lang, path in DOCS.items():
            text = path.read_text(encoding="utf-8")
            got = set()
            for group in re.findall(r'-o "\.mentat/bin/bekotes/#1" "[^"]*/reference/(?:bekotes|manifest)/\{([^}]*)\}"', text):
                got |= set(group.split(","))
            self.assertTrue(guard_modules() <= got, (lang, guard_modules() - got))

    def test_one_bundle_then_one_call(self):
        need = {n + ".py" for n in imports("mentat_init")}
        for lang, path in DOCS.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn(BUNDLE[lang], text, lang)
            self.assertIn("python3 -I .mentat/bin/mentat_init.py --lang %s" % lang, text, lang)  # -I: CISO, #91
            fetched = set(re.search(r'-o "\.mentat/bin/#1" "[^"]*/manifest/\{([^}]*)\}"', text).group(1).split(","))
            self.assertTrue(need <= fetched, (lang, need - fetched))
            self.assertIn("MENTAT-INIT", text, lang)
            for gone in ("claude -p", "git config user.name"):  # the tool does these now
                self.assertNotIn(gone, text, (lang, gone))

    def test_the_interview_skips_what_the_bundle_asked(self):
        for lang, word in (("hu", "hagyd ki"), ("en", "skip")):
            text = (HERE.parent / "intro-chat" / ("intro-questions.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertIn(word, text.lower()[:400], lang)  # said up front, before the steps


if __name__ == "__main__":
    unittest.main()
