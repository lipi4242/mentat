"""The acceptance checks: each takes (terms, output, source) and returns problems.

A problem is (key, [items]); mentat_accept.py turns it into one sentence for the USER.
Add a check = one function here + its name in mentat_contract_terms.CHECKS.
"""
import datetime
from zoneinfo import ZoneInfo

import mentat_accept_load as load


def match(row, where):
    return all((row.get(k, "") in [str(x) for x in v]) if isinstance(v, list) else row.get(k, "") == str(v)
               for k, v in where.items())


def local_day(value, tz):
    """The calendar day of a date or timestamp in the contract's time zone; None if unreadable."""
    v = (value or "").strip()
    try:
        if len(v) == 10:
            return datetime.date.fromisoformat(v)
        dt = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt.astimezone(ZoneInfo(tz)) if dt.tzinfo else dt).date()


def outside(terms, value):
    """None = inside the window; else the problem key."""
    w = terms["window"]
    day = local_day(value, w["tz"])
    if day is None:
        return "bad_date"
    inside = datetime.date.fromisoformat(w["start"]) <= day <= datetime.date.fromisoformat(w["end"])
    return None if inside else "outside"


class Source:
    """The source list the contract names, read once, filtered by `where` and the window."""

    def __init__(self, root, terms):
        self.terms, self.rec = terms, terms.get("records")
        self.rows = load.read(root / self.rec["source"]).rows if self.rec else []

    def eligible(self):
        w, out = self.terms.get("window") or {}, []
        for r in self.rows:
            if not match(r, self.rec.get("where") or {}):
                continue
            if w.get("field") in r and outside(self.terms, r[w["field"]]):
                continue
            out.append(r)
        return out

    def keys(self, rows):
        return [r.get(self.rec["key"], "").strip().lower() for r in rows]


def fields_exact(t, out, src):
    if not out.columns:
        return [("no_columns", [])]
    want, got = t["fields"], out.columns
    return [p for p in (("extra_col", [c for c in got if c not in want]),
                        ("missing_col", [c for c in want if c not in got])) if p[1]]


def no_excluded(t, out, src):
    ex = t.get("exclude") or {}
    conds = ex.get("records", [])
    banned = set(src.keys([r for r in src.rows if any(match(r, w) for w in conds)])) if src.rec else set()
    hit = []
    for r in out.rows:
        direct = any(set(w) <= set(r) and match(r, w) for w in conds)
        if direct or (src.rec and src.keys([r])[0] in banned):
            hit.append(src.keys([r])[0] if src.rec else next(iter(r.values()), ""))
    probs = [("excl_col", [c for c in out.columns if c in ex.get("fields", [])]),
             ("excl_rec", hit),
             ("excl_val", [v for v in ex.get("values", []) if v.lower() in out.text.lower()])]
    return [p for p in probs if p[1]]


def within_window(t, out, src):
    field, probs = t["window"]["field"], {"outside": [], "bad_date": []}
    for r in out.rows:
        if field in r:
            key = outside(t, r[field])
            if key:
                probs[key].append(r[field])
    return [(k, v) for k, v in probs.items() if v]


def exact_records(t, out, src):
    key = src.rec["key"]
    if key not in out.columns:
        return [("missing_col", [key])]
    got, want = src.keys(out.rows), src.keys(src.eligible())
    dup = sorted({k for k in got if got.count(k) > 1})
    return [p for p in (("missing_rec", [k for k in want if k not in got]),
                        ("extra_rec", [k for k in dict.fromkeys(got) if k not in want]),
                        ("dup_rec", dup)) if p[1]]


def allowed_set(t, src):
    au = t.get("audience") or {}
    allowed = {a.lower() for a in au.get("allowed", [])}
    if au.get("from_records"):
        allowed |= {load.address(r.get(au["from_records"], "")) for r in src.eligible()}
    return allowed


def strangers(t, src, people):
    allowed = allowed_set(t, src)
    return [p for p in dict.fromkeys(people)
            if p not in allowed and "@" + p.split("@")[-1] not in allowed]


def recipients_allowed(t, out, src, people):
    bad = strangers(t, src, people)
    return [("stranger", bad)] if bad else []


def visibility_hidden(t, out, src, visible):
    return [("visible", visible)] if visible is not None and len(visible) > 1 else []


TABLE = {"fields_exact": fields_exact, "no_excluded": no_excluded, "within_window": within_window,
         "exact_records": exact_records}
