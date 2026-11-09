"""`me`, `ball`, `changes [--ack SEQ] [--all]`, `project list` — who I am, what is on me, what changed.

    me                 my principal (from the token: the token IS the actor)
    ball               every open task, case and item whose ball is mine; each row gets
                       `overdue` (true: its due date passed, or today's due time did, in the
                       row's tz), and the overdue rows come first (otherwise the server's order)
    changes            the events for me after the cursor (JSON; `last_seq`, `more`, and
                       `ack_command`: the exact command to run once every event shown is handled)
    changes --ack SEQ  after handling the events up to SEQ: move the cursor there
    ack REF [--note T] "seen, nothing to do" on a task/item (id or PREFIX-N): one comment starting
                       with ACK_MARK. The bridge's todo wake-up counts it as the receipt, and it wakes
                       nobody (fleet/bridge/lib/todo-relevance.mjs skips it).

Reading never moves the cursor (feed.py), so an event is never lost to a crash.

`changes` shows only others' writes (`own_skipped` counts mine, `--all` shows them;
`last_seq` still covers them, so the ack steps over), says `acked` and `ack_with`;
`changes --ack` answers JSON. `project list`: the backlog projects (11-08 terep).
`ball` leaves out my own draft items (unissued work is not a ball); `ball --drafts`
shows them too (or: `item list --stage draft --pm <me>`).
"""
from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from anytime_engine import clock

from . import cli_task, feed, occurrence, work

ACK_MARK = "[ack]"
KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,7}-\d+$")
CLI = "python3 -m anytime_todo.cli"
CHANGES_HELP = ("Reading never moves the cursor: the same events come back until you ack. WHEN: after you "
                "handled (answered, did, or decided to skip) every event shown. HOW: run the `ack_command` "
                f"of the output, i.e. `{CLI} changes --ack <last_seq>`. `{CLI} ack <id|KEY>` is something "
                "else: the receipt for one task's wake-up when there is nothing to do.")


def add(sub) -> None:
    sub.add_parser("project", help="backlog projects").add_subparsers(dest="verb", required=True) \
        .add_parser("list", help="every project (GET /projects)")
    sub.add_parser("me", help="my principal")
    sub.add_parser("ball", help="everything whose ball is mine, overdue first (`overdue`; not my drafts: --drafts)") \
        .add_argument("--drafts", action="store_true", help="also my draft items (unissued)")
    ch = sub.add_parser("changes", help="events for me after the cursor; ack with `changes --ack <last_seq>`",
                        description=CHANGES_HELP)
    ch.add_argument("--all", action="store_true", help="include my own writes")
    ch.add_argument("--ack", type=int, metavar="SEQ", help="handled up to SEQ: move the cursor")
    ak = sub.add_parser("ack", help="seen, nothing to do: the receipt for a todo wake-up")
    ak.add_argument("ref", help="task id or backlog key (PREFIX-N)")
    ak.add_argument("--note", help="why there is nothing to do (optional)")


def run(a: argparse.Namespace) -> int:
    if a.cmd == "changes" and a.ack is not None:
        _, s = work.client()
        feed.ack(s.api, s.handle, a.ack)
        return work.show({"handle": s.handle, "acked": a.ack})
    c, s = work.client()
    if a.cmd == "ack":
        tid = a.ref.removeprefix("task:")  # a [Todo | task:<id> | …] sor alakja is megy
        if KEY.match(a.ref):
            item = c.get_json("/items/" + a.ref.upper())
            tid = item.get("id") if isinstance(item, dict) else None
            if not tid:
                raise work.UsageError(f"no item {a.ref}")
        note = work.text(a.note, "note")
        return cli_task.comment(c, tid, f"{ACK_MARK} láttam, nincs teendő" + (f": {note}" if note else ""), None)
    if a.cmd == "me":
        return work.show(c.get_json("/me"))
    if a.cmd == "ball":
        rows = c.get_json("/tasks", {"ball": s.handle, "status": "open", "kind": "all"})
        if a.drafts or not isinstance(rows, list):
            return work.show(_by_overdue(rows))
        drafts = c.get_json("/items", {"stage": "draft", "ball": s.handle})
        skip = {d.get("id") for d in drafts} if isinstance(drafts, list) else set()
        return work.show(_by_overdue([r for r in rows if r.get("id") not in skip]))
    if a.cmd == "project":
        return work.show(c.get_json("/projects"))
    out = feed.read(c, s.handle, include_own=a.all)
    if isinstance(out, dict):
        out["ack_command"] = f"{CLI} {out['ack_with']}" if out.get("ack_with") else None
        out["ack_when"] = CHANGES_HELP
    return work.show(out)


def overdue(row: Any, now_utc: datetime) -> bool:
    """Past its due date, or today with its due time reached (the row's tz). Today without a
    time is due, not overdue. An unreadable date or zone is not overdue (the row still shows)."""
    if not isinstance(row, dict):
        return False
    try:
        if not occurrence.is_due(row, now_utc):
            return False
        local = now_utc.astimezone(ZoneInfo(row.get("tz") or occurrence.DEFAULT_TZ)).date()
        return local > date.fromisoformat(str(row["due_date"])) or bool(row.get("due_time"))
    except (ValueError, ZoneInfoNotFoundError):
        return False


def _by_overdue(rows: Any) -> Any:
    """Every row gets `overdue`; the overdue ones first, the rest in the server's order."""
    if not isinstance(rows, list):
        return rows
    now = clock._utcnow()
    out = [{**r, "overdue": overdue(r, now)} if isinstance(r, dict) else r for r in rows]
    return sorted(out, key=lambda r: not (isinstance(r, dict) and r["overdue"]))
