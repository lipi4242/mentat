"""cases sync (admin mode): the admin <-> markdown mirror.

  up    each case file's body (its context) when its hash differs from the admin's
  down  the admin's change feed after the cursor (.mentat/cases-sync.json):
        what a person changed is printed for the agent; nothing is written
        into the brain from it
  check a case file whose frontmatter still carries tracked fields that
        disagree with the admin is a conflict: reported, never overwritten
        (exit 1); so is a case file the admin does not know, or an admin case
        whose brain file is missing
"""
import hashlib
import json
from pathlib import Path

import adminstore
import fmwrite
import mdstore
from common import TRACKED, case

CURSOR = Path(".mentat") / "cases-sync.json"


def _differs(fm, row):
    want = case(row)
    have = case(fm)
    out = []
    for k in TRACKED:
        if k not in fm:
            continue
        a, b = have[k], want[k]
        if k == "occurrences":
            a, b = [o["due_at"] for o in a], [o["due_at"] for o in b]
        if a != b:
            out.append(k)
    return out


def _up(admin, root, brain, rows, problems):
    sent = same = 0
    for path, fm, text in mdstore.scan(root, brain):
        rel = path.relative_to(root).as_posix()
        cid = fm.get("case_id")
        if not cid:
            problems.append("no case_id: %s — run `cases migrate --to admin`" % rel)
            continue
        if cid not in rows:
            problems.append("not in the admin: %s (%s)" % (rel, cid))
            continue
        clash = _differs(fm, admin.raw(cid)) if any(k in fm for k in TRACKED) else []
        if clash:
            problems.append("conflict: %s — the frontmatter's %s disagree(s) with the admin; not "
                            "overwritten (fix the file, or change it with `cases update`)" % (rel, ", ".join(clash)))
            continue
        ctx = fmwrite.context(text)
        if hashlib.sha256(ctx.encode()).hexdigest() == rows[cid].get("context_hash"):
            same += 1
            continue
        admin.put_raw(cid, {"context": ctx})
        sent += 1
    for cid, r in rows.items():
        if r.get("brain_ref") and not (root / r["brain_ref"]).is_file():
            problems.append("brain file missing: %s (%s, %s)" % (r["brain_ref"], r["title"], cid))
    return "context: %d uploaded, %d unchanged" % (sent, same)


def _down(admin, root, rows):
    path = root / CURSOR
    try:
        after = int(json.loads(path.read_text()).get("after", 0))
    except (OSError, ValueError, AttributeError):
        after = 0
    lines, machine = [], 0
    while True:
        batch = admin._ok(*admin.call("GET", "/api/cases/events?after=%d&limit=500" % after))
        for e in batch:
            after = e["id"]
            if e["actor"] != "user":
                machine += 1
                continue
            title = (rows.get(e["case_id"]) or {}).get("title", e["case_id"])
            lines.append("  %s  user %s %s  %s  %s" % (e["at"], e["kind"], title, e["body"], e["case_id"]))
        if len(batch) < 500:
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    mdstore.write(path, json.dumps({"after": after}) + "\n")
    head = "events: %d by a person, %d by agents" % (len(lines), machine)
    return "\n".join([head] + lines)


def run(root, brain, backend):
    if backend != "admin":
        return "nothing to sync: cases.backend is markdown (the files are the record)", 0
    admin = adminstore.Admin(root, brain)
    rows = {r["id"]: r for r in admin.list_raw(["open", "waiting", "done", "dropped"])}
    problems = []
    out = [_up(admin, root, brain, rows, problems), _down(admin, root, rows)]
    out += problems
    return "\n".join(out), 1 if problems else 0
