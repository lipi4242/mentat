"""Rendering of the capability log: markdown per release under the six groups, and the website feed."""

import json

import mentat_caps_index as idx

try:  # the six top-level groups, in the order the README and the website use
    from mentat_caps_ref import GROUPS
except ImportError:  # a catalog from before the groups
    GROUPS = ()

LABEL = {"en": {"new": "New", "extended": "Extended", "improved": "Improved", "removed": "Removed",
                "title": "Capability log", "note": "Generated from `capability-log.json` - do not edit by hand.",
                "unreleased": "not released yet", "other": "Other"},
         "hu": {"new": "Új", "extended": "Bővült", "improved": "Javult", "removed": "Megszűnt",
                "title": "Képesség-napló", "note": "A `capability-log.json`-ból generált fájl, kézzel ne írd.",
                "unreleased": "még nincs kiadva", "other": "Egyéb"}}


def _groups(lang):
    """(key, label) in display order; a capability without a known group goes last."""
    col = 1 if lang == "hu" else 2
    return [(g[0], g[col]) for g in GROUPS] + [(None, LABEL[lang]["other"])]


def render_md(log, catalog, lang):
    """Per release, the capability changes under the six MECE groups of the catalog."""
    caps = {e["id"]: e for e in catalog}
    known = {g[0] for g in GROUPS}

    def group_of(cap):
        g = caps.get(cap, {}).get("group")
        return g if g in known else None

    t = LABEL[lang]
    out = ["# " + t["title"], "", t["note"], ""]
    for rel in log["releases"]:
        out += ["## %s%s" % (rel["version"], " (%s)" % (rel.get("date") or t["unreleased"])), ""]
        for key, label in _groups(lang):
            lines = []
            for ch in rel["changes"]:
                mine = [c for c in ch["capabilities"] if group_of(c["id"]) == key]
                if mine:
                    moved = "; ".join("%s: %s" % (t[k], ", ".join("`%s`" % c["id"] for c in mine if c["change"] == k))
                                      for k in ("new", "extended", "improved", "removed") if any(c["change"] == k for c in mine))
                    lines.append("- %s. %s (%s)" % (ch["title"][lang], ch["summary"][lang], moved))
            if not lines:
                continue
            out += ["### " + label, ""] + lines
            out.append("")
    return "\n".join(out)


def render_json(log, catalog):
    caps = {e["id"]: e for e in catalog}
    feed = {"schema": 1, "generated_by": "mentat_caplog.py", "releases": log["releases"], "capabilities": {},
            "groups": [{"key": g[0], "label": {"hu": g[1], "en": g[2]}} for g in GROUPS]}
    for rel in log["releases"]:
        for ch in rel["changes"]:
            for c in ch["capabilities"]:
                e = caps.get(c["id"], {})
                node = feed["capabilities"].setdefault(c["id"], {
                    k: e.get(k) for k in ("group", "category", "lifecycle", "summary", "user_summary", "audience")})
                node.setdefault("history", []).append({"version": rel["version"], "change": c["change"],
                                                       "change_id": ch["id"], "title": ch["title"]})
    return json.dumps(feed, indent=2, ensure_ascii=False) + "\n"
