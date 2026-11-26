"""`type adopt <folder>`: infer a definition from hand-made notes. The notes are only read, never written;
the folder's _meta.md keeps every line it has and gains index lines for the notes it does not link yet."""
import collections
import re

import mentat_brain_read as rd
import mentat_brain_tipus as tp
import mentat_brain_tipus_cmd as tc
import mentat_brain_types as bt

SKIP = {"type", "tags", "created"}
TITLES = ("title", "name", "nev", "cim", "megnevezes", "topic")


def kind(values, n):
    """The narrowest kind every non-empty value fits; text when unsure."""
    vs = [v for v in values if v]
    if not vs:
        return "text", []
    if all(v.startswith("[") and v.endswith("]") and "](" not in v for v in vs):
        return "list", []
    if all(tp.DATE.match(v) for v in vs):
        return "date", []
    if all(re.match(r"-?\d+(?:[.,]\d+)?$", v) for v in vs):
        return "number", []
    if all("[[" in v or re.search(r"\]\([^)]+\.md\)", v) for v in vs):
        return "link", []
    distinct = sorted(set(vs))
    if n >= 4 and len(distinct) < len(vs) and len(distinct) <= 8 and \
            all(re.match(r"[\w-]{1,24}$", v) for v in distinct):
        return "enum", distinct
    return "text", []


def infer(folder, root, brain):
    rows = [(p, fm, t) for p, fm, t, _ in rd.notes(root, brain) if p.parent == folder]
    if not rows:
        return None, rows
    keys = collections.OrderedDict()
    for _, fm, _ in rows:
        for k in fm:
            if k not in SKIP:
                keys.setdefault(k, []).append(fm[k].strip())
    fields = []
    for k, vals in keys.items():
        knd, enum = kind(vals, len(rows))
        fields.append({"name": k, "kind": knd, "enum": enum,
                       "required": len(vals) == len(rows) and all(vals)})
    slugs = collections.Counter(fm.get("type") for _, fm, _ in rows if fm.get("type"))
    title = next((k for k in TITLES if k in keys and len(keys[k]) == len(rows)), "")
    return {"slug": slugs.most_common(1)[0][0] if slugs else bt.slugify(folder.name), "fields": fields,
            "title_field": title, "due_field": "", "body": "# {t}\n"}, rows


def refresh_meta(folder, root, rows, slug):
    meta = folder / "_meta.md"
    old = meta.read_text(encoding="utf-8") if meta.exists() else ""
    added = 0
    for p, _, title in rows:
        if "(%s)" % p.name not in old and "[[%s]]" % p.stem not in old:
            tc.index(folder, root, "- [%s](%s) - %s\n" % (title, p.name, slug))
            old = meta.read_text(encoding="utf-8")
            added += 1
    return added


def adopt(a, root, brain, defs):
    rel = a.folder.replace("\\", "/").strip("/")
    rel = rel[len(brain) + 1:] if rel.startswith(brain + "/") else rel
    folder = root / brain / rel
    if not folder.is_dir():
        return "STOP %s/%s/ is not a folder" % (brain, rel)
    if rel in tp.BUILTIN_DIRS or "/" in rel:
        return "STOP %s/ is a built-in folder, not the owner's own" % rel
    if any(d["dir"] == rel for d in defs.values()):
        return "STOP %s/ is already a type (`type show`)" % rel
    d, rows = infer(folder, root, brain)
    if not d:
        return "STOP %s/%s/ has no notes to learn from - use `type add`" % (brain, rel)
    d["slug"] = a.slug or d["slug"]
    if d["slug"] in tp.RESERVED or d["slug"] in defs or d["slug"] != bt.slugify(d["slug"]):
        return "STOP slug %r is built-in, taken or malformed - pass --slug" % d["slug"]
    d.update(name=a.name or rel, dir=rel, description=a.desc or "")
    path = tc.save(d, root, brain)
    added = refresh_meta(folder, root, rows, d["slug"])
    print("%s: %d note(s), %d field(s); %s/_meta.md +%d line(s); notes unchanged" % (
        path.relative_to(root).as_posix(), len(rows), len(d["fields"]), rel, added))
    for f in d["fields"]:
        print("  " + tp.describe(f))
    return ""
