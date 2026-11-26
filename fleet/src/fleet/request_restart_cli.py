"""`fleet request-restart [ágens]` — az ágens SAJÁT újraindítás-kérése, systemctl nélkül.

Az ágens (a flottamenedzser is) nem indítja újra magát: a saját sessionjéből
hívott systemctl a kérő kört is megszakítja, és a crash-költségvetés sem látja.
Ez a parancs csak jelölőt tesz le (requested_stop.mark_restart); a reconcile-
timer a kérő kör vége után (rövid tétlenség) `--resume`-mal indítja újra, a
resume-kereten belül, postcheckkel, és az első üzenetben megmondja, miért.

Csak a hívó saját ágensére: a $FLEET_AGENT (a unit állítja), ennek híján az az
ágens, amelynek registry-workdirje a hívó munkakönyvtára (vagy őse). Másik
ágensre nem kérhető. Kilépési kód: 0 jelölő letéve · 2 nem azonosítható / nem a sajátod.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

from fleet import registry, requested_stop
from fleet.agentctl import _fmt, reconcile_period_s


def own_agent(cwd: Path | None = None, env=os.environ, agents=None) -> str | None:
    name = (env.get("FLEET_AGENT") or "").strip()
    if name:
        return name
    here = (cwd or Path.cwd()).resolve()
    hits = []
    for e in (agents if agents is not None else registry.load_agents()):
        try:
            wd = Path(e.get("workdir") or "").resolve()
        except OSError:
            continue
        if e.get("workdir") and (here == wd or wd in here.parents):
            hits.append((len(wd.parts), e["agent"]))
    return max(hits)[1] if hits else None


def cmd_request_restart(a) -> int:
    me = own_agent()
    target = a.agent or me
    if me is None or target != me:
        print(f"csak a saját ágensed újraindítását kérheted (te: {me or 'nem azonosítható'}, "
              f"kért: {target})", file=sys.stderr)
        return 2
    if registry.get_agent(me) is None:
        print(f"nincs ilyen ágens a registryben: {me}", file=sys.stderr)
        return 2
    p = requested_stop.mark_restart(me)
    print(f"{me}: újraindítás kérve ({p.name}). A fleet-reconcile a kör befejezése után "
          f"`--resume`-mal indítja újra (a timer periódusa {_fmt(reconcile_period_s())}); a beszélgetés megmarad.")
    return 0


def add_parser(sub) -> None:
    x = sub.add_parser("request-restart", help="a SAJÁT ágensed újraindításának kérése: a reconcile a kör vége "
                                               "után --resume-mal indítja újra (saját systemctl helyett)")
    x.add_argument("agent", nargs="?", help="alapból a saját ágensed ($FLEET_AGENT / a munkakönyvtár)")
    x.set_defaults(fn=cmd_request_restart)
