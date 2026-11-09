"""flotta-menedzser: az utolsó LEFUTOTT tick, kívülről olvashatóan (egy menedzser-ágens kérése, 11-08).

Csak a tick saját nyoma számít: `data/state/last-tick.json`, amit a motor tickje ír, ütemezett
triggernél (arming.py). A liveness-segéd által frissíthető jelek (heartbeat mtime, transzkript-
jelölő) itt SZÁNDÉKOSAN nincsenek: egy halott loop azokkal egészségesnek látszhat.

    executed(entry, home, now) -> {"owner", "period_s", "last_tick_at", "age_s"}
        owner: "fleet" (a flotta timere ütemez), "session" (az ágens saját loopja — a CronList-je
        másik sessionből nem látszik, ezért ez a kívülről mérhető helyettesítője), "none".
    stale(t) -> bool            van ütemezés, és a nyom régebbi, mint periódus × TICK_STALE_FACTOR, VAGY nincs nyom
    missing(t) -> bool          van ütemezés, de nincs nyom (mérhetetlen = piros, sosem „nem régi”)
    after(t, started_s) -> bool a tick a processz indulása UTÁN futott (postcheck: friss generáció)
    verdict(t, started_s, now) -> "ok" | "pending" | "red"
        a jelentés ítélete. Friss indulás (restart, upgrade) után az első tickig türelmi idő jár:
        indulás + periódus + GRACE_MARGIN_S; addig a hiányzó vagy az indulás előtti nyom „pending”
        (nem incidens), utána piros. Periódus nélküli loopnál DEFAULT_GRACE_PERIOD_S (90 perc).
"""
from __future__ import annotations
import time
from pathlib import Path

from fleet.liveness import TICK_STALE_FACTOR, state_path


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def executed(entry: dict, home: Path | None = None, now: float | None = None) -> dict:
    home = home or Path.home()
    now = time.time() if now is None else now
    from fleet import tick_watch
    try:
        fleet_tick = tick_watch.fleet_tick(entry, home, now)
    except Exception:  # noqa: BLE001 — mérhetetlen manifest: nem a flotta ütemez
        fleet_tick = None
    owner = "fleet" if fleet_tick else ("session" if scheduled(entry) else "none")
    explicit = (fleet_tick or {}).get("period_s") or entry.get("tick_period_s")
    period = float(explicit or 3600)
    f = state_path(str(entry.get("workdir", "")).replace("%h", str(home)), "last-tick.json")
    try:
        at = f.stat().st_mtime
    except OSError:
        at = None
    return {"owner": owner, "period_s": int(period), "last_tick_at": _iso(at) if at else None,
            "age_s": int(now - at) if at else None, "_at": at, "_explicit": bool(explicit)}


def scheduled(entry: dict) -> bool:
    """Van-e saját loopja (registry: `proactive`, `loop_cmd` vagy `tick_period_s`)."""
    return bool(entry.get("proactive") or entry.get("loop_cmd") or entry.get("tick_period_s"))


def missing(t: dict) -> bool:
    """Ütemezett ágens, és nincs tick-nyoma: MÉRHETETLEN — ez piros, nem „nem régi”. Egy halott loop
    (vagy egy nyomot sosem író tick) így nem látszhat zöldnek. Ütemezés nélküli ágensnél nem hiba."""
    return t["owner"] != "none" and t["age_s"] is None


def stale(t: dict) -> bool:
    """Piros: ütemezett ágens, és a nyom régi (periódus × TICK_STALE_FACTOR) vagy hiányzik."""
    return missing(t) or (t["owner"] != "none" and t["age_s"] > t["period_s"] * TICK_STALE_FACTOR)


GRACE_MARGIN_S = 15 * 60          # a periódus fölött ennyi tűrés az első tickig
DEFAULT_GRACE_PERIOD_S = 90 * 60  # periódus nélküli loop (csak `proactive` / `loop_cmd`) türelmi alapja


def grace_until(t: dict, started_s: float | None) -> float | None:
    if started_s is None:
        return None
    period = t["period_s"] if t.get("_explicit") else DEFAULT_GRACE_PERIOD_S
    return float(started_s) + period + GRACE_MARGIN_S


def verdict(t: dict, started_s: float | None, now: float | None = None) -> str:
    """ok / pending / red. Csak az indulás UTÁNI nyom bizonyítja ezt a generációt; ha még nincs ilyen, a
    türelmi időn belül pending, utána piros. Ismeretlen indulásnál nincs türelem: a régi szabály dönt."""
    now = time.time() if now is None else now
    if t["owner"] == "none":
        return "ok"
    fresh = t.get("_at") is not None and (started_s is None or t["_at"] > float(started_s))
    if fresh:
        return "red" if stale(t) else "ok"
    until = grace_until(t, started_s)
    if until is not None and now < until:
        return "pending"
    return "red"


def after(t: dict, started_s: float | None) -> bool:
    return t.get("_at") is not None and started_s is not None and t["_at"] > float(started_s)


def public(t: dict) -> dict:
    return {k: v for k, v in t.items() if not k.startswith("_")}
