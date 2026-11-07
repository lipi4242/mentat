"""`where --map --html`: the capability tree as a friendly reference page (Krisz, 2026-10-24), not a
graph. The sections and rows come from mentat_caps_ref; each row is a <details>: closed it is one
line (what it does, its state), opened it says what it is for, an example, where it lives, and
for the agent the entry, prerequisites, limits and extension point. kepessegfa-map.html is the
shell (theme, layout); nothing is loaded from the net; it works on a phone, light and dark.
"""
import html
import pathlib
import time

import mentat_caps_ref as ref

HERE = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(".mentat") / "state" / "kepessegfa.html"
L = {
    "hu": {"title": "Képességfa", "tap": "Koppints egy sorra a részletekért.", "what": "Mire jó", "say": "Mondd például",
           "entry": "Belépés", "req": "Előfeltétel", "limits": "Korlát", "extends": "Bővítés", "where": "Hol van",
           "docs": "Doksi", "probe": "Állapot", "checked": "Mit nézett meg", "until": "Addig", "id": "Azonosító",
           "state": {"on": "bekapcsolva", "available": "bekapcsolható", "degraded": "hiányos", "off": "nincs itt",
                     "planned": "tervezett", "unknown": "ismeretlen"}},
    "en": {"title": "Capability tree", "tap": "Tap a row for details.", "what": "What it is for", "say": "Say for example",
           "entry": "Entry", "req": "Requires", "limits": "Limits", "extends": "Extend at", "where": "Where",
           "docs": "Docs", "probe": "State", "checked": "What was checked", "until": "Until then", "id": "Id",
           "state": {"on": "on", "available": "can be switched on", "degraded": "degraded", "off": "not here",
                     "planned": "planned", "unknown": "unknown"}},
}
e = html.escape


def _row(v, key, t):
    st = "planned" if v.get("lifecycle") == "planned" else v["availability"]
    sub = "" if key == "projektek" else "<small>%s</small>" % e(v["id"])
    dl = [(t["what"], e(v["summary"]))]
    if key == "neked" and v.get("say"):
        dl.append((t["say"], "„%s”" % e(v["say"])))
    if v.get("interim"):
        dl.append((t["until"], e(v["interim"])))
    if key != "neked" and v.get("entry"):
        dl.append((t["entry"], "<code>%s</code>" % e(v["entry"])))
    if key in ("agens", "alap"):  # the technical part is for the agent's rows
        for k, label in (("requires", "req"), ("limits", "limits"), ("extends", "extends")):
            val = v.get(k)
            val = ", ".join("%s (%s)" % (r["id"], r["availability"]) for r in val) if k == "requires" else \
                "; ".join(val) if isinstance(val, list) else val
            if val:
                dl.append((t[label], e(val)))
    dl += [(t["where"], "<code>%s</code>" % e(v["source"])) if v.get("source") else None,
           (t["docs"], e(v["docs"])) if v.get("docs") and key != "projektek" else None,
           (t["probe"], e(t["state"].get(st, st))), (t["checked"], e(v.get("probe") or "")) if v.get("probe") else None,
           (t["id"], e(v["id"]))]
    body = "".join("<dt>%s</dt><dd>%s</dd>" % x for x in dl if x)
    return ('<details class="row" id="%s"><summary><span class="nm">%s%s</span><span class="st st-%s">%s</span></summary>'
            '<div class="more"><dl>%s</dl></div></details>' % (e(v["id"]), e(ref.name(v)), sub, e(st),
                                                                  e(t["state"].get(st, st)), body))


def body(views, index, lang, by_id, who=""):
    t, secs = L[lang], ref.rows(views, by_id)
    out = ["<h1>%s</h1>" % e(t["title"]), '<p class="sub">%s · index v%s · %s · %s</p>' % (
        e(who or "Mentat"), e(index["version"]), time.strftime("%Y-%m-%d"), e(t["tap"]))]
    for key in ref.ORDER:
        rows, last = [], None
        for v in secs[key]:
            if key != "projektek" and v.get("group") != last:
                last = v.get("group")
                rows.append('<h3 class="grp">%s</h3>' % e(ref.group_title(last, lang)))
            rows.append(_row(v, key, t))
        rows = "".join(rows)
        head = "%s (%d)" % (ref.TITLES[lang][key], len(secs[key]))
        if key == "alap":
            out.append('<section id="alap"><details class="alap"><summary>%s</summary>%s</details></section>'
                       % (e(head), rows))
        else:
            out.append('<section id="%s"><h2>%s</h2>%s</section>' % (key, e(head), rows))
    return "\n".join(out)


def write(root, views, index, lang, by_id, who=""):
    page = (HERE / "kepessegfa-map.html").read_text(encoding="utf-8")
    page = page.replace("/*BODY*/", body(views, index, lang, by_id, who))
    page = page.replace('<html lang="hu">', '<html lang="%s">' % lang)
    page = page.replace("<title>Képességfa</title>", "<title>%s</title>" % L[lang]["title"])
    path = pathlib.Path(root) / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return OUT.as_posix()
