"""A moved open occurrence (mérés 11): the earliest open date of a series may be
moved later inside its own period — October due on the 20th of a monthly:10
series — so a first month with its own date stays in the series instead of
becoming a separate one-off case. The same rules as the worker
(worker/src/plugins/cases/recurrence.ts slotOf/movedDueProblem, close.ts).

Closed occurrences are always stored by their series date; the moved date is
only the open occurrence's due_at.
"""
from datetime import date, timedelta

from recurrence import MAX_STEPS, _clamped, between, first_open_after, nth, on_series, parse

def slot_of(anchor, rule, d):
    """The series date whose period holds d: the latest one on or before it; None before the anchor."""
    slot = None
    for k in range(MAX_STEPS):
        x = nth(anchor, rule, k)
        if x > d:
            return slot
        slot = x
    raise ValueError("recurrence runs past its step limit")


def moved_problem(anchor, rule, slot, due):
    """Why `due` cannot be the date of the open occurrence `slot`, or None."""
    nxt = first_open_after(anchor, rule, slot)
    if slot <= due < nxt:
        return None
    return ("due_at must be from %s to before %s — the earliest open occurrence (%s) of this "
            "recurring case, moved at most within its own period" % (slot, nxt, slot))


def open_from(anchor, rule, due, until, cap=60):
    """Open dates from the (possibly moved) earliest open one up to `until`."""
    rest = between(anchor, rule, due, until, cap)
    if on_series(anchor, rule, due):
        return rest
    return [due] + rest[:cap - 1] if due <= until else []


def anchor_for(rule, d):
    """Where a series that is first due on `d` is anchored: d itself when it is on
    the rule, else the rule's date just before it (d is then the moved first date)."""
    kind, arg = parse(rule)
    x = date.fromisoformat(d)
    if kind == "weekly":
        return (x - timedelta(days=(x.weekday() - arg) % 7)).isoformat()
    if kind == "yearly":
        c = _clamped(x.year, *arg)
        return (c if c <= x else _clamped(x.year - 1, *arg)).isoformat()
    c = _clamped(x.year, x.month, arg)
    if c > x:
        y, m = (x.year - 1, 12) if x.month == 1 else (x.year, x.month - 1)
        c = _clamped(y, m, arg)
    return c.isoformat()


def close_slot(anchor, rule, open_due, day, closed):
    """Which series date a close of `day` writes: ("already", slot) | ("off", msg) |
    ("later", None) | ("ok", slot). `open_due` is the case's due_at, `closed` the closed dates."""
    slot = slot_of(anchor, rule, day)
    if slot and slot in closed:
        return "already", slot
    if not on_series(anchor, rule, day) and day != open_due:
        return "off", "%s is not a date of the series %s from %s, nor the open one (%s)" % (
            day, rule, anchor, open_due)
    if not slot or not open_due or slot != slot_of(anchor, rule, open_due):
        return "later", None
    return "ok", slot
