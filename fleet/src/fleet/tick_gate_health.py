"""A tick-kapu nyomának ítélete: az élő-tétlen ágens zöld, az elakadt kapu piros.

    verdict(entry, home, now) -> {"state": "ok"|"pending"|"red"|"n/a", "detail", ...}

- `ok`      a timer él (`fired_at` ≤ 2 × alapütem) ÉS az ellenőrzés fut (`checked_at` ≤ 2 × az
            aktuális intervallum) ÉS nincs ERRORS_RED egymást követő hiba — akkor is, ha napok óta
            nem volt munka (tétlen ≠ halott);
- `red`     elakadt timer, bukó előellenőrző, vagy tartós hiba;
- `pending` még nem tüzelt, de a timer telepítése óta nem telt el 2 × alapütem;
- `n/a`     nincs kapu a registryben.

`overlay(entry, home, now, t)` a #74 `tick_signal.executed` eredményére teszi rá ugyanezt
(owner: "gate", a nyom a kapu ellenőrzése): a #74 merge-e után egy sor a tick_signal-ban.
"""
from __future__ import annotations

import time
from pathlib import Path

from fleet import tick_gate as tg
from fleet.tick_gate_decide import ERRORS_RED
from fleet.tick_gate_run import load, trace_path

FACTOR = 2
PENDING_RED_S = 3 * 3600   # ennyi ideje beküldetlen munka (foglalt / korlát) = piros (Codex: éhezés)


def gate_unit(agent: str) -> str:
    return f"fleet-gate-{agent}"


def _armed_at(entry: dict, home: Path) -> float | None:
    t = home / ".config" / "systemd" / "user" / f"{gate_unit(entry['agent'])}.timer"
    try:
        return t.stat().st_mtime
    except OSError:
        return None


def verdict(entry: dict, home: Path | None = None, now: float | None = None) -> dict:
    home = home or Path.home()
    now = time.time() if now is None else now
    cfg = tg.config(entry)
    if cfg is None:
        return {"state": "n/a", "detail": "nincs tick-kapu"}
    base = tg.base_period_s(cfg)
    g = load(trace_path(entry, home))
    num = lambda v: float(v) if isinstance(v, (int, float)) else None   # romlott nyom = nincs nyom
    fired, checked = num(g.get("fired_at")), num(g.get("checked_at"))
    if not isinstance(g.get("interval_s"), int):
        g["interval_s"] = None
    if num(g.get("pending_since")) is None:
        g.pop("pending_since", None)
    interval = int(g.get("interval_s") or tg.interval_s(cfg, g.get("last_activity_at"), now))
    out = {"base_s": base, "interval_s": interval, "fired_at": fired, "checked_at": checked,
           "decision": g.get("decision"), "injected_at": g.get("injected_at")}
    if fired is None:
        armed = _armed_at(entry, home)
        if armed is not None and now - armed <= FACTOR * base:
            return {**out, "state": "pending", "detail": "a kapu még nem tüzelt (friss telepítés)"}
        return {**out, "state": "red", "detail": "tick-kapu: nincs nyom — a timer nem fut, vagy nincs telepítve"}
    if now - fired > FACTOR * base:
        return {**out, "state": "red",
                "detail": f"tick-kapu: a timer {int(now - fired) // 60} perce nem tüzelt (alapütem {base // 60} perc)"}
    if checked is None or now - checked > FACTOR * interval:
        age = "soha" if checked is None else f"{int(now - checked) // 60} perce"
        return {**out, "state": "red",
                "detail": f"tick-kapu: a timer tüzel, de az előellenőrzés nem fut le (utolsó: {age})"}
    if int(g.get("errors") or 0) >= ERRORS_RED:
        return {**out, "state": "red", "detail": f"tick-kapu: {g['errors']} hibás ellenőrzés egymás után ({g.get('error')})"}
    if g.get("pending_since") and now - float(g["pending_since"]) > PENDING_RED_S:
        return {**out, "state": "red", "detail": f"tick-kapu: a munka {int(now - g['pending_since']) // 60} perce vár "
                                                  f"beküldésre ({'; '.join((g.get('reasons') or [])[-2:])})"}
    idle = g.get("decision") in ("idle", "error")
    return {**out, "state": "ok",
            "detail": f"tick-kapu: él{', tétlen' if idle else ''} — utolsó ellenőrzés {int(now - checked) // 60} perce, "
                      f"intervallum {interval // 60} perc"}


def overlay(entry: dict, home: Path | None, now: float | None, t: dict) -> dict:
    """A #74 tick_signal dict-jére: kapus ágensnél a kapu nyoma a tick-jel (additív)."""
    v = verdict(entry, home, now)
    if v["state"] == "n/a":
        return t
    now = time.time() if now is None else now
    at = v["checked_at"] if v["state"] == "ok" else None
    period = int(v["interval_s"])
    return {**t, "owner": "gate", "period_s": period, "_explicit": True, "_at": at,
            "age_s": int(now - at) if at else None, "gate": v["state"], "gate_detail": v["detail"]}


def kepesseg_line(entry: dict, home: Path) -> tuple[str, str] | None:
    """(red|ok, sor) a központi flotta-checknek; None, ha nincs kapu. A piros sor `tick`-kulcsú."""
    v = verdict(entry, home)
    if v["state"] in ("n/a", "pending"):
        return None
    return ("red" if v["state"] == "red" else "ok", v["detail"])
