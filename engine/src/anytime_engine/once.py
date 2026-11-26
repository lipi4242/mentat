"""once — `tick --once`, the session-start fallback where no scheduler ticks.

A desktop without the schedule installed (or a Mac that slept through it) gets one
tick when a session starts: only if no scheduled tick landed in the last hour, under
the tick lock, without the recorded executor (the session is the executor), and it
does not write last-tick.json (that stamp means a scheduler ticked). What it prints
is the work for the session: each planned action's prompt with its context.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from . import clock, config
from .prompts import get_prompt

FRESH = timedelta(hours=1)


def scheduled_at() -> str | None:
    """The `at` of a scheduled tick that landed within the hour and left nothing unhandled
    (route.py: e.g. the todo actions a desktop's deliverer cannot take), else None."""
    try:
        last = json.loads(config.last_tick_path().read_text())
        at = last["at"]
        if last.get("unhandled"):
            return None
        return at if clock.now() - clock.parse(at) < FRESH else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def brief(plan: dict[str, Any], what: str = "Engine tick at session start") -> str:
    """The planned actions as the reader (the session, a model) takes them: each action's
    @action prompt with its data, nothing of the plan's bookkeeping. Empty: nothing to do."""
    parts = [f"## {a['concern']}\n\n{get_prompt(a['action'], a['context'])}"
             for a in plan.get("actions", [])]
    if not parts:
        return ""
    head = (f"# {what} ({len(parts)} action(s)); when one is done: "
            "python3 -m anytime_engine.tick --mark <concern>")
    return "\n\n".join([head] + parts)
