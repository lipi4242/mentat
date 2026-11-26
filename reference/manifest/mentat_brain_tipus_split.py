"""`type split` (notes matching a rule become a new type) and `type edit --rename-field`."""
import pathlib

import mentat_brain_read as rd
import mentat_brain_tipus as tp
import mentat_brain_tipus_cmd as tc
import mentat_brain_tipus_move as mv
import mentat_brain_types as bt
from mentat_brain_tipus_life import _run, decide, members, new_def


def _pairs(items):
    out = {}
    for it in items:
        k, _, v = it.partition("=")
        out.setdefault(k, []).append(v)
    return out


def split(a, root, brain, defs):
    d = defs.get(a.type)
    rules, picks, dirs = _pairs(a.rule), _pairs(a.note), {k: v[0] for k, v in _pairs(a.dir).items()}
    targets = list(dict.fromkeys(list(rules) + list(picks)))
    if not d or not targets or any(t in defs or t in tp.RESERVED or t != bt.slugify(t) for t in targets):
        return "STOP split needs an existing type and new slugs (--rule NEW=field:value | --note NEW=path)"
    plan = []
    for p, fm, _, _ in rd.notes(root, brain):
        if p.parent != root / brain / d["dir"]:
            continue
        hit = next((t for t in targets if any(fm.get(r.split(":", 1)[0], "").strip() == r.split(":", 1)[-1]
                                              for r in rules.get(t, []))
                    or any(pathlib.Path(n).name == p.name for n in picks.get(t, []))), None)
        if hit:
            plan.append((p, root / brain / dirs.get(hit, hit) / p.name, hit))
    return _run(a, root, brain, plan, "type split %s -> %s" % (a.type, ", ".join(targets)),
                lambda: [tc.save(new_def(d, t, dirs.get(t, t)), root, brain) for t in targets])


def rename_fields(a, root, brain, d):
    """`type edit --rename-field old=new`: the definition and the key in every note of the type."""
    pairs = [x.partition("=")[::2] for x in a.rename_field]
    names = [f["name"] for f in d["fields"]]
    if any(o not in names or not n or n in names for o, n in pairs):
        return "STOP --rename-field OLD=NEW: OLD must be a field, NEW a new name"
    for o, n in pairs:
        tp.parse_field(n)
        for f in d["fields"]:
            f["name"] = n if f["name"] == o else f["name"]
        for k in ("due_field", "title_field"):
            d[k] = n if d.get(k) == o else d.get(k, "")
        for p in members(root, brain, d):
            p.write_bytes((mv.rekey(p.read_text(encoding="utf-8"), o, n)).encode("utf-8"))
    tc.save(d, root, brain)
    decide(root, brain, "type edit %s: %s" % (d["slug"], ", ".join("%s -> %s" % x for x in pairs)),
           ["- %s/%s/: %d note(s) rekeyed" % (brain, d["dir"], len(members(root, brain, d)))], getattr(a, "why", ""))
    print("%s: %s renamed in %d note(s); decision written" % (d["slug"], ", ".join(o for o, _ in pairs),
          len(members(root, brain, d))))
    return ""
