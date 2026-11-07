"""Backend switch (design §6.4, §10): all or nothing; `cases.backend` is
rewritten only after every case is verified.

to admin   per file: (a) case_id generated once, written with `migration:
           pending`; (b) PUT keyed by that id — a retry after a lost answer
           cannot duplicate; (c) read back and compare. Then the backend flips,
           and only then are the tracked fields stripped (`migration: done`).
           Interrupted anywhere: still markdown (or, after the flip, a rerun
           finishes the strip) — rerunning reaches the same state.
to markdown  every admin case is read first, all files are written, re-read
           and compared; any failure restores every file byte for byte.
export     the to-markdown files into another folder; brain and backend untouched.
"""
from pathlib import Path

import adminstore
import fmwrite
import mdstore
import mentat_manifest as mm
from common import LEGACY, TRACKED, CasesError, case, slug, ulid

SEND = ("title", "description", "status", "next_action", "recurrence", "anchor_at", "extra")


def _payload(fm, rel, text, own=()):
    """A file's PUT body. Legacy waiting_on/category ride in extra (common.case);
    a frontmatter key the admin declares as an own field is sent as that field."""
    c = case(fm)
    body = {k: c[k] for k in SEND}
    body.update({k: fm[k] for k in own if fm.get(k) is not None})
    if c["recurrence"]:
        body["occurrences"] = c["occurrences"]
    else:
        body["due_at"] = c["due_at"]
    return {**body, "brain_ref": rel, "context": fmwrite.context(text)}


def _verify(admin, cid, fm, rel):
    want, got = case(fm), case(admin.raw(cid))
    keys = [k for k in SEND if want[k] != got[k]]
    if not want["recurrence"] and want["due_at"] != got["due_at"]:
        keys.append("due_at")
    if [o["due_at"] for o in want["occurrences"]] != [o["due_at"] for o in got["occurrences"]]:
        keys.append("occurrences")
    if keys:
        raise CasesError("%s: the admin disagrees after writing (%s) — backend NOT switched" % (rel, ", ".join(keys)))


def to_admin(root, brain, backend, dry_run):
    admin = adminstore.Admin(root, brain)
    files = [(p, fm, t) for p, fm, t in mdstore.scan(root, brain)
             if backend == "markdown" or fm.get("migration") == "pending"]
    if dry_run:
        return "\n".join(["would move %d case(s) to the admin:" % len(files)] + [
            "  %s  %s  %s" % (fm.get("case_id") or "(new id)", fm.get("title"), p.relative_to(root).as_posix())
            for p, fm, _ in files])
    for path, fm, text in files:
        rel = path.relative_to(root).as_posix()
        cid = str(fm.get("case_id") or ulid())
        if backend == "markdown":
            if fm.get("case_id") != cid or fm.get("migration") != "pending":
                text = fmwrite.set_fields(text, {"case_id": cid, "migration": "pending"})
                mdstore.write(path, text)
            admin.put_raw(cid, _payload(fm, rel, text, admin.own()))
        _verify(admin, cid, fm, rel)
    if backend == "markdown":
        mm.update("cases", "cases", {"backend": "admin"}, root)
    for path, fm, text in mdstore.scan(root, brain):
        if fm.get("migration") == "pending":
            drop = {k: fmwrite.DELETE for k in (*TRACKED, *LEGACY, *admin.own())}
            mdstore.write(path, fmwrite.set_fields(text, {**drop, "migration": "done"}))
    return "moved %d case(s); cases.backend is now admin" % len(files)


def _render(root, brain, admin, out_dir):
    """{path: new text} for every admin case — nothing written yet."""
    by_id = {str(fm.get("case_id")): (p, t) for p, fm, t in mdstore.scan(root, brain) if fm.get("case_id")}
    plan = {}
    for row in admin.list_raw(["open", "waiting", "done", "dropped"]):
        c = case(admin.raw(row["id"]), admin.own())
        here, text = by_id.get(c["id"], (None, None))
        name = Path(row.get("brain_ref") or "").name or "%s-%s.md" % (slug(c["title"]), c["id"][-6:].lower())
        path = Path(out_dir) / name if out_dir else here or root / brain / "cases" / name
        if path in plan:
            path = path.with_name("%s-%s.md" % (path.stem, c["id"][-6:].lower()))
        fields = {"type": "case", "case_id": c["id"], "migration": fmwrite.DELETE}
        fields.update({k: fmwrite.DELETE if c[k] in (None, [], {}) else c[k] for k in TRACKED})
        fields.update({k: fmwrite.DELETE for k in LEGACY})
        fields.update({k: fmwrite.DELETE if v is None else v for k, v in c["own"].items()})
        base = text if text is not None else fmwrite.new_file({}, admin.get(c["id"])["context"])
        plan[path] = (fmwrite.set_fields(base, fields), c)
    return plan


def to_markdown(root, brain, out_dir=None):
    admin = adminstore.Admin(root, brain)
    plan = _render(root, brain, admin, out_dir)
    before = {p: (p.read_bytes() if p.exists() else None) for p in plan}
    try:
        for path, (text, _) in plan.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            mdstore.write(path, text)
        if not out_dir:
            got = {c["id"]: c for c in mdstore.Markdown(root, brain).list(["open", "waiting", "done", "dropped"])}
            for path, (_, want) in plan.items():
                have = got.get(want["id"])
                if not have or any(have[k] != want[k] for k in TRACKED):
                    raise CasesError("%s: re-read does not match the admin — nothing switched" % path.name)
            mm.update("cases", "cases", {"backend": "markdown"}, root)
    except BaseException:
        for path, old in before.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old)
        raise
    where = out_dir or "the brain"
    tail = "" if out_dir else "; cases.backend is now markdown"
    return "wrote %d case file(s) to %s%s" % (len(plan), where, tail)


def run(args, brain, backend):
    if args.cmd == "export":
        return to_markdown(args.root, brain, out_dir=Path(args.out).resolve()), 0
    if args.to == "admin":
        return to_admin(args.root, brain, backend, args.dry_run), 0
    if backend != "admin":
        raise CasesError("cases.backend is already markdown")
    if args.dry_run:
        return "would write every admin case back into %s/cases and switch to markdown" % brain, 0
    return to_markdown(args.root, brain), 0
