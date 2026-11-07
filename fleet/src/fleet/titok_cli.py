"""`fleet secrets …` — titok-leltár, tételes jóváhagyás, mozgatás, audit, titok-kapu. Értéket egyik
alparancs sem ír ki.

    scan --agent A [--agent B]     leltár (~/.mentat/titkok/leltar.json) + táblázat; a titok-kaput is
                                   felteszi a box minden Claude-gyökerébe (--no-hook: nem)
    approve --item OP:NÉV:HONNAN:HOVA:MIÉRT … --owner-text "<a tulajdonos szó szerinti igenje>"
    move|copy --name K --from X --to Y --approval ID
    audit [--repo DIR …]           kiszivárgott-e leltárban lévő érték (átiratok, repó, git-történet)
    hook install|status            a titok-kapu felhasználói szintű telepítése / ellenőrzése
    merge-mode on|off|status       az ágens-határ összeolvasztás-módja (hatar_mod.py)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from fleet import titok_jovahagy as J


def cmd_scan(a) -> int:
    from fleet import titok_leltar as L, titok_telepit as T
    repos = dict(r.split("=", 1) for r in a.repo or [] if "=" in r)
    inv = L.scan(a.agent, repos={k: Path(v).expanduser() for k, v in repos.items()})
    path = L.save(inv)
    print(json.dumps(inv, ensure_ascii=False, indent=1) if a.json else L.table(inv))
    print(f"leltár: {path} (0600)", file=sys.stderr)
    if len(set(a.agent)) >= 2:  # a merge 0. lépése: innentől összeolvasztás-mód
        from fleet import hatar_mod
        hatar_mod.safe_on("secrets scan " + "+".join(a.agent), "secrets scan")
    try:
        for note in ([] if a.no_hook else T.install()):
            print(note, file=sys.stderr)
    except T.SelfTestFailed as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_approve(a) -> int:
    try:
        items = [J.parse_item(x) for x in a.item]
        aid = J.create(items, a.owner_text, a.ttl, a.id, owner_msg=a.owner_msg)
    except J.Refused as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 2
    print(aid)
    print(f"jóváhagyás: {len(items)} tétel, {a.ttl} percig, egyszer használható. "
          "v1: ezt a fájlt az ágens is megírhatja — a tulajdonos igenje a csatornán a bizonyíték"
          + ("." if a.owner_msg else "; --owner-msg nélkül az audit önbevallásként jelzi."), file=sys.stderr)
    return 0


def cmd_move(a) -> int:
    from fleet import titok_mozgat as M
    try:
        r = M.run(a.secrets_cmd, a.name, a.src, a.dst, a.approval)
    except J.Refused as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"fleet secrets: fájlhiba ({type(e).__name__}); semmi nem mozdult a nyugta szerint", file=sys.stderr)
        return 1
    print(f"{r['op']} {r['name']}: {r['from']} → {r['to']} (hash8 {r['hash8']}, nyugta: ~/.mentat/titkok/nyugtak.jsonl)")
    return 0


def cmd_audit(a) -> int:
    from fleet import titok_audit as A
    res = A.audit([Path(r).expanduser() for r in a.repo or []])
    if not res.get("error"):
        res["onbevallas"] = J.self_declared()
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else A.report(res))
    return 2 if res.get("error") else (1 if res["leletek"] else 0)


def cmd_hook(a) -> int:
    from fleet import titok_telepit as T
    from fleet import hatar_mod
    try:
        for note in T.install() if a.action == "install" else []:
            print(note)
    except T.SelfTestFailed as e:
        print(f"fleet secrets: {e}", file=sys.stderr)
        return 2
    home = Path.home()
    probs = [p for r in T.roots(home) for p in T.problems(r, home, required=True)]
    if (T.code_dir(home) / "current").exists():
        probs += [f"titok-kapu önteszt: {x}" for x in T.selftest(home)]
    if probs and not T.in_use(home):
        probs.insert(0, "titok-kapu: NINCS telepítve ezen a boxon (sem kód, sem leltár)")
    print("\n".join(probs) if probs else "titok-kapu: minden Claude-gyökérben fent (onFailure: block)")
    print(hatar_mod.status())
    return 1 if probs else 0


def add_parser(sub) -> None:
    s = sub.add_parser("secrets", help="titok-leltár, tételes jóváhagyás, mozgatás, audit, titok-kapu "
                                       "(értéket sosem ír ki)")
    ss = s.add_subparsers(dest="secrets_cmd", required=True)
    x = ss.add_parser("scan", help="titokfájlok neve, helye, formátuma, kulcsnevei — érték nélkül")
    x.add_argument("--agent", action="append", required=True)
    x.add_argument("--repo", action="append", metavar="ÁGENS=DIR", help="ha a registry nem tudja a repót")
    x.add_argument("--json", action="store_true")
    x.add_argument("--no-hook", action="store_true", help="ne telepítse a titok-kaput")
    x.set_defaults(fn=cmd_scan)
    x = ss.add_parser("approve", help="tételes tulajdonosi jóváhagyás (≤60 perc, egyszer használható)")
    x.add_argument("--item", action="append", required=True, metavar="OP:NÉV:HONNAN:HOVA:MIÉRT")
    x.add_argument("--owner-text", required=True,
                   help="a tulajdonos szó szerinti igenje — naplózott önbevallás, nem hitelesítés")
    x.add_argument("--owner-msg", metavar="MSG_ID", help="a tulajdonos igenjét hordozó csatorna-üzenet azonosítója")
    x.add_argument("--ttl", type=int, default=J.MAX_TTL_MIN, metavar="PERC")
    x.add_argument("--id")
    x.set_defaults(fn=cmd_approve)
    for op in J.OPS:
        x = ss.add_parser(op, help=f"egy kulcs ({op}) jóváhagyással; érték nem kerül ki")
        x.add_argument("--name", required=True, help="kulcsnév, vagy '*' = az egész fájl")
        x.add_argument("--from", dest="src", required=True, metavar="ÁGENS|ÚT")
        x.add_argument("--to", dest="dst", required=True, metavar="ÁGENS|ÚT")
        x.add_argument("--approval", required=True)
        x.set_defaults(fn=cmd_move)
    x = ss.add_parser("audit", help="leltárban lévő érték az átiratokban / a repóban / git-történetben")
    x.add_argument("--repo", action="append")
    x.add_argument("--json", action="store_true")
    x.set_defaults(fn=cmd_audit)
    x = ss.add_parser("hook", help="a titok-kapu telepítése a box minden Claude-gyökerébe / ellenőrzése")
    x.add_argument("action", choices=("install", "status"))
    x.set_defaults(fn=cmd_hook)
    from fleet import hatar_mod
    hatar_mod.add_parser(ss)
