"""Egészség-ítélet a jelekből: négy szó, és a végeredmény sosem jobb, mint a
legrosszabb jel.

  healthy    — a jel BIZONYÍTOTTAN jó
  pending    — még nem dőlt el (friss indulás, türelmi időn belül); nem OK
  unknown    — nem mérhető; nem OK, és a kimenet megmondja, miért
  unhealthy  — rossz (vagy a türelmi idő lejárt, és még mindig nem dőlt el)

Ami eddig hazudott: a doctor `GOOD` halmaza a `pending` ütemezést és az
`unknown` RC/auth-ot jónak vette. Itt nincs `else`: egy ismeretlen
állapot-szó `unknown`, nem `healthy` — az új szót előbb ide kell felvenni.
"""
from __future__ import annotations

from fleet.signals import UNKNOWN

HEALTHY, PENDING, UNKNOWN_H, UNHEALTHY = "healthy", "pending", "unknown", "unhealthy"
#: Opcionális jel nem mérhető állapota: kiírjuk, de az összesítést nem rontja.
NA = "n/a"
RANK = {NA: 0, HEALTHY: 0, PENDING: 1, UNKNOWN_H: 2, UNHEALTHY: 3}

#: Az RC opcionális (elfogadási mérés 2026-10-15: RC nélkül a doctor tartósan
#: 1-gyel lépett ki). A transzkript a visszakapcsolódást nem naplózza
#: (signals.rc_verdict), és a postcheck sem követeli meg — az `unknown` RC itt
#: `n/a`. A bizonyított leszakadás (`disconnected`) továbbra is `unhealthy`.
OPTIONAL = frozenset({"rc"})

# jel → {állapot-szó → egészség}. Ami nincs benne, az unknown.
VOCAB = {
    "process": {"up": HEALTHY, "down": UNHEALTHY, UNKNOWN: UNKNOWN_H},
    "schedule": {"armed": HEALTHY, "n/a": HEALTHY, "pending": PENDING,
                 "stale": UNHEALTHY, UNKNOWN: UNKNOWN_H},
    "channel": {"ok": HEALTHY, "n/a": HEALTHY, "stale": UNHEALTHY,
                "conflict": UNHEALTHY, UNKNOWN: UNKNOWN_H},
    "rc": {"connected": HEALTHY, "disconnected": UNHEALTHY, UNKNOWN: UNKNOWN_H},
    "auth": {"ok": HEALTHY, "expired": UNHEALTHY, UNKNOWN: UNKNOWN_H},
}


def classify(name: str, sig: dict) -> tuple[str, str]:
    """Pure: (egészség, indok) egy jelre."""
    state = sig.get("state")
    detail = sig.get("detail") or ""
    h = VOCAB.get(name, {}).get(state)
    if h is None:
        return UNKNOWN_H, f"ismeretlen állapot-szó '{state}' — {detail}".rstrip(" —")
    if h == UNKNOWN_H:
        return h, detail or "nem mérhető, ok nélkül"
    return h, detail or state


def worst(values) -> str:
    vals = [HEALTHY if v == NA else v for v in values]
    return max(vals, key=RANK.__getitem__) if vals else HEALTHY


def judge(signals: dict) -> dict:
    """Pure: {health, per_signal: {név: (egészség, indok)}, pending, unknown,
    unhealthy}. A listák emberi sorok: '<jel>: <indok>'."""
    per = {k: classify(k, v) for k, v in signals.items()}
    per = {k: ((NA, f"nem kötelező jel — {why}") if k in OPTIONAL and h == UNKNOWN_H else (h, why))
           for k, (h, why) in per.items()}
    out = {"health": worst(h for h, _ in per.values()), "per_signal": per,
           PENDING: [], UNKNOWN_H: [], UNHEALTHY: []}
    for k, (h, why) in per.items():
        if h not in (HEALTHY, NA):
            out[h].append(f"{k}: {why}")
    return out


MARK = {HEALTHY: "✅", NA: "➖", PENDING: "⏳", UNKNOWN_H: "❔", UNHEALTHY: "❌"}
