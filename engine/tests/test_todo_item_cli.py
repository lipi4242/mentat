#!/usr/bin/env python3
"""anytime_todo `item …`: a whole PM ↔ developer round through the CLI, and the
client guards that refuse a form or a decision before anything is sent.

Compatible with both pytest and direct execution (stdlib unittest).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

try:
    import pytest  # noqa: F401
except Exception:  # pragma: no cover
    pytest = None

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from _work_fixture import WorkCase, item  # noqa: E402

ACTOR_FIELDS = {"actor", "as", "owner_id", "created_by", "submitted_by", "decided_by", "author_id"}


class ItemCase(WorkCase):
    def setUp(self):
        super().setUp()
        self.srv.items["I1"] = item(stage="taken")

    def form(self) -> str:
        rc, out = self.cli("item", "show", "WEB-7", "--form")
        self.assertEqual(rc, 0, out)
        return out

    def filled(self, text: str | None = None, **verdicts) -> Path:
        text = text or self.form()
        text = text.replace("- summary: ", "- summary: a nézet kész")
        text = text.replace("- head_sha: ", "- head_sha: 0123abc")
        text = text.replace("- pr: ", "- pr: https://github.com/o/r/pull/7")
        for ac in ("AC1", "AC2"):
            v = verdicts.get(ac, "met")
            text = text.replace(f"### AC {ac}\n> Kész, ha {ac} teljesül\n- verdict: met | not_met | na\n"
                                "- evidence: ",
                                f"### AC {ac}\n> Kész, ha {ac} teljesül\n- verdict: {v}\n"
                                f"- evidence: test_{ac.lower()} zöld")
        p = self.root / "form.md"
        p.write_text(text)
        return p

    def submit(self, path: Path) -> tuple[int, str]:
        return self.cli("item", "submit", "WEB-7", "--form", str(path))


class TestRound(ItemCase):
    def test_form_carries_the_live_ac_ids_and_the_next_round(self):
        out = self.form()
        self.assertIn("<!-- mentat:ac-form item=I1 round=1 -->", out)
        self.assertIn("### AC AC1\n> Kész, ha AC1 teljesül", out)
        for head in ("## A)", "## B)", "## C)", "## D)", "## E)", "## F)"):
            self.assertIn(head, out)

    def test_submit_sends_exactly_one_result_per_ac(self):
        rc, out = self.submit(self.filled())
        self.assertEqual(rc, 0, out)
        (_, path, body), = self.sent("submit")
        self.assertEqual(path, "/items/I1/submit")
        self.assertEqual(body["round"], 1)
        self.assertEqual(body["results"], [
            {"ac_id": "AC1", "verdict": "met", "evidence": "test_ac1 zöld"},
            {"ac_id": "AC2", "verdict": "met", "evidence": "test_ac2 zöld"}])
        self.assertEqual((body["summary"], body["head_sha"], body["expected_rev"]),
                         ("a nézet kész", "0123abc", 1))
        self.assertEqual(body["links"], [{"kind": "pr", "url": "https://github.com/o/r/pull/7"}])
        self.assertIn("## B)", body["body"])
        self.assertNotIn("<!--", body["body"])

    def test_a_not_met_can_be_submitted_but_not_accepted(self):
        self.assertEqual(self.submit(self.filled(AC2="not_met"))[0], 0)
        rc, out = self.cli("item", "accept", "WEB-7", "--checked")
        self.assertEqual(rc, 2)
        self.assertIn("not met: AC2", out)
        self.assertEqual(self.sent("accept"), [])

    def test_accept_checks_every_result(self):
        self.submit(self.filled(AC2="na"))
        self.assertEqual(self.cli("item", "accept", "WEB-7", "--checked")[0], 0)
        (_, _, body), = self.sent("accept")
        self.assertEqual(body["checks"], [{"ac_id": "AC1", "pm_ok": 1}, {"ac_id": "AC2", "pm_ok": 1}])

    def test_accept_needs_the_explicit_checked(self):
        self.submit(self.filled())
        self.assertEqual(self.cli("item", "accept", "WEB-7")[0], 2)
        self.assertEqual(self.sent("accept"), [])

    def test_reject_names_the_failed_ac_with_a_reason(self):
        self.submit(self.filled())
        self.assertEqual(self.cli("item", "reject", "WEB-7", "--note", "nézd át")[0], 2)
        self.assertEqual(self.cli("item", "reject", "WEB-7", "--fail", "AC9=x", "--note", "n")[0], 2)
        rc, _ = self.cli("item", "reject", "WEB-7", "--fail", "AC2=390 px-en metsz", "--note", "nézd át")
        self.assertEqual(rc, 0)
        (_, _, body), = self.sent("reject")
        self.assertEqual(body["checks"], [{"ac_id": "AC1", "pm_ok": 1},
                                          {"ac_id": "AC2", "pm_ok": 0, "pm_note": "390 px-en metsz"}])

    def test_the_next_round_needs_a_fresh_form(self):
        old = self.filled()
        self.submit(old)
        self.cli("item", "reject", "WEB-7", "--fail", "AC1=nem", "--note", "újra")
        rc, out = self.submit(old)
        self.assertEqual(rc, 1)
        self.assertIn("round 1, the item expects 2", out)
        self.assertEqual(len(self.sent("submit")), 1)
        self.assertEqual(self.submit(self.filled())[0], 0)
        self.assertEqual(self.sent("submit")[-1][2]["round"], 2)

    def test_no_request_names_an_actor(self):
        self.cli("item", "issue", "WEB-7", "--dev", "rocky")
        self.cli("item", "take", "WEB-7")
        self.submit(self.filled())
        self.cli("item", "accept", "WEB-7", "--checked")
        self.cli("item", "new", "--project", "WEB", "--title", "x", "--ac", "Kész, ha y")
        self.assertGreaterEqual(len(self.srv.sent), 5)
        for _, path, body in self.srv.sent:
            self.assertEqual(ACTOR_FIELDS & set(body), set(), path)

    def test_stale_rev_is_reported_and_nothing_changes(self):
        rc, out = self.cli("item", "hold", "WEB-7", "--note", "várunk", "--rev", "0")
        self.assertEqual(rc, 1)
        self.assertIn("HTTP 409", out)
        self.assertEqual(self.srv.items["I1"]["stage"], "taken")


class TestSpec(ItemCase):
    def test_new_item_sends_project_acs_and_a_stable_idem(self):
        argv = ("item", "new", "--project", "WEB", "--title", "Labda", "--ac", "Kész, ha a",
                "--quote", "kinél a labda?", "--priority", "2")
        self.assertEqual(self.cli(*argv)[0], 0)
        self.assertEqual(self.cli(*argv)[0], 0)
        (_, _, a), (_, _, b) = self.sent("items")
        self.assertEqual(a["idem_key"], b["idem_key"])
        self.assertEqual((a["project"], a["acs"], a["request_quote"], a["priority"]),
                         ("WEB", ["Kész, ha a"], "kinél a labda?", 2))

    def test_ac_edit_uses_the_item_rev_and_keeps_the_ac_id(self):
        self.srv.items["I1"]["rev"] = 4
        self.assertEqual(self.cli("item", "ac-edit", "WEB-7", "AC1", "--text", "Kész, ha b")[0], 0)
        (method, path, body), = self.sent()
        self.assertEqual((method, path, body), ("PATCH", "/acs/AC1", {"text": "Kész, ha b",
                                                                       "expected_rev": 4}))

    def test_an_ac_of_another_item_is_refused(self):
        self.srv.items["I2"] = item("I2", "WEB-8", acs=("B1",))
        for argv in (("ac-edit", "WEB-7", "B1", "--text", "x"), ("ac-remove", "WEB-7", "B1")):
            rc, out = self.cli("item", *argv)
            self.assertEqual(rc, 2, out)
            self.assertIn("not a live AC of WEB-7", out)
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.srv.items["I2"]["acs"][0]["text"], "Kész, ha B1 teljesül")

    def test_link_takes_url_or_task(self):
        self.assertEqual(self.cli("item", "link", "WEB-7")[0], 2)
        self.assertEqual(self.cli("item", "link", "WEB-7", "--url", "u", "--task", "T")[0], 2)
        self.assertEqual(self.cli("item", "link", "WEB-7", "--url", "https://x/pull/1",
                                  "--kind", "pr")[0], 0)
        self.assertEqual(self.sent("links")[0][2]["kind"], "pr")


if __name__ == "__main__":
    unittest.main()
