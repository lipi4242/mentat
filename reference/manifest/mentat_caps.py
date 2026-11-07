"""`mentat_brain.py where --find | --decide | --map`: what already exists, before building.

    where --find "<the request, in the USER's words>" [--json]   candidates + a receipt
    where --decide RECEIPT use|enable|new --candidate ID [--why "…"] [--approved "<USER's yes>"]
    where --map                                                  a generated markdown table
    where --probe ID|all                                         run the capability's real check (TTL)
    where --map --html                                           the same tree as one page (phone, light/dark)
    where --export                                               approved fields only, for the fleet (JSON)

Guide: reference/capabilities.md. The index is the curated suite catalog (capabilities/*.json)
plus the agent's own inventory; availability comes from mentat.json and cheap probes.
"""
import json

import mentat_caps_check as ck
import mentat_caps_html as hx
import mentat_caps_index as ix
import mentat_caps_ki as ki
import mentat_caps_napi as napi
import mentat_caps_probe as pr
import mentat_caps_receipt as rc
import mentat_caps_search as se
import mentat_caps_text as tx

FIELDS = ("provenance", "lifecycle", "scope", "entry", "enable_steps", "limits", "extends")


def view(e, prober, lang, base, checks=None):
    """One capability as the agent sees it: declaration + observation, in its language."""
    c = {"id": e["id"], "category": e["category"], "summary": ix.localize(e["summary"], lang)}
    c.update({k: e.get(k) for k in FIELDS})
    c["docs"] = ix.doc_url(e, lang, base)
    c.update(audience=e.get("audience", "agent"), basic=bool(e.get("basic")), group=e.get("group"),
             say=((e.get("intents") or {}).get(lang) or [""])[0])
    if e.get("user_summary"):
        c["user_summary"] = ix.localize(e["user_summary"], lang)
    if e.get("interim"):
        c["interim"] = ix.localize(e["interim"], lang)
    c.update(prober.state(e["id"]))
    c["enable_steps"] = _steps(e["id"], prober, set()) if c["availability"] != "on" else c["enable_steps"]
    return ck.annotate(c, e, checks if checks is not None else {})


def _steps(cid, prober, seen):
    """A prerequisite that is not on is switched on first: its steps come before ours."""
    e = prober.by_id[cid]
    out = []
    for r in e["requires"]:
        if r not in seen and prober.state(r)["availability"] != "on":
            seen.add(r)
            out += [s for s in _steps(r, prober, seen) if s not in out]
    return out + [s for s in e.get("enable_steps") or [] if s not in out]


def _daily(root, index, prober):
    return napi.changes(root, {e["id"]: prober.state(e["id"])["availability"] for e in index["entries"]})


def find(root, brain, lang, query, as_json):
    index = ix.build(root, brain)
    prober, checks = pr.Prober(root, index["entries"]), ck.load(root)
    hits, near = se.search(index["entries"], query)
    cands = [dict(view(e, prober, lang, index["base"], checks), score=s) for s, e in hits]
    fleet, fmeta = ki.fleet_find(root, query)
    qtok = se.tokens(query)
    cands += sorted([dict(c, score=se.score(qtok, c), requires=[], enable_steps=[], limits=[], extends="",
                          docs="", probe="the fleet's answer (untrusted data)", verified=None) for c in fleet],
                    key=lambda c: -c["score"])[:3]
    rec = rc.recommend(cands)
    out = {"query": query, "receipt": rc.write(root, query, index, cands, rec),
           "index": {"version": index["version"], "hash": index["hash"]},
           "verdict": "candidates" if cands else "inconclusive", "candidates": cands, "recommendation": rec,
           "fallback": {} if cands else {
               "categories": se.categories(index["entries"]),
               "related": [{"id": e["id"], "summary": ix.localize(e["summary"], lang)} for _, e in near],
               "next": tx.T[lang]["next"]}, "changes": _daily(root, index, prober)}
    if fmeta:
        out["fleet"] = fmeta
    print(json.dumps(out, indent=2, ensure_ascii=False) if as_json else tx.find(out, lang))
    return 0


def decide(root, brain, lang, a):
    receipt, decision = a.decide
    index = ix.build(root, brain)
    code, text = rc.decide(root, receipt, decision, index["hash"], a.candidate, a.why, a.approved, tx.T[lang])
    print(text)
    return code


def table(root, brain, lang, html=False):
    index = ix.build(root, brain)
    prober, checks = pr.Prober(root, index["entries"]), ck.load(root)
    views = [view(e, prober, lang, index["base"], checks) for e in index["entries"]]
    by_id = {e["id"]: e for e in index["entries"]}
    if html:
        print(hx.write(root, views, index, lang, by_id))
        return 0
    print(tx.changed(_daily(root, index, prober), lang) + tx.table(views, index, lang, by_id))
    return 0


def probe(root, brain, lang, which):
    """Run the real check of one capability (or of every on/degraded one with `all`)."""
    index = ix.build(root, brain)
    prober = pr.Prober(root, index["entries"])
    pick = [e for e in index["entries"] if e.get("check") and (e["id"] == which or which == "all" and
            prober.state(e["id"])["availability"] in ("on", "degraded"))]
    if not pick:
        print("STOP %s: %s" % (which, tx.T[lang]["nocheck"]))
        return 2
    results = [(e["id"], ck.run(root, e)) for e in pick]
    for cid, r in results:
        print("%s %s: %s" % ("OK" if r["ok"] else "FAIL", cid, r["line"] or "exit %d" % r["exit"]))
    return 0 if all(r["ok"] for _, r in results) else 1


def main(a, root, brain, lang):
    if getattr(a, "probe", None):
        return probe(root, brain, lang, a.probe)
    if a.decide:
        return decide(root, brain, lang, a)
    if getattr(a, "export", False):
        index = ix.build(root, brain)
        print(json.dumps(ki.export(index, pr.Prober(root, index["entries"]), lang), indent=1, ensure_ascii=False))
        return 0
    if a.map:
        return table(root, brain, lang, getattr(a, "html", False))
    return find(root, brain, lang, a.find, a.json)
