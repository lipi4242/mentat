"""11-07: a `fleet doctor` box-sora — ami nem egy ágensé, hanem a gépé.

    box_facts(home, host, release=release_lag.check) -> doctor-riport dict ("box <host>")

  jelentés      a központi flotta-ellenőrzés (flotta_report.py): kikapcsolva (nincs
                 ~/.config/fleet/flotta.env) ⚠, ismeretlen (még nem próbált) ?, elavult ⚠, friss ✓
  riasztási út   van-e kézbesítetlen riasztás a fájlban — az PIROS, amíg ott van: egy riasztás,
                 amit senki nem kapott meg, üzemzavar
  kanári         változtak-e a felhasználói hookok/pluginok/skillek rögzített kanári-futás nélkül (⚠)
  kiadás         régebbi-e a checkout a legújabb publikált kiadásnál (⚠; hálózat nélkül: nem mérhető)
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from fleet import alerts, flotta_report, kanari, release_lag

UNDELIVERED_WINDOW_S = 7 * 86400


def _undelivered(now: float) -> list[dict]:
    try:
        rows = [json.loads(x) for x in alerts.UNDELIVERED.read_text().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    return [r for r in rows if isinstance(r, dict) and now - float(r.get("ts", 0)) < UNDELIVERED_WINDOW_S]


def alert_route(now: float) -> tuple[list[str], list[str], list[str], list[str]]:
    """(problémák, figyelmeztetések, tények, nem-mérhető)."""
    probs, warn, facts, unk = flotta_report.status(now)
    rows = _undelivered(now)
    if rows:
        last = rows[-1]
        probs.append(f"{len(rows)} riasztás NEM ment ki az elmúlt 7 napban ({alerts.UNDELIVERED}); utolsó: "
                     f"{str(last.get('text'))[:200]} — állítsd be a központi jelentést (flotta.env), aztán töröld a fájlt")
    return probs, warn, facts, unk


def box_facts(home: Path, host: str | None, release=release_lag.check, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    probs, warn, facts, unk_route = alert_route(now)
    warn += kanari.drift(home)
    lag, unk, fact = release(home)
    warn += [lag] if lag else []
    facts += [fact] if fact else []
    ok = not probs
    return {"agent": f"box {host or '?'}", "ok": ok, "health": "healthy" if ok else "unhealthy",
            "facts": facts, "problems": probs, "warnings": warn, "pending": [],
            "unknown": unk_route + ([unk] if unk else []), "signals": {}}
