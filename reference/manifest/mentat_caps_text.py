"""Human output of the capability tree: the `--find` answer and the `--map` table (HU/EN)."""

T = {
    "hu": {"head": "Képességfa: „%s” — %d jelölt · nyugta: %s", "entry": "belépés", "enable": "bekapcsolás",
           "req": "előfeltétel", "limits": "korlát", "extends": "bővítés", "docs": "doksi", "probe": "próba",
           "interim": "teendő most", "rec": "Ajánlás", "decide": "Döntés",
           "decide_cmd": "python3 .mentat/bin/mentat_brain.py where --decide %s use|enable|new --candidate <id> "
                         "[--why \"mi hiányzik a legközelebbi jelöltből\"]",
           "none": "Képességfa: „%s” — nincs találat: NEM DÖNTHETŐ, ez nem engedély az építésre · nyugta: %s",
           "cats": "Tágabb kategóriák", "near": "Rokon (gyenge találat)",
           "next": "Futtasd újra más szavakkal vagy egy kategória nevével. Ha így sincs, kérdezd a FELHASZNÁLÓt, "
                   "és csak az igenjével: where --decide <nyugta> new --why \"…\" --approved \"<a szava>\"",
           "map": "Képességfa — index v%s · %s", "cols": "| id | mit tud | hol van | állapot | belépés |",
           "cols_user": "| id | mit kapsz | hol van | állapot | mondd például |",
           "stale": "az index változott a nyugta óta: futtasd újra a where --find-ot",
           "not_in": "nem jelöltje ennek a nyugtának", "nothing": "nincs mit használni: a keresés nem volt dönthető",
           "why": "mi hiányzik a legközelebbi jelöltből, egy mondatban",
           "undecidable": "nem dönthető: a new-hoz a FELHASZNÁLÓ igenje kell, szó szerint (--approved)",
           "changed": "Változás az előző nap óta", "nocheck": "ennek nincs ellenőrzője (where --probe)",
           "verified": "ellenőrizve", "stale": "elavult"},
    "en": {"head": "Capability tree: \"%s\" — %d candidate(s) · receipt: %s", "entry": "entry", "enable": "enable",
           "req": "requires", "limits": "limits", "extends": "extend at", "docs": "docs", "probe": "probe",
           "interim": "do this now", "rec": "Recommendation", "decide": "Decide",
           "decide_cmd": "python3 .mentat/bin/mentat_brain.py where --decide %s use|enable|new --candidate <id> "
                         "[--why \"what the closest candidate lacks\"]",
           "none": "Capability tree: \"%s\" — no hit: NOT DECIDABLE, this is not a licence to build · receipt: %s",
           "cats": "Broader categories", "near": "Related (weak match)",
           "next": "Run it again with other words or a category name. If still nothing, ask the USER, and only "
                   "on their yes: where --decide <receipt> new --why \"…\" --approved \"<their words>\"",
           "map": "Capability tree — index v%s · %s", "cols": "| id | what it does | where | state | entry |",
           "cols_user": "| id | what you get | where | state | say for example |",
           "stale": "the index changed since this receipt: run where --find again",
           "not_in": "not a candidate of this receipt", "nothing": "nothing to use: the search was inconclusive",
           "why": "what the closest candidate lacks, in a sentence",
           "undecidable": "not decidable: new needs the USER's yes, verbatim (--approved)",
           "changed": "Changed since the last day", "nocheck": "it has no check (where --probe)",
           "verified": "checked", "stale": "stale"},
}


def _line(c):
    return "%s [%s · %s%s] %s" % (c["id"], c["provenance"], c["availability"],
                                  " · planned" if c["lifecycle"] == "planned" else "", c["summary"])


def changed(lines, lang):
    return "%s: %s\n" % (T[lang]["changed"], "; ".join(lines)) if lines else ""


def find(out, lang):
    t = T[lang]
    return changed(out.get("changes") or [], lang) + _find(out, t)


def _find(out, t):
    if not out["candidates"]:
        fb = out["fallback"]
        rows = [t["none"] % (out["query"], out["receipt"]),
                "%s: %s" % (t["cats"], ", ".join("%s (%d)" % c for c in fb["categories"]))]
        if fb["related"]:
            rows.append("%s: %s" % (t["near"], "; ".join("%s — %s" % (r["id"], r["summary"]) for r in fb["related"])))
        return "\n".join(rows + [fb["next"]])
    top, rest = out["candidates"][0], out["candidates"][1:]
    rows = [t["head"] % (out["query"], len(out["candidates"]), out["receipt"]), "1. " + _line(top)]
    if top.get("interim"):
        rows.append("   %s: %s" % (t["interim"], top["interim"]))
    for key, label in (("entry", "entry"), ("enable_steps", "enable"), ("requires", "req"),
                       ("limits", "limits"), ("extends", "extends"), ("docs", "docs"), ("probe", "probe")):
        val = top.get(key)
        if key == "requires":
            val = ", ".join("%s (%s)" % (r["id"], r["availability"]) for r in val)
        elif isinstance(val, list):
            val = "; ".join(val)
        if val and not (key == "enable_steps" and top["availability"] == "on"):
            rows.append("   %s: %s" % (t[label], val))
    v = top.get("verified")
    if v:
        rows.append("   %s: %s %s%s" % (t["verified"], "OK" if v["ok"] else "FAIL", v["at"],
                                         " (%s)" % t["stale"] if v["stale"] else ""))
    for i, c in enumerate(rest, 2):
        rows.append("%d. %s%s" % (i, _line(c), " — %s" % c["entry"] if c.get("entry") else ""))
    rec = out["recommendation"]
    rows.append("%s: %s %s%s" % (t["rec"], rec["decision"], rec.get("candidate", ""),
                                 " (interim)" if rec.get("via") else ""))
    rows.append("%s: %s" % (t["decide"], t["decide_cmd"] % out["receipt"]))
    return "\n".join(rows)


def table(views, index, lang, by_id):
    """The reference as markdown: the four sections of mentat_caps_ref, a table each."""
    import mentat_caps_ref as ref
    t, secs = T[lang], ref.rows(views, by_id)
    head = {"neked": t["cols_user"], "agens": t["cols"], "projektek": t["cols"], "alap": t["cols"]}
    out = ["# " + t["map"] % (index["version"], index["hash"])]
    for key in ref.ORDER:
        out += ["", "## %s (%d)" % (ref.TITLES[lang][key], len(secs[key])), "", head[key], "|---|---|---|---|---|"]
        grp = None
        for c in secs[key]:
            if key != "projektek" and c.get("group") != grp:
                grp = c.get("group")
                out.append("| **%s** | | | | |" % ref.group_title(grp, lang))
            last = "„%s”" % c["say"] if key == "neked" and c.get("say") else ("`%s`" % c["entry"] if c.get("entry") else "—")
            cells = [c["id"], ref.name(c), c["source"] or "—",
                     c["availability"] + (" · planned" if c["lifecycle"] == "planned" else ""), last]
            out.append("| %s |" % " | ".join(str(x).replace("|", "\\|") for x in cells))
    return "\n".join(out)
