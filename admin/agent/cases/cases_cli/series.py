"""Open occurrences and the due window — computed the way the admin computes
them (worker/src/plugins/cases/store.ts), so both backends print the same."""
import occurrence as moved
import recurrence as rec
from common import OPEN, CasesError

DUE_KEYS = ("case_id", "title", "status", "description", "next_action",
            "recurrence", "brain_ref", "due_at", "closable")
OPEN_CAP = 60


def earliest_open(c):
    """due_at of a recurring case: the first series date after the last closed one."""
    if not c.get("recurrence"):
        return c.get("due_at")
    if not rec.parse(c["recurrence"]):
        raise CasesError("%s: unknown recurrence %r" % (c["id"], c["recurrence"]))
    if not rec.is_date(c.get("anchor_at") or "") or not rec.anchor_ok(c["anchor_at"], c["recurrence"]):
        raise CasesError("%s: anchor_at %r is not a date of %s" % (c["id"], c.get("anchor_at"), c["recurrence"]))
    last = max((o["due_at"] for o in c["occurrences"]), default=None)
    return rec.first_open_after(c["anchor_at"], c["recurrence"], last)


def due_of(c, asked, strict=False):
    """due_at as stored: the earliest open date, or `asked` when it moves that one
    later inside its own period. An asked date out of range: refused when strict,
    else (a stale stored one) back to the series date."""
    first = earliest_open(c)
    if not c.get("recurrence") or not asked or asked == first:
        return first
    problem = moved.moved_problem(c["anchor_at"], c["recurrence"], first, asked)
    if problem and strict:
        raise CasesError(problem)
    return first if problem else asked


def open_dates(c, until):
    if not c["due_at"]:
        return []
    if not c["recurrence"]:
        return [c["due_at"]] if c["due_at"] <= until else []
    return moved.open_from(c["anchor_at"], c["recurrence"], c["due_at"], until, OPEN_CAP)


def show_open(c, today):
    """The detail view's open occurrences: up to today or due_at, recurring only."""
    if not c["recurrence"] or c["status"] not in OPEN:
        return []
    return open_dates(c, max(today, c["due_at"] or today))


def due_items(cases, until):
    items = []
    for c in cases:
        if c["status"] in OPEN:
            for i, d in enumerate(open_dates(c, until)):
                items.append(item({**c, "case_id": c["id"], "due_at": d, "closable": i == 0}))
    return sort_items(items)


def item(raw):
    return {k: raw.get(k) for k in DUE_KEYS}


def sort_items(items):
    return sorted(items, key=lambda i: (i["due_at"], i["title"] or "", i["case_id"]))
