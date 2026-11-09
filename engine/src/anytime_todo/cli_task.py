"""`task new|update|done|comment|show|list` — plain todos (and closing a case).

    task new --title T [--description D] [--due YYYY-MM-DD] [--parent REF] [--assignee PID]
             [--repeat RULE [--repeat-from schedule|completion]] [--idem K]
    task update REF [--title T] [--description D] [--due D] [--assignee PID]
             [--repeat RULE|none] [--repeat-from …] [--rev N]
    task done REF [--children close|keep] [--rev N]     # a case with open todos needs --children
    task comment REF --text T [--rev N]                  # also on a backlog item
    task show REF                                        # read back one task (an item key: the item)
    task list [--ball H] [--owner H] [--assignee H] [--status S] [--kind K] [--due-before D] [--parent ID]

REF is the task id, or a backlog key (WEB-12) where an item fits. RULE: daily,
weekdays, weekly:mon[,thu…], every:N:days|weeks|months, monthly:15, monthly:last,
monthly:2:tue, yearly:…; the server checks it. A backlog item is not a plain todo:
the server refuses status and assignee writes on it; use the `item` verbs.
"""
from __future__ import annotations

import argparse
from typing import Any

from . import work
from .api import TodoApiError, seg

LIST_FILTERS = ("ball", "owner", "assignee", "status", "kind", "due_before", "parent", "label")


def add(sub) -> None:
    p = sub.add_parser("task", help="plain todos: new, update, done, comment, show, list"
                       ).add_subparsers(dest="verb", required=True)
    n = p.add_parser("new", help="create a todo")
    n.add_argument("--title", required=True)
    _fields(n)
    n.add_argument("--parent", help="parent task id, or an item key (WEB-12)")
    work.add_idem(n)
    u = p.add_parser("update", help="change fields of a todo or case")
    u.add_argument("id")
    u.add_argument("--title")
    _fields(u)
    work.add_rev(u)
    d = p.add_parser("done", help="complete it (a repeating todo rolls to its next date)")
    d.add_argument("id")
    d.add_argument("--children", choices=("close", "keep"),
                   help="a case with open todos: close them too, or keep them open")
    work.add_rev(d)
    c = p.add_parser("comment", help="comment on a todo, case or item (id or key)")
    c.add_argument("id")
    c.add_argument("--text", required=True)
    work.add_rev(c)
    s = p.add_parser("show", help="one task with children, comments, labels")
    s.add_argument("id")
    ls = p.add_parser("list", help="tasks by ball/owner/assignee/status/kind/due (GET /tasks)")
    for f in LIST_FILTERS:
        ls.add_argument("--" + f.replace("_", "-"))


def _fields(p: argparse.ArgumentParser) -> None:
    p.add_argument("--description")
    p.add_argument("--due", help="YYYY-MM-DD")
    p.add_argument("--assignee", help="principal id")
    p.add_argument("--repeat", metavar="RULE", help="daily, weekly:mon, every:2:weeks, … (none = stop repeating)")
    p.add_argument("--repeat-from", choices=("schedule", "completion"),
                   help="the next date counts from the due date (default) or from the completion")


def _set(a: argparse.Namespace) -> dict[str, Any]:
    rule = work.text(a.repeat, "repeat")
    out = {"title": work.text(getattr(a, "title", None), "title"), "description": a.description,
           "due_date": a.due, "assignee_id": a.assignee, "repeat_from": a.repeat_from,
           "repeat_rule": rule if rule != "none" else None}
    keep_null = {"repeat_rule"} if rule == "none" else set()
    return {k: v for k, v in out.items() if v is not None or k in keep_null}


def run(a: argparse.Namespace) -> int:
    c, _ = work.client()
    if a.verb == "new":
        body = {"kind": "todo", **_set(a), "parent_id": work.resolve(c, a.parent) if a.parent else None}
        body["idem_key"] = work.idem(a.idem, "task", body)
        return work.show(c.send("POST", "/tasks", body))
    if a.verb == "list":
        q = {k: getattr(a, k) for k in LIST_FILTERS}
        return work.show(c.get_json("/tasks", q))
    if a.verb == "show":
        if work.KEY.match(a.id):
            return work.show(c.get_json("/items/" + seg(a.id)))
        return work.show(c.get_json(work.task_path(a.id)))
    path = work.task_path(work.resolve(c, a.id))
    if a.verb == "update":
        fields = _set(a)
        if not fields:
            raise work.UsageError("task update needs at least one field to change")
        return work.show(c.send("PATCH", path, {"set": fields,
                                                "expected_rev": work.rev_of(c, path, a.rev)}))
    if a.verb == "done":
        return work.show(c.send("POST", path + "/complete", {
            "expected_rev": work.rev_of(c, path, a.rev), "children": a.children}))
    return comment(c, work.resolve(c, a.id), work.required(a.text, "text"), a.rev)


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
