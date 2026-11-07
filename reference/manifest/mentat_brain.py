#!/usr/bin/env python3
"""Notes in one call: create from the template, list what is due, search.

    python3 mentat_brain.py new case|person|todo|decision|brain-dump|connector "Title" \
        [--due YYYY-MM-DD] [--tags a,b] [--body TEXT|-]     # prints the new file's path
    python3 mentat_brain.py due [--days 7] [--all] [--full]  # overdue + due soon; 8 lines, --full = all
    python3 mentat_brain.py find WORD [WORD...] [--limit 12]  # file + one line each (+ [due ...])
    python3 mentat_brain.py mv OLD [NEW] [--title T]        # rename + fix links and the _meta index
    python3 mentat_brain.py commit "message"                # git add + commit the brain folder only
    python3 mentat_brain.py where                           # brain / engine / fleet / admin, read-only
    python3 mentat_brain.py where --find "<request>" [--json]  # what exists already; writes a receipt
    python3 mentat_brain.py where --decide RECEIPT use|enable|new --candidate ID [--why T] [--approved T]
    python3 mentat_brain.py where --map                     # the capability tree as a markdown table
    python3 mentat_brain.py where --probe ID|all            # a capability's real check, kept with a TTL
    python3 mentat_brain.py where --map --html | --export   # the tree as a page; the fleet's view (JSON)

Run it from the brain repo root (or pass --repo). Do not read the templates for these
six types: the file comes out filled in, with ULID and the _meta.md index line.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mentat_brain_ops as ops  # noqa: E402
import mentat_brain_read as rd  # noqa: E402
import mentat_brain_types as bt  # noqa: E402


def settings(root, lang):
    try:
        m = json.loads((root / "mentat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        m = {}
    lang = lang or (m.get("agent") or {}).get("language")
    brain = ((m.get("components") or {}).get("brain") or {}).get("root")
    if not brain:
        brain = next((d for d in ("agy", "brain") if (root / d).is_dir()), "agy")
    lang = lang or ("en" if brain == "brain" else "hu")
    return lang, brain, (m.get("cases") or {}).get("backend", "markdown")


def new(a, root, lang, brain, backend):
    if a.type == "case" and backend == "admin":
        print("STOP cases live in the admin (cases.backend: admin) - use its `cases` CLI")
        return 2
    d = root / brain / bt.DIRS[a.type]
    day = bt.local_today(root).isoformat()
    name = ("%s-%s" % (day, bt.slugify(a.title)) if a.type in bt.DATED else bt.slugify(a.title))
    path = d / (name + ".md")
    if path.exists():
        print("STOP exists: %s - edit it or pick another title" % path.relative_to(root))
        return 1
    tags = [t for t in a.tags.split(",") if t]
    head, tail = bt.BODY[lang][a.type]
    text = (sys.stdin.read() if a.body == "-" else a.body or "").strip()
    if text:
        body = head.replace("{t}", a.title) + ("" if a.type == "brain-dump" else "\n\n") + text + tail
    else:
        body = head + tail
    body = body.replace("{t}", a.title).replace("{d}", day)
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(bt.frontmatter(a.type, a.title, tags, a.due, day) + body, encoding="utf-8")
    meta = d / "_meta.md"
    line = "- [%s](%s) - %s%s\n" % (a.title, path.name, a.type, ", %s" % a.due if a.due else "")
    old = meta.read_text(encoding="utf-8") if meta.exists() else "# %s\n" % d.relative_to(root)
    meta.write_text(old + ("" if old.endswith("\n") else "\n") + line, encoding="utf-8")
    print(path.relative_to(root))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mentat_brain.py")
    p.add_argument("--repo", default=".")
    p.add_argument("--lang", choices=["hu", "en"])
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("type", choices=sorted(bt.DIRS))
    n.add_argument("title")
    n.add_argument("--due")
    n.add_argument("--tags", default="")
    n.add_argument("--body")
    d = sub.add_parser("due")
    d.add_argument("--days", type=int, default=7)
    d.add_argument("--all", action="store_true", help="also open items without a date")
    d.add_argument("--full", action="store_true", help="all rows (default: at most 8 lines)")
    f = sub.add_parser("find")
    f.add_argument("words", nargs="+")
    f.add_argument("--limit", type=int, default=12)
    v = sub.add_parser("mv", help="rename a note + fix every link and the _meta index")
    v.add_argument("old")
    v.add_argument("new", nargs="?")
    v.add_argument("--title", help="also retitle (new file name derives from it when NEW is omitted)")
    v.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("commit", help="git add + commit the brain folder only (never .env)")
    c.add_argument("message")
    w = sub.add_parser("where", help="what is where; --find: what already exists for a request")
    w.add_argument("--find", metavar="REQUEST", help="the request in the USER's words (before new code)")
    w.add_argument("--json", action="store_true")
    w.add_argument("--map", action="store_true", help="the capability tree as a markdown table")
    w.add_argument("--probe", metavar="ID|all", help="run a capability's real check (remembered with a TTL)")
    w.add_argument("--html", action="store_true", help="with --map: one self-contained page")
    w.add_argument("--export", action="store_true", help="approved fields only, for the fleet (JSON)")
    w.add_argument("--decide", nargs=2, metavar=("RECEIPT", "use|enable|new"))
    w.add_argument("--candidate")
    w.add_argument("--why", default="")
    w.add_argument("--approved", default="", help="the USER's yes, verbatim")
    a = p.parse_args(argv)
    if getattr(a, "due", None) and not re.match(r"\d{4}-\d\d-\d\d$", a.due):
        p.error("--due must be YYYY-MM-DD")
    root = pathlib.Path(a.repo)
    lang, brain, backend = settings(root, a.lang)
    if a.cmd == "new":
        return new(a, root, lang, brain, backend)
    if a.cmd == "where":
        return ops.where(a, root, brain, lang)
    return {"due": rd.due, "find": rd.find, "mv": ops.mv, "commit": ops.commit}[a.cmd](a, root, brain)


if __name__ == "__main__":
    sys.exit(main())
