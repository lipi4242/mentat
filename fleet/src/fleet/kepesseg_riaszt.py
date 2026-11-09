"""11-07: a piros alapfunkció eljut valakihez — a beteg ágens csatornájától függetlenül.

    sweep(agents=None, home=None, now=None) -> [naplósor]   a reconcile (5 perces kör) hívja;
        ágensenként legfeljebb PERIOD_S-enként mér (egy `mentat-todo me` 15 percenként),
        az eredményt a központi flotta-ellenőrzésnek jelenti (flotta_report.py, 10 percenként)
    alert_red(agent, red) -> 'kozpont' | 'stderr' | 'dup'   a postcheck képesség-hibája
    record(agent, red, ...)                                 egy mérés rögzítése (a postcheck is ezt hívja)

A mérés a doctor-é (doctor.essentials_for): titok-kapu-döntés, token-előfeltétel, néma küldés a
naplóban, és a képesség-próba (kepesseg.py). Az út: a box jelent a központnak, ott a
felelős ágens feladatot kap, és ha nem oldja meg, e-mail megy a tulajdonosnak. Külön riasztó bot
nincs. Ha a jelentés nincs beállítva vagy nem ment ki, a piros a fájl-tartalékba kerül
(alerts.alert(independent_only=True): az ágens saját hídján SOHA), és a doctor box-sora piros.
A tartalék kulcsa a hibalista lenyomata: ugyanaz a hiba egyszer kerül oda, egy új hiba újra.
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path

from fleet import CONFIG_DIR, alerts, flotta_report

PERIOD_S = 900
STATE = CONFIG_DIR / "state" / "kepesseg.json"


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def record(agent: str, red: list[str], now: float | None = None, unknown=(), ok=()) -> None:
    st = _load()
    st[agent] = {"at": time.time() if now is None else now, "red": list(red), "unknown": list(unknown), "ok": list(ok)}
    _save(st)
    if not red:
        alerts.clear(f"kepesseg:{agent}:")


def fallback(agent: str, red: list[str]) -> str:
    """A fájl-tartalék: amikor a központ nem kapta meg (nincs beállítva, vagy a jelentés bukott)."""
    digest = hashlib.sha256("\n".join(sorted(red)).encode()).hexdigest()[:12]
    text = (f"🔴 {agent}: alapfunkció hiba — az ágens fut, de ezt nem tudja: " + "; ".join(red)[:900]
            + f"\n(`fleet doctor {agent}` a boxon)")
    return alerts.alert(f"kepesseg:{agent}:{digest}", text, independent_only=True)


def alert_red(agent: str, red: list[str]) -> str:
    record(agent, red)
    if flotta_report.config() is not None:
        flotta_report.force()   # a következő reconcile-kör azonnal jelenti, nem vár a 10 percre
        return "kozpont"
    return fallback(agent, red)


def sweep(agents: list[dict] | None = None, home: Path | None = None, now: float | None = None,
          measure=None, host: str | None = None, opener=None) -> list[str]:
    from fleet import essentials
    from fleet.doctor import essentials_for
    now = time.time() if now is None else now
    measure = measure or essentials_for
    agents = essentials.local_agents() if agents is None else agents
    st, lines, names, measured = _load(), [], [], set()
    for e in agents:
        a = e["agent"]
        if e.get("status") == "dormant" or e.get("supervision") == "none":
            continue
        names.append(a)
        if a in st and now - float(st[a].get("at", 0)) < PERIOD_S:
            continue
        m = measure(e)
        measured.add(a)
        record(a, m["red"], now, m.get("unknown", []), m.get("facts", []))
    st = _load()
    if host is None:
        from fleet.registry import local_host
        host = local_host()
    kw = {"opener": opener} if opener else {}
    res = flotta_report.maybe_report(st, names, host, now, home, **kw)
    if res in ("sent", "failed"):
        lines.append(f"flotta-jelentés: {'elküldve' if res == 'sent' else 'HIBA — a piros a fájl-tartalékba kerül'} "
                     f"({len(names)} ágens)")
    delivered = res in ("sent", "fresh")
    for a in names:
        red = st.get(a, {}).get("red", [])
        if red:
            how = "kozpont" if delivered else fallback(a, red)
            if a in measured or how not in ("kozpont", "dup"):
                lines.append(f"{a}: képesség PIROS [{how}] — {'; '.join(red)[:300]}")
    return lines
