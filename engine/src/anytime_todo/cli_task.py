"""`task new|update|done|comment` — plain todos (and closing a case).

    task new --title T [--description D] [--due YYYY-MM-DD] [--parent ID] [--assignee PID] [--idem K]
    task update ID [--title T] [--description D] [--due D] [--assignee PID] [--rev N]
    task done ID [--children close|keep] [--rev N]     # a case with open todos needs --children
    task comment ID --text T [--rev N]

A backlog item is not a plain todo: the server refuses status and assignee
writes on it; use the `item` verbs.
"""
from __future__ import annotations

import argparse
from typing import Any

from . import work
from .api import TodoApiError


def add(sub) -> None:
    p = sub.add_parser("task", help="plain todos").add_subparsers(dest="verb", required=True)
    n = p.add_parser("new")
    n.add_argument("--title", required=True)
    _fields(n)
    n.add_argument("--parent")
    work.add_idem(n)
    u = p.add_parser("update")
    u.add_argument("id")
    u.add_argument("--title")
    _fields(u)
    work.add_rev(u)
    d = p.add_parser("done")
    d.add_argument("id")
    d.add_argument("--children", choices=("close", "keep"),
                   help="a case with open todos: close them too, or keep them open")
    work.add_rev(d)
    c = p.add_parser("comment")
    c.add_argument("id")
    c.add_argument("--text", required=True)
    work.add_rev(c)


def _fields(p: argparse.ArgumentParser) -> None:
    p.add_argument("--description")
    p.add_argument("--due", help="YYYY-MM-DD")
    p.add_argument("--assignee", help="principal id")


def _set(a: argparse.Namespace) -> dict[str, Any]:
    out = {"title": work.text(getattr(a, "title", None), "title"),
           "description": a.description, "due_date": a.due, "assignee_id": a.assignee}
    return {k: v for k, v in out.items() if v is not None}


def run(a: argparse.Namespace) -> int:
    c, _ = work.client()
    if a.verb == "new":
        body = {"kind": "todo", **_set(a), "parent_id": a.parent}
        body["idem_key"] = work.idem(a.idem, "task", body)
        return work.show(c.send("POST", "/tasks", body))
    path = work.task_path(a.id)
    if a.verb == "update":
        fields = _set(a)
        if not fields:
            raise work.UsageError("task update needs at least one field to change")
        return work.show(c.send("PATCH", path, {"set": fields,
                                                "expected_rev": work.rev_of(c, path, a.rev)}))
    if a.verb == "done":
        return work.show(c.send("POST", path + "/complete", {
            "expected_rev": work.rev_of(c, path, a.rev), "children": a.children}))
    return comment(c, a.id, work.required(a.text, "text"), a.rev)


def comment(c, task_id: str, body: str, rev: int | None) -> int:
    """A comment changes no field, so a rev that moved meanwhile is retried once
    (only when the rev was read here, not given by the caller)."""
    path = work.task_path(task_id)
    for attempt in (1, 2):
        try:
            return work.show(c.send("POST", path + "/comments",
                                    {"body": body, "expected_rev": work.rev_of(c, path, rev)}))
        except TodoApiError as e:
            if e.status != 409 or rev is not None or attempt == 2:
                raise
    return 1   # pragma: no cover
