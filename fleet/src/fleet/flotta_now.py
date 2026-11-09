"""paritás: `fleet flotta-report` — azonnali jelentés a központi flotta-ellenőrzésnek.

A boxon a reconcile timere 10 percenként jelent; a saját gépen (Claude Desktop/Code) nincs timer és
always-on processz, ezért a futó session maga hívja (pl. induláskor és a saját tickjében). Ugyanazt a
jelentést küldi: a felügyelet nélküli (`supervision: none`) tagokat a desktop-képességpróbával
(todo, saját állapot, git; híd és unit nélkül), a többit a doctor alapfunkció-próbájával méri.
Kilépés: 0 elküldve · 1 nem sikerült · 2 nincs beállítva (flotta.env vagy a gép nincs a registryben).
"""
from __future__ import annotations
import time
from pathlib import Path


def report_now(agents: list[dict] | None = None, host: str | None = None, home: Path | None = None,
               opener=None, measure=None, now: float | None = None) -> tuple[int, str]:
    from fleet import essentials, flotta_report, kepesseg, kepesseg_riaszt
    from fleet.doctor import essentials_for
    home, now = home or Path.home(), time.time() if now is None else now
    if host is None:
        from fleet.registry import local_host
        host = local_host()
    agents = essentials.local_agents() if agents is None else agents
    names = []
    for e in agents:
        if e.get("status") == "dormant":
            continue
        m = (kepesseg.check(e, home, desktop=True) if kepesseg.is_desktop(e) else (measure or essentials_for)(e))
        kepesseg_riaszt.record(e["agent"], m["red"], now, m.get("unknown", []), m.get("ok", m.get("facts", [])))
        names.append(e["agent"])
    if flotta_report.config() is None or not host:
        return 2, "nincs beállítva: ~/.config/fleet/flotta.env (FLOTTA_URL + FLOTTA_TOKEN), vagy a gép nincs a registryben"
    flotta_report.force()
    kw = {"opener": opener} if opener else {}
    res = flotta_report.maybe_report(kepesseg_riaszt._load(), names, host, now, home, **kw)
    return (0, f"elküldve ({len(names)} ágens)") if res == "sent" else (1, f"nem sikerült ({res})")


def cmd(a) -> int:
    rc, msg = report_now()
    print(f"flotta-jelentés: {msg}")
    return rc


def add_parser(sub) -> None:
    x = sub.add_parser("flotta-report", help="azonnali jelentés a központi flotta-ellenőrzésnek (a saját gépen a session hívja; "
                       "a boxon a reconcile timere küldi)")
    x.set_defaults(fn=cmd)
