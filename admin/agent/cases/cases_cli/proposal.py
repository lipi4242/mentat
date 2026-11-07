"""The post-install proposal (.mentat/cases-proposal.json): which living notes of
the brain should run as cases. The agent writes it (recognition is its job, not
this code's); here only the format is checked.

    {"schema": 1, "items": [{"id": "p1", "source": "<brain>/people/x.md", "title": ..,
      "description": .., "next_action": .., "kind": "one-off", "due_at": "YYYY-MM-DD",
      "reason": ..}, {.., "kind": "recurring", "recurrence": "monthly:5", "anchor_at": ..,
      "own": {"priority": "magas"}}]}

`own` (optional): the admin's own case fields (`cases_cli fields`); on the
markdown backend the values go to the case's `extra`.

The import: proposal_import.py.
"""
import json
import re
from pathlib import Path

import mentat_rules as rules
import recurrence as rec
from common import CasesError

DEFAULT = ".mentat/cases-proposal.json"
TEXT = ("title", "description", "next_action", "reason")
KEYS = {"id", "source", "kind", "due_at", "recurrence", "anchor_at", "own", *TEXT}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load(root, path):
    p = (Path(root) / (path or DEFAULT)).resolve()
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        raise CasesError("no proposal at %s — the agent writes it first (.mentat/cases-propose.md)" % (path or DEFAULT))
    except ValueError as e:
        raise CasesError("%s is not JSON: %s" % (path or DEFAULT, e))
    return doc


def _item(root, brain, it):
    if not isinstance(it, dict):
        return ["an item is not an object"]
    errs = ["unknown key %s" % k for k in sorted(set(it) - KEYS)]
    errs += ["%s must be a non-empty string" % k for k in TEXT
             if not isinstance(it.get(k), str) or not it[k].strip()]
    errs += ["%s must be one line" % k for k in ("title", "next_action")
             if isinstance(it.get(k), str) and "\n" in it[k]]
    src = it.get("source")
    if not (rules.path_inside_repo(src) and str(src).startswith(brain + "/") and (Path(root) / src).is_file()):
        errs.append("source must be an existing note under %s/ (repo-relative): %r" % (brain, src))
    own = it.get("own", {})
    if not (isinstance(own, dict) and all(NAME_RE.match(str(k)) and k not in KEYS
                                          and isinstance(v, (str, int, float, bool)) for k, v in own.items())):
        errs.append("own must map field names to plain values (text, number, true/false)")
    kind = it.get("kind")
    if kind == "one-off":
        if not rec.is_date(it.get("due_at")) or it.get("recurrence") or it.get("anchor_at"):
            errs.append("a one-off has due_at (YYYY-MM-DD) and no recurrence/anchor_at")
    elif kind == "recurring":
        if it.get("due_at") or not rec.parse(it.get("recurrence")):
            errs.append("a recurring item has recurrence (monthly:<1-31>, quarterly:<1-31>, yearly:<MM-DD>,"
                        " weekly:<mon..sun>)"
                        " and no due_at")
        elif not (rec.is_date(it.get("anchor_at")) and rec.anchor_ok(it["anchor_at"], it["recurrence"])):
            errs.append("anchor_at must be the first due date, a date of %s" % it["recurrence"])
    else:
        errs.append("kind must be one-off or recurring, not %r" % kind)
    return errs


def problems(root, brain, doc):
    if not isinstance(doc, dict) or doc.get("schema") != 1 or not isinstance(doc.get("items"), list):
        return ['the proposal must be {"schema": 1, "items": [...]}']
    out, seen = [], set()
    for n, it in enumerate(doc["items"]):
        iid = it.get("id") if isinstance(it, dict) else None
        name = iid if isinstance(iid, str) and ID_RE.match(iid) else "items[%d]" % n
        if name != iid:
            out.append("%s: id must match %s" % (name, ID_RE.pattern))
        elif iid in seen:
            out.append("duplicate id %s" % iid)
        seen.add(iid)
        out += ["%s: %s" % (name, e) for e in _item(root, brain, it)]
    return out


def checked(root, brain, path, then=""):
    doc = load(root, path)
    errs = problems(root, brain, doc)
    if errs:
        raise CasesError("the proposal is not valid%s:\n  %s" % (then, "\n  ".join(errs)))
    return doc["items"]


def check(root, brain, path):
    return "ok: %d items in %s" % (len(checked(root, brain, path)), path or DEFAULT), 0
