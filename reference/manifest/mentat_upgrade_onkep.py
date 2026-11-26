"""The role self-image (Szerep önkép) at an upgrade, on the install's own format and decision.

bekotes/szerep_onkep.py (downloaded next to these tools) holds the format of <brain root>/szerep-onkep.md,
the shipped defaults (bekotes/szerepek/<role>.<lang>.md) and the decision table; this module only
names its actions and carries them out for the roles in mentat.json `roles.installed`:
  install   no block yet: the default goes in (szerep_onkep.write)
  uptodate  nothing to do
  replace   the owner never changed the block and our default moved on: new default, alap, verzio
  keep      changed by the owner, our default the same (or a custom role): kept
  offer     changed by the owner and our default changed: the diff is shown; adopted only with
            --adopt-onkep <role>, the owner's text saved to szerep-onkep.elozo.md first
"Substantially improved" is not measurable from a hash, so a changed default is offered, never
applied on its own. Text outside the blocks is never touched.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
WHY = {"install": "no self-image yet: the default goes in", "uptodate": "nothing changed",
       "replace": "unchanged since our default: replaced with the new one",
       "keep": "changed by the owner: kept",
       "offer": "changed by the owner, and our default changed: offered, not applied"}


def engine():
    """bekotes/szerep_onkep: downloaded next to the tools, else the release tree (dev)."""
    for d in (HERE / "bekotes", HERE.parent / "bekotes"):
        if (d / "szerep_onkep.py").is_file():
            if str(d) not in sys.path:
                sys.path.append(str(d))
            import szerep_onkep
            return szerep_onkep
    return None


def roles_of(root):
    """The roles this agent has (mentat.json roles.installed); none recorded -> none touched."""
    try:
        r = json.loads((pathlib.Path(root) / "mentat.json").read_text(encoding="utf-8")).get("roles") or {}
    except (OSError, ValueError, AttributeError):
        return []
    return [x for x in (r.get("installed") or []) if isinstance(x, str)] if isinstance(r, dict) else []


def plan(root, brain_root, lang):
    """[(role, action, why, diff)]; nothing written."""
    so, names = engine(), roles_of(root)
    if so is None or not names:
        return []
    action = {so.BEIR: "install", so.SEMMI: "uptodate", so.CSERE: "replace", so.MARAD: "keep",
              so.FELAJANL: "offer"}
    return [(n, action[act], WHY[action[act]], d or "") for n, act, d in so.plan(root, brain_root, names, lang)]


def apply(root, brain_root, lang, version, adopt=()):
    """Carry out install / replace (and offer only for the roles in `adopt`); [(role, what was done)]."""
    so, steps = engine(), plan(root, brain_root, lang)
    path, done = pathlib.Path(root) / brain_root / (so.FILE if so else ""), []
    todo = {r: ("adopt" if a == "offer" and r in adopt else a) for r, a, _, _ in steps}
    swap = [r for r, a in todo.items() if a in ("replace", "adopt")]
    if swap:
        text, have = path.read_text(encoding="utf-8"), so.parse(path.read_text(encoding="utf-8"))
        keep = [r for r in swap if todo[r] == "adopt"]
        if keep:  # the owner's text first goes to a file of its own, never lost
            with open(path.with_name("szerep-onkep.elozo.md"), "a", encoding="utf-8", newline="\n") as f:
                f.write("".join("\n## %s\n\n%s\n" % (r, have[r]["text"]) for r in keep))

        def sub(m):
            if m.group(1) not in swap:
                return m.group(0)
            new = so.template(m.group(1), lang)
            return so.render(m.group(1), new, so.digest(new), version).rstrip("\n")
        path.write_bytes(so.BLOCK.sub(sub, text).encode("utf-8"))
        done += [(r, todo[r]) for r in swap]
    new = [r for r, a in todo.items() if a == "install"]
    if new and so.write(root, brain_root, new, lang):
        done += [(r, "install") for r in new]
    return done
