"""Anchored recurrence — the same rules as the admin worker
(worker/src/plugins/cases/recurrence.ts) and the engine's cases pack.

    monthly:<1-31> | quarterly:<1-31> | yearly:<MM-DD> | weekly:<mon..sun>

A quarterly series steps three months; its phase is the anchor's month.

The k-th date is anchor + k steps. A day the month lacks (the 31st, 29 Feb)
falls on that month's last day, and the next month goes back to the asked-for
day: every date is derived from the anchor, never from the previous date.
"""
import calendar
import re
from datetime import date, timedelta

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_STEPS = 20000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_date(v):
    if not isinstance(v, str) or not DATE_RE.match(v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def parse(rule):
    """(kind, arg) or None when the rule is not in the v1 set."""
    if not isinstance(rule, str):
        return None
    m = re.match(r"^(monthly|quarterly):([1-9]|[12]\d|3[01])$", rule)
    if m:
        return m.group(1), int(m.group(2))
    m = re.match(r"^yearly:(\d{2})-(\d{2})$", rule)
    if m:
        try:
            date(2028, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        return "yearly", (int(m.group(1)), int(m.group(2)))
    m = re.match(r"^weekly:(mon|tue|wed|thu|fri|sat|sun)$", rule)
    return ("weekly", WEEKDAYS.index(m.group(1))) if m else None


def _clamped(y, m, d):
    return date(y, m, min(d, calendar.monthrange(y, m)[1]))


def nth(anchor, rule, k):
    kind, arg = parse(rule)
    a = date.fromisoformat(anchor)
    if kind == "weekly":
        return (a + timedelta(days=7 * k)).isoformat()
    if kind == "yearly":
        return _clamped(a.year + k, arg[0], arg[1]).isoformat()
    months = a.month - 1 + (3 * k if kind == "quarterly" else k)
    return _clamped(a.year + months // 12, months % 12 + 1, arg).isoformat()


def anchor_ok(anchor, rule):
    kind, arg = parse(rule)
    a = date.fromisoformat(anchor)
    if kind == "weekly":
        return a.weekday() == arg
    if kind in ("monthly", "quarterly"):
        return _clamped(a.year, a.month, arg) == a
    return _clamped(a.year, arg[0], arg[1]) == a


def first_open_after(anchor, rule, after):
    if after is None:
        return anchor
    for k in range(MAX_STEPS):
        d = nth(anchor, rule, k)
        if d > after:
            return d
    raise ValueError("recurrence runs past its step limit")


def between(anchor, rule, start, until, cap=60):
    out = []
    for k in range(MAX_STEPS):
        d = nth(anchor, rule, k)
        if d > until or len(out) >= cap:
            break
        if d >= start:
            out.append(d)
    return out


def on_series(anchor, rule, d):
    return between(anchor, rule, d, d, 1) == [d]
