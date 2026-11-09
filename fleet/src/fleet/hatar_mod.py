"""`fleet secrets merge-mode on|off|status` — az ágens-határ összeolvasztás-módjának EGYETLEN írója.

A jelző: ~/.mentat/titkok/hatar-aktiv (JSON: since, until, reason, set_by). A titok-kapu hookja
(security/eszkozok/identitas/hatar_jel.py) olvassa: amíg él, a git-írás más ágens fő ágán, a helyi
`tmux send-keys`, és a kifelé ható parancs más ágens kódjával tilos. Jelző nélkül ezek szabadok,
mert a kiadó ágensek (Rilí) minden tickben `git reset --hard`-ot és commitot futtatnak a kezelt
repók fő ágán (CISO Q2). Legfeljebb 7 nap; a lejárt jelző = nincs mód.

Írja: `fleet plan-merge` (az összeolvasztás eleje), `fleet hold-outward`, `merge-mode on`. A
`fleet secrets scan` SOHA (11-07, 11-07: egy kétágenses leltár 7 napra boxszinten bekapcsolta,
és Rilí minden tickben fő ágat író gitje bukott volna). `off(set_by=X)` csak X okát veszi le; ha más ok marad,
a jelző marad. A kézi `merge-mode off` mindet leveszi.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

from fleet import titok_hely as H

MAX_DAYS = 7


def path(home: Path | None = None) -> Path:
    return H.base(home) / "hatar-aktiv"


def read(home: Path | None = None, now: float | None = None) -> dict | None:
    """Az ÉLŐ jelző, vagy None (nincs, lejárt, hibás, 7 napnál hosszabb)."""
    now = time.time() if now is None else now
    try:
        d = json.loads(path(home).read_text())
        since, until = float(d["since"]), float(d["until"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    ok = since <= now + 60 and now < until and until - since <= MAX_DAYS * 86400 + 60
    return d if ok else None


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def on(reason: str, set_by: str, until: float | None = None, home: Path | None = None,
       now: float | None = None) -> dict:
    now = time.time() if now is None else now
    cap = now + MAX_DAYS * 86400
    old = read(home, now) or {}
    until = min(cap, max(until or cap, float(old.get("until", 0))))
    by = list(dict.fromkeys([*old.get("set_by", []), set_by]))
    reasons = [r for r in (old.get("reason", ""), reason) if r]
    doc = {"since": now, "until": until, "reason": "; ".join(dict.fromkeys(reasons)), "set_by": by,
           "until_local": _iso(until)}
    H.write_atomic(path(home), json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return doc


def off(set_by: str | None = None, home: Path | None = None, now: float | None = None) -> str:
    p = path(home)
    old = read(home, now)
    if old is None:
        p.unlink(missing_ok=True)
        return "nincs élő összeolvasztás-mód"
    rest = [] if set_by is None else [b for b in old.get("set_by", []) if b != set_by]
    if rest:
        old["set_by"] = rest
        H.write_atomic(p, json.dumps(old, ensure_ascii=False, indent=1) + "\n")
        return f"összeolvasztás-mód marad ({', '.join(rest)} miatt)"
    p.unlink(missing_ok=True)
    return "összeolvasztás-mód kikapcsolva"


def status(home: Path | None = None) -> str:
    d = read(home)
    if not d:
        return "ágens-határ: alap mód (unit-, szabály- és registry-írás tilos; git/tmux/kifelé szabad)"
    return (f"ágens-határ: ÖSSZEOLVASZTÁS-MÓD {d.get('until_local') or _iso(float(d['until']))}-ig "
            f"({', '.join(d.get('set_by', []))}: {d.get('reason', '')})")


def safe_on(reason: str, set_by: str, until: float | None = None) -> None:
    """A többi parancs hívja: a jelző hibája nem buktatja el a fő műveletet, de látszik."""
    try:
        on(reason, set_by, until)
        print(f"!!! BOXSZINTŰ: az összeolvasztás-mód BE ({set_by}) — a box MINDEN ágensére: más ágens fő "
              "ágán git-írás, tmux send-keys, kifelé ható parancs más kódjával tiltva. Kikapcsolás: "
              "`fleet secrets merge-mode off`", file=sys.stderr)
        print(status(), file=sys.stderr)
    except OSError as e:
        print(f"! az összeolvasztás-mód jelzője nem íródott ki ({type(e).__name__})", file=sys.stderr)


def safe_off(set_by: str) -> None:
    try:
        print(off(set_by), file=sys.stderr)
    except OSError as e:
        print(f"! az összeolvasztás-mód jelzője nem törölhető ({type(e).__name__})", file=sys.stderr)


def cmd(a) -> int:
    if a.state == "on":
        on(a.reason or "kézi", "kézi", time.time() + a.days * 86400)
    elif a.state == "off":
        print(off())
    print(status())
    return 0


def add_parser(ss) -> None:
    x = ss.add_parser("merge-mode", help="az ágens-határ összeolvasztás-módja (git/tmux/kifelé tiltás) "
                                         "be/ki/állapot; legfeljebb 7 nap")
    x.add_argument("state", choices=("on", "off", "status"))
    x.add_argument("--reason")
    x.add_argument("--days", type=float, default=MAX_DAYS)
    x.set_defaults(fn=cmd)
