"""Egy ágens egy helyen — duplikáció-felismerés, fencing nélkül.

Ugyanaz az ágens két gépen (pl. Mac + box) eddig csak tünetből derült ki:
kettős válasz, vagy a Telegram 409-e (két poller egy bot-tokenen). Itt két
közvetlen jel:

  * egy MÁSIK gépre rendelt ágens (registry `host`) claude-processze EZEN a
    gépen fut (`--remote-control <rc_name>`);
  * a csatorna 409-e: a saját hídunk mellett valaki más is pollol — lehet egy
    másik gép ugyanazzal a tokennel.

Csak riaszt. Kizárás (fencing) nincs: egy idegen gép processzét innen nem
lehet biztonságosan leállítani, a helyit pedig ember döntse el, melyik az igazi.
"""
from __future__ import annotations

from fleet.signals import find_agent_process

HINT_409 = ("409: ugyanazon a bot-tokenen más is pollol — ha a saját gépen nincs "
            "plugin-poller, egy másik gépen futhat ugyanez az ágens")


def foreign_here(agents: list[dict], host: str | None, procs: list[dict]) -> list[tuple[dict, int]]:
    """Pure: [(bejegyzés, pid)] — más hostra rendelt ágensek, amelyek itt futnak.
    Ismeretlen host (None) vagy host nélküli bejegyzés: nem ítélünk."""
    if host is None or not procs:
        return []
    out = []
    for e in agents:
        if not e.get("host") or e["host"] == host:
            continue
        p = find_agent_process(e, procs)
        if p is not None:
            out.append((e, p["pid"]))
    return out


def dup_message(e: dict, pid: int, host: str) -> str:
    return (f"⚠️ {e['agent']}: a registry szerint a(z) {e['host']!r} gépen fut, de EZEN a gépen "
            f"({host!r}) is fut egy példánya (pid {pid}) — két helyen futó ágens kettős választ ad. "
            "Állítsd le az egyiket (`fleet doctor`), vagy javítsd a registry host mezőjét")
