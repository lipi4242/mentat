"""K24 (h2-1, 2026-10-19): on a takeover the first reply missed the
half-finished work, and another person's uncommitted changes went silently
into the brain commit. The brain prompt says it before the first reply.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import pathlib
import unittest

RELEASE = pathlib.Path(__file__).resolve().parent.parent.parent
PHRASES = {
    "hu": ["mi félkész", "mit változtatott más", "ne commitold szó nélkül"],
    "en": ["what is half-finished", "what someone else changed", "never commit them silently"],
}


class TakeoverSummary(unittest.TestCase):
    def test_brain_prompt_asks_for_it_before_the_first_answer(self):
        for lang, phrases in PHRASES.items():
            text = (RELEASE / ("BRAIN-PROMPT.%s.md" % lang)).read_text(encoding="utf-8")
            before_steps = text[:text.find("1. **")]
            for p in phrases:
                self.assertIn(p, before_steps, "%s: %s" % (lang, p))


if __name__ == "__main__":
    unittest.main()
