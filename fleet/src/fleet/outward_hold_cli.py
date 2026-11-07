"""A kifelé-tartás két parancsa (outward_hold.py): `fleet hold-outward` és `fleet release-outward`."""
from __future__ import annotations
import json
import sys

from fleet import hatar_mod, outward_hold as oh


def cmd_hold(a) -> int:
    try:
        r = oh.hold(a.agent, a.until, a.reason, ssh=a.ssh, workdir=a.workdir)
    except ValueError as e:
        print(f"hold-outward: {e}", file=sys.stderr)
        return 2
    if r.get("ok"):
        hatar_mod.safe_on(f"hold-outward {a.agent}", "hold-outward")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif not r.get("ok"):
        print(f"{a.agent} @ {r['target']}: a jelző NEM íródott ki — {r.get('error')}", file=sys.stderr)
    else:
        print(f"{a.agent} @ {r['target']}\n  {oh.line(r['hold'])}\n  jelző: {r['hold']['path']}\n"
              f"  feloldás: fleet release-outward {a.agent}")
        if not r.get("engine_knows"):
            print("  ! a motor NEM ismeri a kifelé-tartást (nincs anytime_engine.hold) — a jelző hatástalan; "
                  "frissítsd a motort, mielőtt az élő ágensbe építesz", file=sys.stderr)
    return 0 if r.get("ok") and r.get("engine_knows") else 1


def cmd_release(a) -> int:
    try:
        r = oh.release(a.agent, ssh=a.ssh, workdir=a.workdir)
    except ValueError as e:
        print(f"release-outward: {e}", file=sys.stderr)
        return 2
    if r.get("ok"):
        hatar_mod.safe_off("hold-outward")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif r.get("ok"):
        print(f"{a.agent} @ {r['target']}: kifelé-tartás feloldva"
              + ("" if r.get("removed") else " (nem is volt jelző)"))
    else:
        print(f"{a.agent} @ {r['target']}: NEM sikerült feloldani — {r.get('error')}", file=sys.stderr)
    return 0 if r.get("ok") else 1


def _common(x) -> None:
    x.add_argument("agent", metavar="ágens")
    x.add_argument("--ssh", metavar="user@box", help="a box, ha az ágens nincs (ezen a gépen) a registryben")
    x.add_argument("--workdir", help="az ágens repója a boxon (alap: a registry workdir-je; %%h = HOME)")
    x.add_argument("--json", action="store_true")


def add_parser(sub) -> None:
    x = sub.add_parser("hold-outward", help="kifelé-tartás: amíg él, az ágens minden tickje dry-run, "
                                            "semmi nem megy ki (építés egy élő ágensbe)")
    _common(x)
    x.add_argument("--until", required=True, metavar="ISO|+4h", help="meddig (legfeljebb 24 óra)")
    x.add_argument("--reason", required=True, help="miért — a tick-kimenetben és a doctorban látszik")
    x.set_defaults(fn=cmd_hold)
    x = sub.add_parser("release-outward", help="a kifelé-tartás feloldása")
    _common(x)
    x.set_defaults(fn=cmd_release)
