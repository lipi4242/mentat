"""`mentat_brain.py type add|list|show|edit|adopt` and `new <custom type>`."""
import mentat_brain_tipus as tp
import mentat_brain_types as bt


def parser(sub):
    t = sub.add_parser("type", help="the owner's own entity types (ask the USER once before adding one)")
    ts = t.add_subparsers(dest="action", required=True)
    spec = "name:kind[:required][:enum=a|b]"
    a, e = ts.add_parser("add"), ts.add_parser("edit")
    a.add_argument("--name", required=True)
    a.add_argument("--dir", required=True, help="folder under the brain, e.g. borok")
    a.add_argument("--field", action="append", default=[], metavar=spec)
    e.add_argument("--add-field", action="append", default=[], metavar=spec)
    e.add_argument("--remove-field", action="append", default=[], metavar="NAME")
    e.add_argument("--rename-field", action="append", default=[], metavar="OLD=NEW", help="also in every note")
    for s in (a, e):
        s.add_argument("slug")
        s.add_argument("--due-field")
        s.add_argument("--title-field")
        s.add_argument("--desc")
    ts.add_parser("list")
    ts.add_parser("show").add_argument("slug")
    ad = ts.add_parser("adopt", help="turn a hand-made folder into a type; the notes are never changed")
    ad.add_argument("folder")
    ad.add_argument("--slug")
    ad.add_argument("--name")
    ad.add_argument("--desc")
    sub.add_parser("types", help="= type list")
    import mentat_brain_tipus_life as tl
    import mentat_brain_tipus_suggest as ts_
    tl.parser(ts)
    ts_.parser(ts)


def index(folder, root, line, header=""):
    meta = folder / "_meta.md"
    old = meta.read_text(encoding="utf-8") if meta.exists() else "# %s\n%s" % (folder.relative_to(root).as_posix(), header)
    meta.write_bytes((old + ("" if old.endswith("\n") else "\n") + line).encode("utf-8"))


def save(d, root, brain):
    """Write the definition; on first save also its index line and the type folder's _meta.md."""
    path = root / brain / tp.TYPES_DIR / (d["slug"] + ".md")
    first = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((tp.render(d)).encode("utf-8"))
    if first:
        index(path.parent, root, "- [%s](%s) - %s\n" % (d["name"], path.name, d["dir"]))
    return path


def check_fields(d, due, title):
    names = [f["name"] for f in d["fields"]]
    if len(set(names)) != len(names):
        return "duplicate field"
    for k, v in (("due-field", due), ("title-field", title)):
        if v and v not in names:
            return "--%s %s is not a field" % (k, v)
    if due and next(f for f in d["fields"] if f["name"] == due)["kind"] != "date":
        return "--due-field %s must be a date field" % due
    return ""


def add(a, root, brain, defs):
    name = a.dir.replace("\\", "/").strip("/")
    folder = root / brain / name
    if a.slug != bt.slugify(a.slug) or a.slug in tp.RESERVED or a.slug in defs:
        return "STOP %s: %s" % (a.slug, "built-in or existing type" if a.slug == bt.slugify(a.slug) else "slug: a-z, 0-9, -")
    if not name or "/" in name or name in tp.BUILTIN_DIRS or any(d["dir"] == name for d in defs.values()):
        return "STOP %s/ belongs to another type (one folder under the brain)" % name
    if folder.is_dir() and any(p.name != "_meta.md" for p in folder.glob("*.md")):
        return "STOP %s/ already has notes - use `type adopt %s`" % (name, name)
    try:
        fields = [tp.parse_field(s) for s in a.field]
    except ValueError as e:
        return "STOP %s" % e
    d = {"slug": a.slug, "name": a.name, "dir": name, "description": a.desc or "", "fields": fields,
         "title_field": a.title_field or next((f["name"] for f in fields if f["kind"] == "text"), ""),
         "due_field": a.due_field or "", "body": "# {t}\n"}
    err = check_fields(d, a.due_field, a.title_field)
    if err:
        return "STOP " + err
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "_meta.md").exists():
        head = "# %s/%s\n\n%s\n" % (brain, d["dir"], d["description"] or d["name"])
        (folder / "_meta.md").write_bytes(head.encode("utf-8"))
    print(save(d, root, brain).relative_to(root).as_posix())
    return ""


def edit(a, root, brain, defs):
    d = defs.get(a.slug)
    if not d:
        return "STOP unknown type %s (`types`)" % a.slug
    try:
        new = [tp.parse_field(s) for s in a.add_field]
    except ValueError as e:
        return "STOP %s" % e
    d["fields"] = [f for f in d["fields"] if f["name"] not in a.remove_field] + new
    for k in ("due_field", "title_field"):
        if getattr(a, k):
            d[k] = getattr(a, k)
        elif d.get(k) in a.remove_field:
            d[k] = ""
    if a.desc:
        d["description"] = a.desc
    err = check_fields(d, d.get("due_field"), d.get("title_field"))
    if err:
        return "STOP " + err
    if a.rename_field:
        import mentat_brain_tipus_split as sp
        return sp.rename_fields(a, root, brain, d)
    print("%s (notes unchanged; `check` lists the gaps)" % save(d, root, brain).relative_to(root).as_posix())
    return ""


def count(root, brain, d):
    return sum(1 for p in (root / brain / d["dir"]).glob("*.md") if p.name != "_meta.md")


def show(d, root, brain):
    print("%s - %s\ndir: %s/%s/ (%d notes)\n%s" % (d["slug"], d["name"], brain, d["dir"], count(root, brain, d),
          d.get("description") or ""))
    print("title field: %s\ndue field: %s" % (d.get("title_field") or "-", d.get("due_field") or "-"))
    for f in d["fields"]:
        print("  " + tp.describe(f))


def main(a, root, brain, lang):
    defs = tp.load(root, brain)
    act = "list" if a.cmd == "types" else a.action
    if act == "list":
        for d in defs.values():
            print("%-14s %-22s %3d  %s" % (d["slug"], "%s/%s/" % (brain, d["dir"]), count(root, brain, d),
                                          d.get("description") or d["name"]))
        print("%d type(s); reshape: type rename|merge|split|collect (--dry-run), candidates: type suggest" % len(defs))
        return 0
    if act == "show":
        if a.slug not in defs:
            print("STOP unknown type %s (`types`)" % a.slug)
            return 1
        show(defs[a.slug], root, brain)
        return 0
    if act in ("rename", "merge", "split", "collect", "suggest", "adopt"):
        import mentat_brain_tipus_adopt as ad
        import mentat_brain_tipus_life as tl
        import mentat_brain_tipus_split as sp
        import mentat_brain_tipus_suggest as sg
        err = {"adopt": ad.adopt, "rename": tl.rename, "merge": tl.merge, "split": sp.split,
               "collect": sg.collect, "suggest": sg.suggest}[act](a, root, brain, defs)
    else:
        err = {"add": add, "edit": edit}[act](a, root, brain, defs)
    if err:
        print(err)
        return 1
    return 0
