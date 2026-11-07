"""Shared pieces: the case shape every backend returns, errors, ids, dates."""
import os
import re
import time
import unicodedata

# The plugin's tracked fields (the brain template's frontmatter names).
KEYS = ("id", "title", "description", "status", "next_action", "due_at", "recurrence",
        "anchor_at", "brain_ref")
TEXT = ("title", "description", "next_action")
TRACKED = ("title", "description", "status", "next_action", "due_at", "recurrence",
           "anchor_at", "occurrences", "extra")
# Dropped from the base model (admin migration 0202): an older file's value is
# kept, in extra under the same key — never silently lost.
LEGACY = ("waiting_on", "category")
STATUSES = ("open", "waiting", "done", "dropped")
OPEN = ("open", "waiting")
ULID_RE = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class CasesError(Exception):
    """A refusal the agent can act on: exit 1."""
    code = 1


class Unavailable(CasesError):
    """The chosen backend cannot be reached: exit 3, nothing written."""
    code = 3


class Diagnostic(CasesError):
    """The manifest cannot be acted on (unknown schema, unreadable): exit 2."""
    code = 2


class NotFound(CasesError):
    pass


def ulid():
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(CROCKFORD[(n >> 5 * i) & 31] for i in range(25, -1, -1))


def slug(title):
    flat = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", flat.lower()).strip("-")[:48] or "ugy"


def case(raw, own=(), **over):
    """The common shape: KEYS, occurrences (closed, oldest first), extra, and
    `own` — the instance's own fields the admin declares (GET /api/meta)."""
    out = {k: raw.get(k) for k in KEYS}
    out.update(over)
    for k in TEXT:
        if out[k] is not None:
            out[k] = str(out[k])
    out["status"] = out["status"] or "open"
    out["occurrences"] = sorted((occurrence(o) for o in raw.get("occurrences") or []),
                                key=lambda o: o["due_at"])
    out["extra"] = dict(raw.get("extra")) if isinstance(raw.get("extra"), dict) else {}
    for k in LEGACY:
        if raw.get(k) is not None:
            out["extra"].setdefault(k, str(raw[k]))
    out["own"] = {k: raw.get(k) for k in own}
    return out


def occurrence(o):
    return {"due_at": str(o.get("due_at")), "status": o.get("status") or "done",
            "done_at": None if o.get("done_at") is None else str(o.get("done_at")),
            "note": None if o.get("note") is None else str(o.get("note"))}


def sort_cases(rows):
    return sorted(rows, key=lambda r: (r["due_at"] is None, r["due_at"] or "", r["title"] or "", r["id"]))


def statuses(arg):
    if arg == "all":
        return list(STATUSES)
    want = [s for s in (arg or "open,waiting").split(",") if s]
    bad = [s for s in want if s not in STATUSES]
    if bad:
        raise CasesError("unknown status: %s (%s | all)" % (", ".join(bad), " | ".join(STATUSES)))
    return want
