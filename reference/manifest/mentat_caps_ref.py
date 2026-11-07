"""The capability tree as a reference (Krisz, 2026-10-24): one structure for `--map` (markdown) and
`--map --html`. Four sections, in this order:

    neked      what the USER gets (audience: user), in their words, with an example to say
    agens      what the agent needs to decide (audience: agent): entry, prerequisites, limits, extends
    projektek  the agent's own work and external tools (provenance own / external)
    alap       the basics (basic: true), folded away at the end

Each row also says where the capability is defined (`source`): the tool file in the bootstrap
(reference/…), the engine module, or the docs; for own work, its path in the repo.
"""
import re

ORDER = ("neked", "agens", "projektek", "alap")
TITLES = {
    "hu": {"neked": "Neked: mit kapsz", "agens": "Az ágensnek: technikai képességek",
           "projektek": "Projektek és saját eszközök", "alap": "Alapfunkciók"},
    "en": {"neked": "For you: what you get", "agens": "For the agent: technical capabilities",
           "projektek": "Projects and own tools", "alap": "Basics"},
}
# The human top level, MECE, the same as on the website and in the README (Krisz, 2026-10-24):
# every catalog entry has exactly one `group`; the agent rows sit under the same groups.
GROUPS = (
    ("memoria", "Memória és tudás", "Memory and knowledge"),
    ("proaktiv", "Proaktivitás és ütemezés", "Proactivity and scheduling"),
    ("munka", "Munkavégzés és projektek", "Work and projects"),
    ("kulvilag", "Kapcsolat a külvilággal", "Connection to the outside world"),
    ("biztonsag", "Biztonság és kontroll", "Safety and control"),
    ("mukodes", "Működés és rugalmasság", "Operation and flexibility"),
)
GROUP_KEYS = tuple(g[0] for g in GROUPS)
BIN = re.compile(r"\.mentat/bin/((?:web/|bekotes/)?[\w.-]+\.py)")


def source(v, e):
    """Where it is defined: a bootstrap file, an engine module, the fleet, or the docs."""
    if v["provenance"] != "suite":
        return v.get("entry") or ""
    m = BIN.search(" ".join([v.get("entry") or ""] + [str(x) for x in e.get("probe", {}).values()]))
    p = e.get("probe") or {}
    if "bin" in p or m:
        name = m.group(1) if m else p["bin"]
        folder = {"web": "reference/web", "bekotes": "reference/bekotes"}.get(name.split("/")[0], "reference/manifest")
        return "%s/%s" % (folder, name.split("/")[-1])
    if "module" in p:
        pkg, _, mod = p["module"].partition(".")
        return "engine/src/%s/%s.py" % (pkg, mod or "__init__")
    if "plugin" in p:
        return "engine/src/%s/" % p["plugin"]
    if "local" in p and p["local"].startswith("fleet"):
        return "fleet/"
    return v.get("docs") or ""


def section(v):
    if v["provenance"] != "suite":
        return "projektek"
    if v.get("basic"):
        return "alap"
    return "neked" if v.get("audience") == "user" else "agens"


def rows(views, entries_by_id):
    """{section: [view + source, sorted: on first, then by id]} in ORDER."""
    rank = {"on": 0, "degraded": 1, "available": 2, "off": 3, "unknown": 4}
    out = {k: [] for k in ORDER}
    for v in views:
        out[section(v)].append(dict(v, source=source(v, entries_by_id.get(v["id"], {}))))
    for k in out:
        out[k].sort(key=lambda v: (_g(v), v.get("lifecycle") == "planned", rank.get(v["availability"], 5), v["id"]))
    return out


def _g(v):
    return GROUP_KEYS.index(v["group"]) if v.get("group") in GROUP_KEYS else len(GROUP_KEYS)


def group_title(key, lang):
    return next((g[1] if lang == "hu" else g[2] for g in GROUPS if g[0] == key), key or "")


def name(v):
    """The row's title: the USER's words in `neked`, the summary elsewhere."""
    return v.get("user_summary") or v["summary"]
