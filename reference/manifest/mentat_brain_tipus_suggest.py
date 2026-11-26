"""`type suggest`: cheap, deterministic signals that something deserves its own type (no LLM);
`type collect`: scattered notes into an existing type's folder (links and index follow)."""
import collections

import mentat_brain_read as rd
import mentat_brain_tipus as tp

# keys every built-in note may carry: a recurring one of these says nothing about a new kind of thing
COMMON = {"type", "tags", "title", "name", "topic", "status", "priority", "due", "due_at", "date", "created",
          "weight", "role", "relationship", "case_id", "description", "next_action", "processed", "auth_location"}
# title words too common to name a kind of thing
STOP = {"a", "az", "egy", "es", "the", "and", "of", "for", "new", "uj", "re", "to", "with"}


def parser(ts):
    s = ts.add_parser("suggest", help="recurring untyped things: candidates for a new type, with counts")
    s.add_argument("--min", type=int, default=3, help="how often a tag, field or title word must recur")
    s.add_argument("--all", action="store_true", help="every candidate (default: the top 10)")
    c = ts.add_parser("collect", help="scattered notes into a type's folder (links + index follow)")
    c.add_argument("type")
    c.add_argument("notes", nargs="*")
    c.add_argument("--tag")
    c.add_argument("--why", default="")
    c.add_argument("--dry-run", action="store_true")


def _tags(fm):
    return [t.strip() for t in (fm.get("tags") or "").strip("[]").split(",") if t.strip()]


def suggest(a, root, brain, defs):
    known = tp.RESERVED | set(defs)
    owned = {d["dir"] for d in defs.values()}
    base = root / brain
    folders, kinds, tags, keys, words = (collections.Counter() for _ in range(5))
    for p, fm, title, _ in rd.notes(root, brain):
        rel = p.relative_to(base).parts
        top = rel[0] if len(rel) > 1 else ""
        if top in owned or top == tp.TYPES_DIR:
            continue  # already a type of the owner's
        if top and top not in tp.BUILTIN_DIRS:
            folders[top] += 1  # its fields and tags are the folder's business: `type adopt` reads them
            continue
        if fm.get("type") and fm["type"] not in known:
            kinds[fm["type"]] += 1
        tags.update(_tags(fm))
        keys.update(k for k in fm if k not in COMMON)
        w = rd.fold(title.split(":", 1)[0] if ":" in title else title.split(" ", 1)[0]).strip(" #*")
        if len(w) >= 4 and w not in STOP:
            words[w] += 1
    rows = [(n, "folder %s/%s/" % (brain, f), "`type adopt %s`" % f) for f, n in folders.items() if n >= 2]
    rows += [(n, "type: %s" % k, "notes outside a type; `type add %s ...` then `type collect %s ...`" % (k, k))
             for k, n in kinds.items() if n >= 2]
    rows += [(n, "tag #%s" % t, "`type collect <slug> --tag %s` after `type add`" % t)
             for t, n in tags.items() if n >= a.min and t not in known]
    rows += [(n, "field %s" % k, "a recurring field outside any type") for k, n in keys.items() if n >= a.min]
    rows += [(n, "title '%s'" % w, "recurring title word") for w, n in words.items() if n >= a.min and w not in known]
    rows.sort(key=lambda r: (-r[0], r[1]))
    for n, what, hint in rows if a.all else rows[:10]:
        print("%3d  %-28s %s" % (n, what, hint))
    if len(rows) > 10 and not a.all:
        print("+%d more (--all)" % (len(rows) - 10))
    print("%d candidate(s)%s" % (len(rows), "; ask the USER once about the best one (name + fields), on yes `type add`, then `type collect`" if rows else ""))
    return ""


def collect(a, root, brain, defs):
    import mentat_brain_tipus_life as tl
    d = defs.get(a.type)
    if not d:
        return "STOP unknown type %s (`types`)" % a.type
    want = {(root / n).resolve() for n in a.notes}
    folder = root / brain / d["dir"]
    plan = [(p, folder / p.name, a.type) for p, fm, _, _ in rd.notes(root, brain)
            if p.parent != folder and p.parent.name != tp.TYPES_DIR
            and (p.resolve() in want or (a.tag and a.tag in _tags(fm)))]
    if not plan:
        return "STOP nothing to collect (note paths or --tag)"
    return tl._run(a, root, brain, plan, "type collect -> %s" % a.type)

