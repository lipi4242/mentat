"""A flotta timerén futó tick felügyelete (LG1 szinergia-mátrix: motor + flotta
→ „a flotta veszi át a tick ütemezését, és a `last-tick.json`-t felügyeli").

Elfogadási mérés 2026-10-15 (06-flotta): `schedule_owner: fleet` mellett az
ágens `proactive: false` volt, ezért a schedule-jel `n/a` lett — a tick a
flotta timerén futott, de ha elakad, senki nem riaszt. A proactive a claude-
session saját loopjáról szól; a flotta timere ettől független kérdés.

Itt nincs új frissesség-szabály: az ítélet a meglévő
`signals.schedule_verdict` (periódus × TICK_STALE_FACTOR), a riasztás a
reconcile meglévő csend-riasztása (SILENCE_PERIODS / silence_after_s). Ez a
modul csak a bemenetet adja: a tick kora, a periódus, és mióta élesített.
"""
from __future__ import annotations
import re
from pathlib import Path

from fleet import mentat_manifest as mm
from fleet.liveness import state_path
from fleet.tick_schedule import tick_unit

DEFAULT_PERIOD_S = 3600.0   # a tick_schedule alapértelmezett ütemével (OnCalendar=hourly) egyezik
_NAMED = {"minutely": 60, "hourly": 3600, "daily": 86400, "weekly": 7 * 86400}
_EVERY_MIN = re.compile(r"^\*:0?0/(\d+)(?::00)?$|^\*:\*/(\d+)$")


def workdir(entry: dict, home: Path) -> Path:
    return Path(str(entry.get("workdir", "")).replace("%h", str(home)))


def fleet_owned(entry: dict, home: Path) -> bool:
    doc = mm.load(workdir(entry, home)) or {}
    eng = (doc.get("components") or {}).get("engine")
    return isinstance(eng, dict) and eng.get("schedule_owner") == "fleet"


def calendar_period_s(timer_text: str) -> float | None:
    """Pure: az OnCalendar periódusa, ha egyszerű (hourly, daily, *:0/N)."""
    for ln in timer_text.splitlines():
        if not ln.startswith("OnCalendar="):
            continue
        v = ln.split("=", 1)[1].strip()
        if v in _NAMED:
            return float(_NAMED[v])
        m = _EVERY_MIN.match(v)
        if m:
            return float(int(m.group(1) or m.group(2)) * 60)
    return None


def fleet_tick(entry: dict, home: Path, now: float) -> dict | None:
    """None, ha nem a flotta ütemez. Különben {tick_age, period_s, armed_since}:
    `armed_since` a flotta tick-timerének írási ideje (a türelmi idő kezdete,
    mert a tick ettől és nem a claude-processztől függ)."""
    if not fleet_owned(entry, home):
        return None
    timer = home / ".config" / "systemd" / "user" / f"{tick_unit(entry['agent'])}.timer"
    try:
        text, armed = timer.read_text(), timer.stat().st_mtime
    except OSError:
        text, armed = "", None
    period = float(entry.get("tick_period_s") or calendar_period_s(text) or DEFAULT_PERIOD_S)
    f = state_path(str(workdir(entry, home)), "last-tick.json")
    try:
        age = now - f.stat().st_mtime
    except OSError:
        age = None
    return {"tick_age": age, "period_s": period, "armed_since": armed}
