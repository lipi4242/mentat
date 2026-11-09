"""`case new|update|review|confirm|review-due` — one-off processes with a goal.

    case new --title T --goal G [--frame F] [--next-action A] [--waiting-on W]
             [--due D --due-reason R] [--brain-ref PATH] [--review-every DAYS] [--idem K]
    case update ID [--title ...] [--goal ...] ... [--rev N]
    case review ID --note N [--rev N]        # "I looked at it": sets last_reviewed
    case confirm ID [--rev N]                # a human's step; an agent's case is a proposal
    case review-due                          # my monitored cases whose review is due

A case created by an agent stays a proposal until a human confirms it. There is
no repeating case: a recurring obligation is not a case (no --repeat here).
Close a case with `task done ID --children close|keep`.
"""
from __future__ import annotations

import argparse
from typing import Any

from . import work

CASE_FIELDS = ("goal", "frame", "next_action", "waiting_on", "due_reason", "brain_ref")


def add(sub) -> None:
    p = sub.add_parser("case", help="cases: new, update, review, confirm, review-due").add_subparsers(dest="verb", required=True)
    n = p.add_parser("new")
    n.add_argument("--title", required=True)
    _fields(n)
    work.add_idem(n)
    u = p.add_parser("update")
    u.add_argument("id")
    u.add_argument("--title")
    _fields(u)
    work.add_rev(u)
    r = p.add_parser("review")
    r.add_argument("id")
    r.add_argument("--note", required=True)
    work.add_rev(r)
    c = p.add_parser("confirm")
    c.add_argument("id")
    work.add_rev(c)
    p.add_parser("review-due")


def _days(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        n = 0
    if n <= 0:
        raise argparse.ArgumentTypeError(f"--review-every must be a whole number of days > 0: {text!r}")
    return n


def _fields(p: argparse.ArgumentParser) -> None:
    p.add_argument("--description")
    p.add_argument("--due", help="YYYY-MM-DD")
    for f in CASE_FIELDS:
        p.add_argument("--" + f.replace("_", "-"))
    p.add_argument("--review-every", type=_days, help="days between reviews (none = not monitored)")


def _split(a: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    task = {"title": work.text(a.title, "title"), "description": a.description, "due_date": a.due}
    case = {f: work.text(getattr(a, f), f.replace("_", "-")) for f in CASE_FIELDS}
    case["review_every"] = a.review_every
    return ({k: v for k, v in task.items() if v is not None},
            {k: v for k, v in case.items() if v is not None})


def run(a: argparse.Namespace) -> int:
    c, s = work.client()
    if a.verb == "review-due":
        return work.show(c.get_json("/cases/review-due", {"for": s.handle}))
    if a.verb == "new":
        task, case = _split(a)
        if not case.get("goal"):
            raise work.UsageError("a case needs --goal: what done means for the whole case")
        body = {"kind": "case", **task, "case": case}
        body["idem_key"] = work.idem(a.idem, "case", body)
        return work.show(c.send("POST", "/tasks", body))
    path = work.task_path(a.id)
    if a.verb == "update":
        task, case = _split(a)
        if not task and not case:
            raise work.UsageError("case update needs at least one field to change")
        return work.show(c.send("PATCH", path, {"set": task or None, "case": case or None,
                                                "expected_rev": work.rev_of(c, path, a.rev)}))
    if a.verb == "review":
        return work.show(c.send("POST", path + "/review", {
            "note": work.required(a.note, "note"), "expected_rev": work.rev_of(c, path, a.rev)}))
    return work.show(c.send("POST", path + "/confirm", {"expected_rev": work.rev_of(c, path, a.rev)}))
