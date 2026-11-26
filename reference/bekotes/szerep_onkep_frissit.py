"""`bekotes.py onkep [--alkalmaz]`: the upgrade step for the role self-image blocks.

Prints each installed role's action (szerep_onkep.decide). With --alkalmaz it carries out only
the safe ones: `csere` (the owner never changed the block: new default text, `alap`, `verzio`) and
`beir`; a changed block stays, and `felajanl` prints the diff for the owner to decide.
"""
import pathlib

import hely
import mentat_manifest as mm
import mentat_rules as rules
import mentat_self_image
import szerep_onkep as so


def replace(text, name, default):
    """`text` with role `name`'s block set to `default` and its alap/verzio moved on."""
    def sub(m):
        return so.render(name, default, so.digest(default), so.version()).rstrip("\n") if m.group(1) == name \
            else m.group(0)
    return so.BLOCK.sub(sub, text)


def run(a):
    repo = pathlib.Path(a.repo)
    lang = a.lang or ("en" if hely.language(repo) == "en" else "hu")
    root = hely.brain_root(repo)
    names = rules._dict(mm.load(repo).get("roles")).get("installed") or []
    steps = so.plan(repo, root, names, lang)
    for n, act, d in steps:
        print("%s: %s" % (n, act))
        if d:
            print(d, end="")
    if getattr(a, "alkalmaz", False):
        path = repo / root / so.FILE
        for n, act, _ in steps:
            if act == so.CSERE:
                path.write_bytes(replace(path.read_text(encoding="utf-8"), n, so.template(n, lang)).encode("utf-8"))
        so.write(repo, root, [n for n, act, _ in steps if act == so.BEIR], lang)
        mentat_self_image.write(repo, lang)
    return 0
