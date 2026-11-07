"""Concern `todo_labda` ("whose ball is it"): the work store has something for me.

Hourly. Plans only when there are events for me after my cursor (feed.py), or
when a backlog item was issued to me and I have not taken it yet. Otherwise:
silence, no plan entry. Never a timer, never a nudge to anyone else.

Provider `todo.labda`: {configured, status, pending, issued, review_due}. The
review-due cases ride along when the concern runs; alone they do not plan it.
Errors stay quiet here: `todo_esedekes` already reports a todo API outage, and
while its backoff holds this concern does not call the API at all.
"""
from __future__ import annotations

import sys
from typing import Any

from anytime_engine import clock, config
from anytime_engine.assembler import register_provider
from anytime_engine.prompts import action, format_context
from anytime_engine.registry import Concern, register

from . import due, feed, settings
from .api import Client, TodoApiError


def compute(state) -> dict[str, Any]:
    memo = getattr(state, "_labda_memo", None)
    if memo and memo[0] == state.now():
        return memo[1]
    result = _compute(state)
    state._labda_memo = (state.now(), result)
    return result


def _compute(state) -> dict[str, Any]:
    s = settings.load(config.repo_root().resolve())
    if s is None:
        return {"configured": False}
    h = state.cache.get(due.HEALTH) or {}
    if h.get("retry_at") and state.now() < clock.parse(h["retry_at"]):
        return {"configured": True, "status": "error", "error": "todo API in backoff"}
    try:
        c = Client(s.api, s.token())
        pending = feed.pending(c, s.handle)
        issued = c.get_json("/items", {"stage": "issued", "ball": s.handle})
        review = c.get_json("/cases/review-due", {"for": s.handle})
    except (TodoApiError, settings.TodoConfigError, feed.CursorError) as e:
        print(f"[anytime_todo] todo_labda skipped: {e}", file=sys.stderr)
        return {"configured": True, "status": "error", "error": str(e)}
    pick = ("id", "key", "title", "stage", "rev")
    return {"configured": True, "status": "ok", "handle": s.handle, "pending": pending,
            "issued": [{k: i.get(k) for k in pick} for i in issued if isinstance(i, dict)]
            if isinstance(issued, list) else [],
            "review_due": [{k: t.get(k) for k in ("id", "title", "rev")} for t in review
                           if isinstance(t, dict)] if isinstance(review, list) else []}


def should_run(state) -> bool:
    try:
        r = compute(state)
    except Exception as e:   # noqa: BLE001 — a pack must not break the tick
        print(f"[anytime_todo] todo_labda skipped: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    return r.get("status") == "ok" and bool(r["pending"] or r["issued"])


register_provider("todo.labda", compute)

register(Concern(
    name="todo_labda",
    description="The work store has something for me: new events, or an item issued to me.",
    triggers=["hourly"], should_run=should_run, context_needs=["todo.labda"],
    action="todo_labda", staleness_minutes=60))

CLI = "python3 -m anytime_todo.cli"

_RULES = f"""Follow the `backlog` skill. In order:

1. `{CLI} changes` lists the events for you after your cursor (oldest first).
   Handle each one: answer a question or a mention with `task comment`; act on
   what is now yours (`{CLI} ball` shows everything whose ball is yours).
2. ONLY after the events up to a seq are handled: `{CLI} changes --ack <seq>`
   (usually the `last_seq` it printed). If `more` was true, run `changes` again.
   Never ack what you have not handled; a crash before the ack just repeats.
3. `issued` — items issued to you as the developer. When you start:
   `{CLI} item take <key>`. Cannot or should not do it: `{CLI} item handback <key>
   --note "<why>"`. Do not leave it issued without a word.
4. `review_due` — your monitored cases whose review is due: look at each, act on
   its next_action, then `{CLI} case review <id> --note "<what you saw>"`.

You never write as a person, and you never chase anyone on a timer."""


@action("todo_labda")
def todo_labda_prompt(ctx: dict[str, Any]) -> str:
    data = ctx.get("todo.labda") or ctx
    return "# Whose ball is it (todo + backlog)\n\n" + _RULES + "\n\n" + format_context(data)
