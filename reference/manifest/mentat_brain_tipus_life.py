"""Types evolve: `type rename|merge|split|collect`. Notes move with their links and index lines
(mentat_brain_tipus_move), every change leaves a decision note, and --dry-run only prints the plan."""
import argparse
import pathlib

import mentat_brain_read as rd
import mentat_brain_tipus as tp
import mentat_brain_tipus_cmd as tc
import mentat_brain_tipus_move as mv
import mentat_brain_types as bt


def parser(ts):
    r = ts.add_parser("rename", help="new slug (and folder); notes, links, index follow")
    r.add_argument("old")
    r.add_argument("new")
    r.add_argument("--dir")
    r.add_argument("--name")
    m = ts.add_parser("merge", help="two types into one; fields united, notes moved")
    m.add_argument("types", nargs=2)
    m.add_argument("--into", required=True)
    m.add_argument("--dir", help="folder of --into when it is a new type")
    s = ts.add_parser("split", help="notes matching a rule move to a new type")
    s.add_argument("type")
    s.add_argument("--rule", action="append", default=[], metavar="NEW=field:value")
    s.add_argument("--note", action="append", default=[], metavar="NEW=path")
    s.add_argument("--dir", action="append", default=[], metavar="NEW=folder")
    for p in (r, m, s):
        p.add_argument("--why", default="", help="the reason, in the USER's words")
        p.add_argument("--dry-run", action="store_true")


def decide(root, brain, title, lines, why):
    """The trace of a type change: an ordinary decision note."""
    import mentat_brain as mb
    lang, _, backend = mb.settings(root, None)
    body = "\n".join(lines) + ("\n\n%s %s" % ("Miért:" if lang == "hu" else "Why:", why) if why else "")
    a = argparse.Namespace(type="decision", title=title, due=None, tags="entity-type", body=body, set=None)
    if mb.new(a, root, lang, brain, backend):
        a.title = "%s (%s)" % (title, bt.ulid()[-6:].lower())
        mb.new(a, root, lang, brain, backend)


def _run(a, root, brain, plan, title, prepare=None, finish=None, extra=()):
    """check -> print the plan -> (dry run stops here) -> prepare, move, finish -> decision note."""
    err = mv.check(plan, root)
    if err:
        return err
    mv.describe(plan, root)
    if a.dry_run:
        print("dry run: nothing changed")
        return ""
    if prepare:
        prepare()
    n = mv.apply(plan, root, brain)
    after = finish() if finish else []
    lines = list(extra) + ["- %s -> %s" % (o.relative_to(root).as_posix(), nw.relative_to(root).as_posix())
                           for o, nw, _ in plan if o != nw] + after
    decide(root, brain, title, lines, a.why)
    print("%d note(s) moved, links fixed in %d file(s); decision written" % (sum(o != nw for o, nw, _ in plan), n))
    return ""


def members(root, brain, d):
    return sorted(p for p in (root / brain / d["dir"]).glob("*.md") if p.name != "_meta.md")


def new_def(base, slug, folder, name=""):
    return dict(base, slug=slug, dir=folder, name=name or slug, fields=[dict(f) for f in base["fields"]])


def _drop(root, brain, d):
    """Remove a type definition (and its emptied folder); the old index text goes to the decision."""
    p = root / brain / tp.TYPES_DIR / (d["slug"] + ".md")
    p.unlink()
    idx = p.parent / "_meta.md"
    if idx.exists():
        keep = [ln for ln in idx.read_text(encoding="utf-8").splitlines(True) if "](%s)" % p.name not in ln]
        idx.write_bytes("".join(keep).encode("utf-8"))
    folder = root / brain / d["dir"]
    meta = folder / "_meta.md"
    old = meta.read_text(encoding="utf-8") if meta.exists() else ""
    if folder.is_dir() and not [q for q in folder.iterdir() if q.name != "_meta.md"]:
        if meta.exists():
            meta.unlink()
        folder.rmdir()
        return ["", "%s/_meta.md:" % d["dir"]] + ["    " + ln for ln in old.splitlines() if "](" not in ln and ln.strip()]
    return []


def rename(a, root, brain, defs):
    d = defs.get(a.old)
    if not d or a.new in defs or a.new in tp.RESERVED or a.new != bt.slugify(a.new):
        return "STOP %s -> %s: unknown, taken or malformed slug" % (a.old, a.new)
    folder = (a.dir or d["dir"]).strip("/")
    if folder != d["dir"] and (folder in tp.BUILTIN_DIRS or (root / brain / folder).exists()):
        return "STOP %s/ is taken" % folder
    plan = [(p, root / brain / folder / p.name, a.new) for p in members(root, brain, d)]
    def prepare():
        tc.save(new_def(d, a.new, folder, a.name or d["name"]), root, brain)
        old, new = root / brain / d["dir"] / "_meta.md", root / brain / folder / "_meta.md"
        if folder != d["dir"] and old.exists():  # the index's own text moves with the folder
            new.parent.mkdir(parents=True, exist_ok=True)
            text = "".join(ln for ln in old.read_text(encoding="utf-8").splitlines(True) if "](" not in ln)
            new.write_bytes(text.replace(d["dir"], folder, 1).encode("utf-8"))
    return _run(a, root, brain, plan, "type rename %s -> %s" % (a.old, a.new), prepare,
                lambda: _drop(root, brain, d))


def merge(a, root, brain, defs):
    if any(t not in defs for t in a.types) or a.types[0] == a.types[1]:
        return "STOP merge needs two different existing types (`types`)"
    if a.into not in a.types and (a.into in defs or a.into in tp.RESERVED or not a.dir):
        return "STOP --into %s: an existing slug, or a new one with --dir" % a.into
    base = defs[a.into] if a.into in defs else new_def(defs[a.types[0]], a.into, a.dir.strip("/"), a.into)
    names = {f["name"] for f in base["fields"]}
    for t in a.types:
        for f in defs[t]["fields"]:
            if f["name"] not in names:
                base["fields"].append(dict(f, required=False))
                names.add(f["name"])
    plan = [(p, root / brain / base["dir"] / p.name, a.into) for t in a.types for p in members(root, brain, defs[t])]
    olds = [defs[t] for t in a.types if t != a.into]
    return _run(a, root, brain, plan, "type merge %s + %s -> %s" % (a.types[0], a.types[1], a.into),
                lambda: tc.save(base, root, brain), lambda: sum((_drop(root, brain, d) for d in olds), []),
                ["fields: " + ", ".join(f["name"] for f in base["fields"])])
