"""`fleet hold-outward <ágens> --until +4h --reason "…"` / `fleet release-outward <ágens>`.

Kifelé-tartás: amíg egy fejlesztő egy élő ágensbe épít, az ágens senkinek nem írhat.
H5 (2026-10): a fejlesztő a fogadó élő tickjét futtatta --dry-run nélkül, és a fogadó
valódi emlékeztetőt küldött a csapat-csoportba építés közben. Az eljárás szövege nem
tartott, ezért az ÁLLAPOTOT védjük: a jelzőt a motor olvassa (anytime_engine/hold.py),
és amíg él, minden tick dry-run, a kézbesítő csak előnézetet mutat, a Telegram-csatorna
nem küld. A jelzőt ez a modul írja az ágens repójába, helyben vagy ssh-n (remote.py),
a box saját python3-jával (outward_hold_box.py).
"""
from __future__ import annotations
import getpass
import json
import re
import shlex
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fleet.remote import Target, resolve

BOX = Path(__file__).with_name("outward_hold_box.py")
MAX_HOURS = 24
_REL = re.compile(r"^\+(\d+)([mhd])$")
_UNIT = {"m": "minutes", "h": "hours", "d": "days"}


def parse_until(text: str, now: datetime | None = None) -> datetime:
    """`+30m`, `+4h`, `+1d` vagy ISO (zóna nélkül: ennek a gépnek a helyi ideje).
    A jövőben kell lennie, és legfeljebb 24 órára — egy elfelejtett tartás se némítson tovább."""
    now = now or datetime.now(timezone.utc)
    m = _REL.match(text.strip())
    if m:
        until = now + timedelta(**{_UNIT[m[2]]: int(m[1])})
    else:
        try:
            until = datetime.fromisoformat(text.strip())
        except ValueError:
            raise ValueError(f"--until: nem értem: {text!r} (példa: +4h, +30m, 2026-10-29T18:00)") from None
        until = until if until.tzinfo else until.astimezone()
    if until <= now:
        raise ValueError(f"--until: a múltban van ({until.isoformat(timespec='seconds')})")
    if until - now > timedelta(hours=MAX_HOURS):
        raise ValueError(f"--until: legfeljebb {MAX_HOURS} óra (a motor úgyis levágja) — hosszabb "
                         "munkához tedd fel újra, amikor lejár")
    return until


def _box(tgt: Target, spec: dict) -> dict:
    r = tgt.sh("python3 - " + shlex.quote(json.dumps(spec, ensure_ascii=False)),
               stdin=BOX.read_text(), timeout=60)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else \
            {"ok": False, "error": f"a box nem válaszolt (kód {r.returncode}): {(r.stderr or '').strip()[-300:]}"}
    except (ValueError, IndexError):
        return {"ok": False, "error": f"értelmezhetetlen válasz: {(r.stdout or '')[-200:]}"}


def _where(name: str, ssh: str | None, workdir: str | None, resolver) -> tuple[str, Target]:
    entry, tgt = resolver(name, ssh=ssh)
    wd = workdir or (entry or {}).get("workdir")
    if not wd:
        raise ValueError(f"{name}: nem tudom, hol a repója — nincs a registryben; add meg: --workdir")
    return wd, tgt


def hold(name: str, until: str, reason: str, *, ssh=None, workdir=None, resolver=resolve,
         now: datetime | None = None) -> dict:
    t = parse_until(until, now)
    wd, tgt = _where(name, ssh, workdir, resolver)
    marker = {"until": t.isoformat(timespec="seconds"), "reason": reason,
              "set_by": f"fleet hold-outward ({getpass.getuser()}@{socket.gethostname()})",
              "set_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}
    r = _box(tgt, {"op": "set", "workdir": wd, "marker": marker})
    return dict(r, agent=name, target=tgt.label)


def release(name: str, *, ssh=None, workdir=None, resolver=resolve) -> dict:
    wd, tgt = _where(name, ssh, workdir, resolver)
    return dict(_box(tgt, {"op": "release", "workdir": wd}), agent=name, target=tgt.label)


def show(tgt: Target, workdir: str) -> dict:
    """A probe-nak: a jelző a box szemével (csak olvas)."""
    r = _box(tgt, {"op": "show", "workdir": workdir})
    return r.get("hold") or {"error": r.get("error")}


def line(h: dict | None) -> str:
    """Egy sor a probe-ba és a doctorba."""
    if not h or h.get("error"):
        return "kifelé:   nem mérhető" + (f" ({h['error']})" if h and h.get("error") else "")
    if h.get("active"):
        why = "; ".join(x for x in (h.get("reason"), h.get("set_by")) if x)
        return f"kifelé:   TARTÁS AKTÍV — dry-run, eddig: {h['until']}" + (f" ({why})" if why else "")
    if h.get("present"):
        return f"kifelé:   nincs tartás (lejárt jelző: {h['until']} — `fleet release-outward` törli)"
    return "kifelé:   nincs tartás"
