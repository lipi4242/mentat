"""setup: the first `components.engine.todo_trusted` list — who may create a duty this agent just does.

The agent itself, the owner's principal id when it is known (`--todo-owner p_krisz` or
$ANYTIME_TODO_OWNER), and the agent's own PM when it has one (`--todo-pm p_paul` or $ANYTIME_TODO_PM).
An existing list, even a hand-extended or empty one, is never rewritten: only the ids given
EXPLICITLY on the command line (`explicit`) that are missing from it are added, at the end. Nothing
is removed or reordered, and the environment alone never extends an existing list.
Once a list exists, an item created by anyone else is notification-only (anytime_todo.due).
"""
from __future__ import annotations

import os
from typing import Any, Iterable

HINT = ("todo_trusted: only this agent is listed, so duties created by anyone else (the owner included) "
        "are reported, not done. Add the owner: re-run setup with --todo-owner <their principal id, "
        "e.g. p_krisz> (and --todo-pm <the agent's PM> if it has one), or edit "
        "components.engine.todo_trusted in mentat.json")


def owner_of(arg: str | None) -> str | None:
    return (arg or os.environ.get("ANYTIME_TODO_OWNER") or "").strip() or None


def pm_of(arg: str | None) -> str | None:
    return (arg or os.environ.get("ANYTIME_TODO_PM") or "").strip() or None


def seed(section: dict[str, Any], manifest: dict[str, Any] | None, owner: str | None,
         pm: str | None = None, explicit: Iterable[str | None] = ()) -> list[str] | None:
    """The list to record, or None: nothing to change (an existing list with nothing explicit
    missing from it), or the agent's handle is unknown."""
    if "todo_trusted" in section:
        have = list(section["todo_trusted"] or [])
        new = [x for x in dict.fromkeys(e.strip() for e in explicit if e and e.strip()) if x not in have]
        return have + new if new else None
    handle = (os.environ.get("TODO_HANDLE") or section.get("todo_handle")
              or ((manifest or {}).get("agent") or {}).get("name"))
    if not handle:
        return None
    return list(dict.fromkeys([str(handle)] + [x for x in (owner, pm) if x]))
