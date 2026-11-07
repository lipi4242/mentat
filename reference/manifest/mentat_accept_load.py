"""Read an output the way the acceptance checks need it: rows, columns, raw text, or a send plan.

    .csv            header + rows
    .json           a list of objects, {"records"|"rows": [...]}, or a send plan:
                    {"to": [...], "cc": [...], "bcc": [...], "guests": [...],
                     "visibility": "hidden", "guestsCanSeeOtherGuests": false, ...}
    .md / other     the first pipe table, if any; the text is always checked
"""
import csv
import io
import json
import re

PLAN_KEYS = ("to", "cc", "bcc", "guests")
EMAIL = re.compile(r"[^\s<>,;\"']+@[^\s<>,;\"']+")


class Output:
    def __init__(self, text, rows=None, columns=None, plan=None):
        self.text, self.rows, self.columns, self.plan = text, rows or [], columns or [], plan


def _cell(v):
    return "" if v is None else (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))


def _table(objs):
    cols = list(dict.fromkeys(k for o in objs for k in o))
    return [{c: _cell(o.get(c)) for c in cols} for o in objs], cols


def _markdown(text):
    lines = [ln.strip() for ln in text.splitlines()]
    for i in range(len(lines) - 1):
        if lines[i].startswith("|") and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            cols = [c.strip() for c in lines[i].strip("|").split("|")]
            rows = []
            for ln in lines[i + 2:]:
                if not ln.startswith("|"):
                    break
                cells = [c.strip() for c in ln.strip("|").split("|")]
                rows.append(dict(zip(cols, cells + [""] * (len(cols) - len(cells)))))
            return rows, cols
    return [], []


def parse(text, suffix):
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        rows = [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in reader]
        return Output(text, rows, [c.strip() for c in reader.fieldnames or []])
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict) and any(k in data for k in PLAN_KEYS):
            return Output(text, plan=data)
        if isinstance(data, dict):
            data = data.get("records", data.get("rows", []))
        if not (isinstance(data, list) and all(isinstance(o, dict) for o in data)):
            raise ValueError("JSON output must be a list of objects or a send plan")
        return Output(text, *_table(data))
    return Output(text, *_markdown(text))


def read(path):
    """Output, or raises OSError/ValueError when it cannot be read."""
    text = path.read_text(encoding="utf-8")
    return parse(text, path.suffix.lower())


def address(s):
    m = EMAIL.search(s or "")
    return m.group(0).lower() if m else (s or "").strip().lower()


def recipients(plan):
    """(every recipient, those visible to each other or None if the plan says they are hidden)."""
    every = [address(r) for k in PLAN_KEYS for r in plan.get(k) or []]
    if plan.get("visibility") == "hidden":
        return every, None
    if plan.get("guests"):
        # calendar guests see the guest list unless it is switched off explicitly
        return every, (None if plan.get("guestsCanSeeOtherGuests") is False else
                       [address(g) for g in plan["guests"]])
    return every, [address(r) for k in ("to", "cc") for r in plan.get(k) or []]
