"""Command dispatch: read the manifest, pick the backend, print."""
from pathlib import Path

import mentat_manifest as mm
import mentat_rules as rules
import view
from common import CasesError, Diagnostic, sort_cases, statuses


def setup(root):
    """(brain root, backend name) — or a refusal when the manifest can't be acted on."""
    ev = mm.evaluate_root(root)
    if ev["diagnostic_only"]:
        raise Diagnostic("mentat.json / .mentat/local.json cannot be acted on: %s"
                         % ", ".join("%s at %s" % (e["code"], e["at"]) for e in ev["errors"]))
    doc = mm.load(root)
    brain = ((doc.get("components") or {}).get("brain") or {}).get("root")
    if not rules.path_inside_repo(brain):
        raise CasesError("mentat.json has no usable components.brain.root")
    backend = (doc.get("cases") or {}).get("backend") or "markdown"
    if backend not in ("markdown", "admin"):
        raise CasesError("unknown cases.backend %r (markdown | admin)" % backend)
    return brain, backend


def store(root, brain, backend):
    if backend == "admin":
        import adminstore
        return adminstore.Admin(root, brain)
    import mdstore
    return mdstore.Markdown(root, brain)


def _show(args, c, extra=None):
    d = view.detail(c, args.today)
    if args.json:
        return view.dump({**d, **(extra or {})})
    return view.show_text(d)


def run(args):
    brain, backend = setup(args.root)
    if args.cmd == "status":
        import status
        return status.text(args.root, brain, backend), 0
    if args.cmd == "sync":
        import sync
        return sync.run(args.root, brain, backend)
    if args.cmd in ("export", "migrate"):
        import migrate
        return migrate.run(args, brain, backend)
    if args.cmd == "propose-scan":
        import propose_scan
        return propose_scan.run(args, args.root, brain)
    if args.cmd == "proposal":
        import proposal
        return proposal.check(args.root, brain, args.file)
    s = store(args.root, brain, backend)
    if args.cmd == "import":
        import proposal_import
        return proposal_import.run(args, args.root, brain, s)
    if args.cmd == "fields":
        if backend != "admin":
            return "no own case fields in markdown mode — own fields are declared in the admin", 0
        f = s.own_fields()
        return (view.dump(f) if args.json else view.fields_text(f)), 0
    own = getattr(args, "own", None) or {}
    if own:
        if backend != "admin":
            raise CasesError("--set writes the admin's own fields; cases.backend is markdown — "
                             "put the value in the frontmatter's extra instead")
        bad = sorted(set(own) - set(s.own()))
        if bad:
            raise CasesError("not an own case field of this admin: %s (see `cases fields`)" % ", ".join(bad))
        args.fields.update(own)
    if args.cmd == "list":
        rows = sort_cases(s.list(statuses(args.status)))
        return (view.list_json(rows) if args.json else view.list_text(rows)), 0
    if args.cmd == "due":
        items = s.due(args.until)
        return (view.dump(items) if args.json else view.due_text(items, args.today)), 0
    if args.cmd == "show":
        return _show(args, s.get(args.id)), 0
    if args.cmd == "create":
        if not args.fields.get("title"):
            raise CasesError("--title is required")
        if args.fields.get("recurrence"):
            args.fields.pop("due_at", None)
        if args.file:
            args.file = Path(args.file).resolve()
            folder = (args.root / brain / "cases").resolve()
            if args.file.parent != folder or args.file.suffix != ".md":
                raise CasesError("case files live in %s/cases/ — move the note there first (git mv), "
                                 "then run create --file again" % brain)
        return _show(args, s.put(None, args.fields, file=args.file, title=args.fields["title"])), 0
    if args.cmd == "add":
        return add(args, s, backend), 0
    if args.cmd == "update":
        if not args.fields:
            raise CasesError("nothing to update")
        _anchor_from_due(args.fields)
        return _show(args, s.put(args.id, args.fields)), 0
    if args.cmd == "close":
        c, already = s.close(args.id, args.occurrence, "skipped" if args.skip else "done",
                             args.done_at or args.today, args.note)
        if args.next_step is not None:  # close + the new next step, one command
            c = s.put(args.id, {"next_action": args.next_step or None})
        if args.json:
            return _show(args, c, {"already_closed": already}), 0
        head = "already closed — nothing written" if already else "closed"
        nxt = "; next due %s" % c["due_at"] if c["recurrence"] and c["due_at"] else ""
        nxt += "; next step: %s" % c["next_action"] if args.next_step else ""
        return "%s: %s%s" % (head, c["title"], nxt), 0
    raise CasesError("unknown command " + args.cmd)


def add(args, s, backend):
    """One case into the configured backend. --due is the date; with a
    --recurrence it is the first due date, and the series is anchored on the
    rule's date of that period (monthly:10 --due 2026-10-20: anchor 10-10,
    October due on the 20th, then every 10th)."""
    f = args.fields
    if not f.get("title"):
        raise CasesError("--title is required")
    if not f.get("due_at"):
        raise CasesError("--due is required (a case has a date: the deadline, or the first due date)")
    _anchor_from_due(f)
    c = s.put(None, f, title=f["title"])
    if args.json:
        return _show(args, c)
    where = "admin" if backend == "admin" else "markdown (%s)" % c.get("brain_ref", "")
    lines = [_show(args, c), "written to: %s" % where]
    if backend != "admin" and ((mm.local(args.root) or {}).get("admin") or {}).get("url"):
        lines.append("note: an admin is bound, but cases.backend is markdown. To keep cases in the admin: "
                     "cases_cli migrate --to admin --dry-run, then migrate --to admin (moves all of them).")
    return "\n".join(lines)


def _anchor_from_due(f):
    """--recurrence with --due and no --anchor: anchor on the rule's date of the
    due date's period; an off-rule due date is that occurrence moved later."""
    import occurrence
    import recurrence
    if f.get("recurrence") and f.get("due_at") and not f.get("anchor_at") and recurrence.parse(f["recurrence"]) \
            and recurrence.is_date(f["due_at"]):
        f["anchor_at"] = occurrence.anchor_for(f["recurrence"], f["due_at"])
