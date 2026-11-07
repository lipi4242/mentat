"""What the commands print — one format whichever backend answered."""
import json
from datetime import date

import series
from common import KEYS


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def list_json(rows):
    return dump([{**{k: r[k] for k in KEYS}, **r.get("own", {})} for r in rows])


def list_text(rows):
    if not rows:
        return "no cases"
    return "\n".join("%-10s  %-7s  %s%s  %s" % (r["due_at"] or "-", r["status"], r["title"],
                                                "  [%s]" % r["recurrence"] if r["recurrence"] else "", r["id"])
                     for r in rows)


def _when(d, today):
    days = (date.fromisoformat(d) - date.fromisoformat(today)).days
    return "overdue" if days < 0 else "today" if days == 0 else "in %dd" % days


def due_text(items, today):
    if not items:
        return "nothing due"
    return "\n".join("%s  %-9s  %s%s%s  %s" % (
        i["due_at"], _when(i["due_at"], today), i["title"],
        " — " + i["next_action"] if i["next_action"] else "",
        "  (after the earlier date)" if not i["closable"] else "", i["case_id"]) for i in items)


def detail(c, today):
    out = {k: c[k] for k in KEYS}
    out.update(c.get("own") or {})
    out.update(occurrences=c["occurrences"], open_occurrences=series.show_open(c, today),
               extra=c["extra"], context=c.get("context") or "")
    return out


def show_text(d):
    own = [k for k in d if k not in KEYS and k not in ("occurrences", "open_occurrences", "extra", "context")]
    lines = ["%s: %s" % (k, d[k]) for k in (*KEYS, *own) if d[k] is not None]
    lines += ["closed: %s %s%s%s" % (o["due_at"], o["status"], " " + o["done_at"] if o["done_at"] else "",
                                     " — " + o["note"] if o["note"] else "") for o in d["occurrences"]]
    if d["open_occurrences"]:
        lines.append("open: " + ", ".join(d["open_occurrences"]))
    if d["extra"]:
        lines.append("extra: " + json.dumps(d["extra"], ensure_ascii=False))
    if d["context"]:
        lines += ["--- context ---", d["context"].rstrip("\n")]
    return "\n".join(lines)


def fields_text(fields):
    """The admin's own case fields (GET /api/meta), one per line."""
    if not fields:
        return "no own case fields — the admin declares none (config/models.json fields.cases)"
    def kind(f):
        extra = "|".join(f.get("options") or []) or f.get("ref") or ""
        return "%s: %s" % (f["type"], extra) if extra else f["type"]
    return "\n".join("%-16s %-28s %s%s" % (f["name"], kind(f), f.get("label", ""),
                                           "  (pending migration)" if f.get("pending") else "") for f in fields)
