"""Tick-kapu: a registry `tick_gate` mezője, a három preset és a TISZTA döntés.

Nincs I/O: a futtató (tick_gate_run) adja a megfigyelést és az időt, ez mondja meg, mi
legyen: kimarad-e az ellenőrzés (tétlen módban a köztes tüzelés), beküld-e, és mi a
következő intervallum. Tervdokumentum: fleet/docs/design/2026-11-08-tick-kapu.md.
"""
from __future__ import annotations

import re

from fleet.render import _SAFE_CMD

#: A bekötés kérdése új kiadó ágensnél — a szöveg EGY helyen él (docs és skill ezt idézi).
QUESTION = (
    "Milyen gyakran nézzen rá a kiadó ágens a sorra? Az üres ellenőrzés nagyon olcsó: nem fut AI, "
    "csak egy gyors lekérdezés — AI-kör csak akkor indul, ha van munka.\n"
    "1. Rendszeres (aktív fejlesztéshez) (ajánlott) — 30 percenként; ha 3 órája nem volt munka, óránként.\n"
    "2. Mérsékelt — óránként; ha 3 órája nem volt munka, 3 óránként.\n"
    "3. Reggel és este — napi két fix ellenőrzés (alapból 08:07 és 18:07, átállítható).")

PRESETS = {
    "rendszeres": {"active_s": 1800, "idle_s": 3600, "idle_after_s": 10800},
    "mersekelt": {"active_s": 3600, "idle_s": 10800, "idle_after_s": 10800},
    "reggel-este": {"at": ["08:07", "18:07"]},
}
DEFAULT_PRESET = "rendszeres"
ANSWERS = {"1": "rendszeres", "2": "mersekelt", "3": "reggel-este"}
DEFAULTS = {"tz": "Europe/Budapest", "offset_min": 4, "daily_at": [], "max_per_day": 48,
            "check": "builtin:release", "lease_ttl_min": 25}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_TZ = re.compile(r"^[A-Za-z_]+(/[A-Za-z_+-]+)*$")


def config(entry: dict) -> dict | None:
    """A kapu teljes beállítása (preset + explicit mezők), vagy None, ha nincs kapu."""
    raw = entry.get("tick_gate")
    if not isinstance(raw, dict):
        return None
    preset = raw.get("preset") or DEFAULT_PRESET
    out = {**DEFAULTS, **PRESETS.get(preset, {}), **raw, "preset": preset}
    out.setdefault("tick_cmd", entry.get("loop_cmd") or "")
    return out


def problems(cfg: dict) -> list[str]:
    """Miért NEM telepíthető ez a kapu (üres = rendben). A render ugyanígy tilt, nem escape-el."""
    out = []
    if cfg["preset"] not in PRESETS:
        out.append(f"tick_gate.preset ismeretlen: {cfg['preset']!r} (lehet: {', '.join(PRESETS)})")
    if not cfg.get("tick_cmd") or not _SAFE_CMD.match(cfg["tick_cmd"]):
        out.append(f"tick_gate.tick_cmd hiányzik vagy tiltott karaktert tartalmaz: {cfg.get('tick_cmd')!r}")
    for t in list(cfg.get("at") or []) + list(cfg.get("daily_at") or []):
        if not _HHMM.match(str(t)):
            out.append(f"tick_gate időpont nem ÓÓ:PP: {t!r}")
    if not _TZ.match(str(cfg.get("tz"))):
        out.append(f"tick_gate.tz nem zónanév: {cfg.get('tz')!r}")
    if not cfg.get("at"):
        a, i, after = (cfg.get(k) for k in ("active_s", "idle_s", "idle_after_s"))
        if not all(isinstance(v, int) and v > 0 for v in (a, i, after)):
            out.append("tick_gate: active_s, idle_s, idle_after_s pozitív egész kell")
        elif a < 900 or 3600 % a and a % 3600 or i % a:
            out.append("tick_gate: active_s ≥ 900, osszon egy órát (vagy órák egésze), idle_s pedig a többszöröse")
    if not 0 <= int(cfg.get("offset_min", 0)) < 15:
        out.append("tick_gate.offset_min 0–14")
    if not str(cfg.get("check", "")).startswith("builtin:") and not isinstance(cfg.get("check"), list):
        out.append("tick_gate.check: 'builtin:release' vagy argv-lista (shell nélkül)")
    return out


def calendars(cfg: dict) -> list[str]:
    """A timer OnCalendar-sorai: fix időpontok, vagy az alapütem az eltolással."""
    tz = cfg["tz"]
    if cfg.get("at"):
        return [f"OnCalendar=*-*-* {t}:00 {tz}" for t in cfg["at"]]
    a, off = cfg["active_s"], int(cfg.get("offset_min", 0))
    if a < 3600:
        mins = ",".join(f"{m:02d}" for m in range(off, 60, a // 60))
        return [f"OnCalendar=*-*-* *:{mins}:00 {tz}"]
    return [f"OnCalendar=*-*-* 00/{a // 3600}:{off:02d}:00 {tz}"]


def base_period_s(cfg: dict) -> int:
    """A timer két tüzelése közti leghosszabb idő (az egészség ehhez mér)."""
    if cfg.get("at"):
        mins = sorted(int(t[:2]) * 60 + int(t[3:]) for t in cfg["at"])
        gaps = [b - a for a, b in zip(mins, mins[1:])] + [mins[0] + 1440 - mins[-1]]
        return max(gaps) * 60
    return int(cfg["active_s"])


def interval_s(cfg: dict, last_activity_at: float | None, now: float) -> int:
    """Pure: 30↔60 váltás. Aktivitás az utolsó `idle_after_s`-ben → active_s, különben idle_s."""
    if cfg.get("at"):
        return base_period_s(cfg)
    if last_activity_at is not None and now - last_activity_at < cfg["idle_after_s"]:
        return int(cfg["active_s"])
    return int(cfg["idle_s"])


SLACK_S = 120   # a timer pontatlansága: a „még nem esedékes” határ ennyivel engedékenyebb


def due(state: dict, now: float) -> bool:
    """Pure: kell-e ellenőrizni ennél a tüzelésnél (tétlen módban a köztes tüzelés kimarad)."""
    nxt = state.get("next_due_at")
    if not isinstance(nxt, (int, float)) or nxt > now + 2 * 86400:   # romlott / jövőbe ugrott óra: esedékes
        return True
    return now >= float(nxt) - SLACK_S
