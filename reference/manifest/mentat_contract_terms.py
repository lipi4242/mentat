"""The terms of a task contract: validation, the derived checks, material changes, the digest.

Pure functions, no I/O. The terms (all optional except `goal`):
    goal      one sentence: what the work is for
    fields    the output's columns, exactly
    exclude   {"fields": [...], "records": [{field: value}, ...], "values": [text, ...]}
    audience  {"who": text, "allowed": [address or @domain], "from_records": field, "visibility": "hidden"|"visible"}
    window    {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "tz": "Area/City", "field": column}
    defaults  {field: value} for new rows
    records   {"source": relative path, "key": column, "where": {field: value or [values]}}
    checks    the acceptance checks; derived from the rest when left out
    notes     free text; the only key whose change is not material
"""
import datetime
import hashlib
import json
import re

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KEYS = ("goal", "fields", "exclude", "audience", "window", "defaults", "records", "checks", "notes")
CHECKS = ("fields_exact", "no_excluded", "within_window", "exact_records", "recipients_allowed",
          "visibility_hidden")
NOT_MATERIAL = ("notes",)
DAY = re.compile(r"\d{4}-\d\d-\d\d$")


def _strs(v):
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)


def _window(w):
    errs = []
    for k in ("start", "end"):
        if not (isinstance(w.get(k), str) and DAY.match(w[k])):
            errs.append("window.%s must be an absolute date YYYY-MM-DD (not %r): resolve it with mentat_dates.py and ask the USER" % (k, w.get(k)))
    if not errs:
        try:
            if datetime.date.fromisoformat(w["start"]) > datetime.date.fromisoformat(w["end"]):
                errs.append("window.start is after window.end")
        except ValueError as e:
            errs.append("window: %s" % e)
    if not isinstance(w.get("tz"), str) or not w["tz"]:
        errs.append("window.tz is required (e.g. Europe/Budapest)")
    else:
        try:
            ZoneInfo(w["tz"])
        except (ZoneInfoNotFoundError, ValueError):
            errs.append("window.tz is not a known time zone: %r" % w["tz"])
    return errs


def validate(t):
    """A list of problems; empty = the terms can be drafted."""
    if not isinstance(t, dict):
        return ["the proposal must be a JSON object"]
    errs = ["unknown key: %s" % k for k in t if k not in KEYS]
    goal = t.get("goal")
    if not (isinstance(goal, str) and goal.strip() and "\n" not in goal.strip()):
        errs.append("goal: one sentence is required")
    if "fields" in t and not _strs(t["fields"]):
        errs.append("fields must be a list of column names")
    ex = t.get("exclude", {})
    if not isinstance(ex, dict) or any(k not in ("fields", "records", "values") for k in ex):
        errs.append("exclude takes fields, records, values")
    elif not all(isinstance(r, dict) and r for r in ex.get("records", [])):
        errs.append("exclude.records must be a list of {field: value} objects")
    au = t.get("audience", {})
    if not isinstance(au, dict) or au.get("visibility") not in (None, "hidden", "visible"):
        errs.append("audience.visibility must be hidden or visible")
    elif au.get("from_records") and not t.get("records"):
        errs.append("audience.from_records needs records (the source list)")
    if "window" in t:
        errs += _window(t["window"]) if isinstance(t["window"], dict) else ["window must be an object"]
    rec = t.get("records")
    if rec is not None:
        src = rec.get("source", "") if isinstance(rec, dict) else ""
        if not (isinstance(src, str) and src and not src.startswith("/") and ".." not in src.split("/")):
            errs.append("records.source must be a relative path inside the folder")
        elif not rec.get("key"):
            errs.append("records.key (the column that identifies a record) is required")
    bad = [c for c in t.get("checks", []) if c not in CHECKS]
    if bad:
        errs.append("unknown checks: %s (known: %s)" % (", ".join(bad), ", ".join(CHECKS)))
    return errs


def derive_checks(t):
    """The checks the rest of the terms imply."""
    au, out = t.get("audience") or {}, []
    for name, on in (("fields_exact", t.get("fields")), ("no_excluded", t.get("exclude")),
                     ("within_window", (t.get("window") or {}).get("field")),
                     ("exact_records", t.get("records")),
                     ("recipients_allowed", au.get("allowed") or au.get("from_records")),
                     ("visibility_hidden", au.get("visibility") == "hidden")):
        if on:
            out.append(name)
    return out


def normalize(t):
    t = dict(t)
    t.setdefault("checks", derive_checks(t))
    return t


def material(old, new):
    """The keys whose change needs a new approval."""
    keys = set(old) | set(new)
    return sorted(k for k in keys if k not in NOT_MATERIAL and old.get(k) != new.get(k))


def digest(t):
    core = {k: v for k, v in t.items() if k not in NOT_MATERIAL}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
