"""import --from <proposal> [--only id,..]: the approved items of a proposal
(proposal.py checks the format) become cases. Each case file names its source;
the source note gets a line with the case's brain_ref and stays where it is. A
rerun skips what is already there: a case of the same title the source points
to, or whose file names the source. Nothing is written when the proposal, the
selection or an own field name is wrong.
"""
from pathlib import Path

import mdstore
from common import STATUSES, TRACKED, CasesError
from proposal import checked


def _existing(store, root, it):
    """The case this item already became, or None."""
    src_text = (Path(root) / it["source"]).read_text(encoding="utf-8")
    for c in store.list(list(STATUSES)):
        if (c["title"] or "").strip().casefold() != it["title"].strip().casefold():
            continue
        if c["brain_ref"] and c["brain_ref"] in src_text:
            return c, True
        if "`%s`" % it["source"] in (store.get(c["id"]).get("context") or ""):
            return c, False
    return None, False


def run(args, root, brain, store):
    items = checked(root, brain, args.src, " — nothing imported")
    want = [s for s in (args.only or "").split(",") if s]
    unknown = sorted(set(want) - {it["id"] for it in items})
    if unknown:
        raise CasesError("--only names ids the proposal lacks: %s — nothing imported" % ", ".join(unknown))
    chosen = [i for i in items if not want or i["id"] in want]
    named = {k for i in chosen for k in i.get("own") or {}}
    if named and store.name == "admin" and named - set(store.own()):
        raise CasesError("not an own case field of this admin: %s (see `cases_cli fields`) — nothing imported"
                         % ", ".join(sorted(named - set(store.own()))))
    lines = []
    for it in chosen:
        c, linked = _existing(store, root, it)
        if c is None:
            c = _create(store, root, brain, it)
        if not linked:
            _link(Path(root) / it["source"], c)
        lines.append("%s %s: %s → %s" % ("imported" if not linked else "already", it["id"], c["title"],
                                         c["brain_ref"]))
    return "\n".join(lines) or "nothing selected", 0


def _create(store, root, brain, it):
    path = mdstore.Markdown(root, brain)._new_path(it["title"])
    mdstore.write(path, "Source: `%s`\n" % it["source"])
    keys = ("title", "next_action", "description") + (
        ("recurrence", "anchor_at") if it["kind"] == "recurring" else ("due_at",))
    fields = {k: it[k] for k in keys if k in TRACKED}
    own = it.get("own") or {}
    if own:
        fields.update(own) if store.name == "admin" else fields.update(extra=dict(own))
    try:
        return store.put(None, fields, file=path, title=it["title"])
    except Exception:
        path.unlink(missing_ok=True)  # ours, new: no half-made case file stays behind
        raise


def _link(src, c):
    text = src.read_text(encoding="utf-8")
    sep = "" if text.endswith("\n") else "\n"
    mdstore.write(src, "%s%s\n→ case: %s — brain_ref: %s\n" % (text, sep, c["title"], c["brain_ref"]))
