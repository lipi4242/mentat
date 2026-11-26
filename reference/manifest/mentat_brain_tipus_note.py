"""Notes of the owner's own types: `new <custom type>` and `check` (frontmatter against the definition)."""
import sys

import mentat_brain_read as rd
import mentat_brain_tipus as tp
import mentat_brain_tipus_cmd as tc
import mentat_brain_types as bt


def new(a, root, brain, d):
    fields = {f["name"]: f for f in d["fields"]}
    vals = {}
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        if k not in fields:
            print("STOP %s has no field %r (fields: %s)" % (d["slug"], k, ", ".join(fields) or "-"))
            return 1
        vals[k] = v.strip()
    if a.due:
        if not d.get("due_field"):
            print("STOP %s has no due field (`type edit %s --due-field F`)" % (d["slug"], d["slug"]))
            return 1
        vals[d["due_field"]] = a.due
    if d.get("title_field"):
        vals.setdefault(d["title_field"], a.title)
    folder = root / brain / d["dir"]
    path = folder / (bt.slugify(a.title) + ".md")
    if path.exists():
        print("STOP exists: %s - edit it or pick another title" % path.relative_to(root).as_posix())
        return 1
    day = bt.local_today(root).isoformat()
    tags = [t for t in a.tags.split(",") if t]
    rows = ["type: %s" % d["slug"]] + ["%s: %s" % (f, vals.get(f, "")) for f in fields]
    rows += ["tags: [%s]" % ", ".join(tags), "created: %s" % day]
    body = d["body"].replace("{t}", a.title).replace("{d}", day)
    text = (sys.stdin.read() if a.body == "-" else a.body or "").strip()
    if text:
        body = body.rstrip("\n") + "\n\n" + text + "\n"
    folder.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("---\n" + "\n".join(rows) + "\n---\n\n" + body).encode("utf-8"))
    tc.index(folder, root, "- [%s](%s) - %s\n" % (a.title, path.name, d["slug"]))
    print(path.relative_to(root).as_posix())
    return 0


def check(a, root, brain):
    defs, bad = tp.load(root, brain), 0
    dirs = {d["dir"]: s for s, d in defs.items()}
    for p, fm, _, _ in rd.notes(root, brain):
        rel = p.relative_to(root / brain)
        kind = fm.get("type") or dirs.get(rel.parts[0] if len(rel.parts) > 1 else "")
        d = defs.get(kind)
        if not d or (a.type and kind != a.type):
            continue
        out = tp.problems(fm, d) + ([] if fm.get("type") else ["no `type: %s` line" % kind])
        if out:
            bad += 1
            print("%s: %s" % (p.relative_to(root).as_posix(), "; ".join(out)))
    print("check: %d note(s) with warnings%s" % (bad, "" if bad else " - all custom notes match their type"))
    return 1 if bad and a.strict else 0
