"""The contract read back to the USER in plain words (hu/en): what, from where, to whom, when."""

T = {
    "en": {"head": "Contract %s, version %s (%s).", "goal": "Goal: %s",
           "fields": "Columns: %s, nothing else", "out": "Left out: %s",
           "out_fields": "the column(s) %s", "out_rec": "records where %s", "out_val": "any text containing %s",
           "records": "Records: from %s where %s, one per %s", "all": "every row",
           "who": "Goes to: %s", "from": "only addresses from the records' %s column",
           "allowed": "only %s", "hidden": "recipients cannot see each other",
           "visible": "recipients see each other",
           "window": "Time window: %s – %s, both days included, in %s time%s", "by": " (by the %s column)",
           "defaults": "Defaults for new rows: %s", "empty": "(empty)",
           "checks": "Before it goes out and before I call it done, I check: %s",
           "ask": "Not approved yet. Ask the USER: \"Is this right? A yes approves it.\" — then "
                  "`approve %s --quote \"<their words>\" --version %s`.",
           "ok": "Approved %s by the USER: \"%s\"", "and": " and ", "or": " or ",
           "draft": "draft, not approved", "approved": "approved"},
    "hu": {"head": "%s megállapodás, %s. verzió (%s).", "goal": "Cél: %s",
           "fields": "Oszlopok: %s, más nem", "out": "Kimarad: %s",
           "out_fields": "a(z) %s oszlop", "out_rec": "a rekordok, ahol %s", "out_val": "minden szöveg, amiben %s szerepel",
           "records": "Rekordok: %s, ahol %s; %s szerint egy-egy", "all": "minden sor",
           "who": "Címzettek: %s", "from": "csak a rekordok %s oszlopában lévő címek",
           "allowed": "csak %s", "hidden": "a címzettek nem látják egymást",
           "visible": "a címzettek látják egymást",
           "window": "Időablak: %s – %s, mindkét nap benne van, %s idő szerint%s", "by": " (a(z) %s oszlop alapján)",
           "defaults": "Új sor alapértéke: %s", "empty": "(üres)",
           "checks": "Kiküldés és a „kész” előtt ellenőrzöm: %s",
           "ask": "Még nincs jóváhagyva. Kérdezd meg a FELHASZNÁLÓT: „Így jó? Egy igen jóváhagyja.” — utána "
                  "`approve %s --quote \"<a szavai>\" --version %s`.",
           "ok": "A FELHASZNÁLÓ jóváhagyta (%s): „%s”", "and": " és ", "or": " vagy ",
           "draft": "tervezet, nincs jóváhagyva", "approved": "jóváhagyva"},
}
LABEL = {
    "en": {"fields_exact": "exactly these columns", "no_excluded": "nothing left-out is in it",
           "within_window": "every date is inside the window", "exact_records": "exactly the eligible records",
           "recipients_allowed": "only the agreed recipients", "visibility_hidden": "recipients cannot see each other"},
    "hu": {"fields_exact": "pontosan ezek az oszlopok", "no_excluded": "semmi kizárt nincs benne",
           "within_window": "minden dátum az időablakon belül", "exact_records": "pontosan a jogosult rekordok",
           "recipients_allowed": "csak a megbeszélt címzettek", "visibility_hidden": "a címzettek nem látják egymást"},
}


def _cond(d, s):
    parts = []
    for k, v in d.items():
        v = s["or"].join(map(str, v)) if isinstance(v, list) else v
        parts.append("%s = %s" % (k, v))
    return s["and"].join(parts)


def readback(c, lang):
    s, t, out = T.get(lang, T["en"]), c["terms"], []
    out.append(s["goal"] % t["goal"])
    if t.get("fields"):
        out.append(s["fields"] % ", ".join(t["fields"]))
    ex, left = t.get("exclude") or {}, []
    if ex.get("fields"):
        left.append(s["out_fields"] % ", ".join(ex["fields"]))
    left += [s["out_rec"] % _cond(r, s) for r in ex.get("records", [])]
    left += [s["out_val"] % ('"%s"' % v) for v in ex.get("values", [])]
    if left:
        out.append(s["out"] % "; ".join(left))
    rec = t.get("records")
    if rec:
        where = _cond(rec["where"], s) if rec.get("where") else s["all"]
        out.append(s["records"] % (rec["source"], where, rec["key"]))
    au = t.get("audience")
    if au:
        who = [au["who"]] if au.get("who") else []
        if au.get("from_records"):
            who.append(s["from"] % au["from_records"])
        if au.get("allowed"):
            who.append(s["allowed"] % ", ".join(au["allowed"]))
        if au.get("visibility"):
            who.append(s[au["visibility"]])
        out.append(s["who"] % "; ".join(who))
    w = t.get("window")
    if w:
        out.append(s["window"] % (w["start"], w["end"], w["tz"], s["by"] % w["field"] if w.get("field") else ""))
    if t.get("defaults"):
        out.append(s["defaults"] % ", ".join("%s = %s" % (k, v if v != "" else s["empty"])
                                             for k, v in t["defaults"].items()))
    if t.get("checks"):
        label = LABEL.get(lang, LABEL["en"])
        out.append(s["checks"] % ", ".join(label.get(k, k) for k in t["checks"]))
    lines = [s["head"] % (c["id"], c["version"], s.get(c["status"], c["status"]))] + ["- " + x for x in out]
    if c["status"] == "approved" and c.get("approval"):
        lines.append(s["ok"] % (c["approval"]["at"], c["approval"]["quote"]))
    else:
        lines.append(s["ask"] % (c["id"], c["version"]))
    return "\n".join(lines)
