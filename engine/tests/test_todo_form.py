#!/usr/bin/env python3
"""anytime_todo `item submit --form`: each broken form is refused locally, and no
submit request is sent.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_todo_item_cli import ItemCase  # noqa: E402


class Refusing(ItemCase):
    def refused(self, text: str, why: str) -> None:
        p = self.root / "bad.md"
        p.write_text(text)
        rc, out = self.submit(p)
        self.assertEqual(rc, 1, out)
        self.assertIn(why, out)
        self.assertEqual(self.sent("submit"), [])


class TestFormGuards(Refusing):
    """Each broken form is refused locally: no submit request is sent."""

    def test_missing_ac(self):
        text = self.filled().read_text()
        self.refused(text[:text.index("### AC AC2")] + text[text.index("## B)"):], "AC missing")

    def test_duplicate_ac(self):
        text = self.filled().read_text()
        block = text[text.index("### AC AC1"):text.index("### AC AC2")]
        self.refused(text.replace(block, block + block), "appears twice")

    def test_foreign_ac(self):
        self.refused(self.filled().read_text().replace("AC AC2", "AC AC9"), "not a live AC")

    def test_untouched_verdict_and_blank_evidence(self):
        self.refused(self.form().replace("- summary: ", "- summary: s"), "verdict must be one of")
        self.refused(self.form().replace("- summary: ", "- summary: s")
                     .replace("met | not_met | na", "met"), "evidence is required")

    def test_ac_changed_since_the_form(self):
        p = self.filled()
        self.srv.items["I1"]["acs"][0]["text"] = "Kész, ha AC1 390 px-en is teljesül"
        self.refused(p.read_text(), "changed since the form was made")

    def test_not_a_form(self):
        self.refused("# jegyzet\n", "not an AC form")

    def test_form_of_another_item(self):
        self.refused(self.filled().read_text().replace("item=I1", "item=I2"), "is for item I2")



class TestFormContent(ItemCase):
    """Nothing the developer wrote is lost on the way to the server."""

    def body_of(self, text: str) -> dict:
        p = self.root / "f.md"
        p.write_text(text)
        rc, out = self.submit(p)
        self.assertEqual(rc, 0, out)
        return self.sent("submit")[0][2]

    def test_a_heading_inside_a_code_fence_stays_in_the_body(self):
        fenced = "## B) Tests\nFailure output:\n```markdown\n## unexpected heading\n## C) not a section\nFAIL: tests failed\n```\nafter the fence"
        body = self.body_of(self.filled().read_text().replace("## B) Tests", fenced, 1))["body"]
        for kept in ("## unexpected heading", "## C) not a section", "FAIL: tests failed", "after the fence"):
            self.assertIn(kept, body)

    def test_an_unknown_heading_outside_a_fence_is_content(self):
        body = self.body_of(self.filled().read_text().replace("## C) Review", "## Notes\nsee log\n\n## C) Review", 1))["body"]
        self.assertIn("## Notes\nsee log", body)

    def test_quoted_evidence_lines_are_evidence(self):
        text = self.filled().read_text().replace("- evidence: test_ac1 zöld",
                                                 "- evidence: observed output:\n> FAIL: permission denied\n> exit 1", 1)
        ev = self.body_of(text)["results"][0]["evidence"]
        self.assertEqual(ev, "observed output:\n> FAIL: permission denied\n> exit 1")

    def test_fenced_evidence_is_kept_whole(self):
        text = self.filled().read_text().replace("- evidence: test_ac1 zöld",
                                                 "- evidence: log:\n```\n### AC AC2\n- verdict: na\n```", 1)
        res = self.body_of(text)["results"]
        self.assertEqual([r["ac_id"] for r in res], ["AC1", "AC2"])
        self.assertIn("### AC AC2\n- verdict: na", res[0]["evidence"])
        self.assertEqual(res[1]["verdict"], "met")


class TestFormStructure(Refusing):
    def test_a_doubled_section_is_refused(self):
        text = self.filled().read_text()
        self.refused(text.replace("## D) Gates", "## B) Tests\nmore\n\n## D) Gates", 1), "two B sections")

    def test_typed_text_in_e_is_refused(self):
        self.refused(self.filled().read_text().replace("## E) Verdict", "## E) Verdict\nIGEN", 1), "derived")

    def test_an_unknown_meta_line_is_refused(self):
        self.refused(self.filled().read_text().replace("- pr: ", "- notes: x\n- pr: ", 1), "only summary")

    def test_text_before_meta_is_refused(self):
        self.refused(self.filled().read_text().replace("## Meta", "fontos megjegyzés\n\n## Meta", 1), "before the Meta")


if __name__ == "__main__":
    unittest.main()
