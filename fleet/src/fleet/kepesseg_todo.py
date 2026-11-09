"""11-08: a todo-ébresztés egészsége a képesség-próbában — a híd health-fájljából.

    check(entry, home, out, now=None)   a kepesseg.check hívja; a sorai a kepesseg-eredménybe kerülnek,
                                        onnan a doctorba és a központi flotta-jelentésbe (flotta_report)

A híd (bridge/lib/todo-wire.mjs) ≤60 s-onként lekéri az ágens todo-változásait, és a relevánsakat egy
sorban a pane-be írja. Ennek az egészsége három szám a `~/.config/<ágens>/telegram-state/health.json`-ban:

  todo_last_poll_ok           az utolsó sikeres poll (ms)   → POLL_STALE_S-nál régebbi = piros
  todo_last_wake_latency_ms   az utolsó ébresztés késése (az esemény ideje → a sor kiment)
  todo_unhandled              a határidőn túl feldolgozatlan ébresztések (24 órán belül) → >0 = piros

Csak hidas ágensnél, és csak ha a boxon van todo-beállítás (~/.config/todo/env). A piros sor a
`todo-ébresztés` kulcsot kapja (flotta_report.check_key), így a #53 rendes útján incidens lesz belőle.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from fleet import essentials_env as E

POLL_STALE_S = 600   # 10 perc sikeres poll nélkül: az ébresztés nem működik (a poll ≤60 s-onként fut)
PREFIX = "todo-ébresztés"


def _health(home: Path, agent: str) -> dict | None:
    try:
        d = json.loads((home / ".config" / agent / "telegram-state" / "health.json").read_text())
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def check(entry: dict, home: Path, out: dict, now: float | None = None) -> None:
    if not E.bridged(entry) or not (home / ".config" / "todo" / "env").is_file():
        return
    a, now = entry["agent"], time.time() if now is None else now
    h = _health(home, a)
    if h is None:
        out["unknown"].append(f"{PREFIX}: nincs olvasható híd-életjel (health.json) — a csatorna-jel mutatja, fut-e a híd")
        return
    state = h.get("todo_wake")
    if state is None:
        out["unknown"].append(f"{PREFIX}: a telepített híd még nem ismeri (régi híd) — `fleet bridge install {a}`")
        return
    if str(state).startswith("off: "):
        out["red"].append(f"{PREFIX} KI: {str(state)[5:][:200]} — a boxon van todo, a híd mégsem pollozza")
        return
    if state != "on":
        out["unknown"].append(f"{PREFIX}: a híd nem pollozza a todót ({str(state)[:80]})")
        return
    ok = float(h.get("todo_last_poll_ok") or 0) / 1000
    if now - ok > POLL_STALE_S:
        last = time.strftime("%H:%M", time.localtime(ok)) if ok else "soha"
        err = str(h.get("todo_last_error") or "")[:160]
        out["red"].append(f"{PREFIX}: {int((now - ok) // 60) if ok else '∞'} perce nincs sikeres todo-poll "
                          f"(utolsó: {last}{', hiba: ' + err if err else ''})")
        return
    n = int(h.get("todo_unhandled") or 0)
    if n > 0:
        out["red"].append(f"{PREFIX}: {n} ébresztés feldolgozatlan (határidőn túl nincs saját írás a tételen) — "
                          f"`node ~/.config/{a}/sub-etha/delivery.mjs`")
    lat = h.get("todo_last_wake_latency_ms")
    out["ok"].append(f"{PREFIX} (poll {int(now - ok)} s ezelőtt"
                     + (f", utolsó késés {int(lat) // 1000} s" if isinstance(lat, (int, float)) else "") + ")")
