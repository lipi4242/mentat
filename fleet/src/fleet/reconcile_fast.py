"""A reconcile gyors útja (`fleet reconcile --fast`, ~30 mp-es timer).

06-flotta mérés: a leölt ágens 4,5 percig nem jött vissza, mert egyetlen
dolog indítja újra — az 5 perces teljes kör. A teljes kör mellékhatásai
(híd-restart költségvetés, riasztás, re-arm) viszont NEM gyorsíthatók: egy
409 elmúlása percekbe telik, az 1 perces újrapróbálás a költségvetést a
hatás előtt égetné el. Ezért a gyors út CSAK egyet tehet: elindítja a
leállt processzt, és azt is csak akkor, ha két megfigyelésben, legalább
CONFIRM_S különbséggel is hiányzott (a claude önfrissítése vagy egy `--resume`
→ friss indítás átmenetileg nem téves riasztás). A szabályok (zár, karantén,
dormant, költségvetés) ugyanazok: a `decide` dönt, ez csak szűri.
"""
from __future__ import annotations
import time
from pathlib import Path

from fleet import CONFIG_DIR

MARK_DIR = CONFIG_DIR / "state" / "down"
CONFIRM_S = 20.0
#: Amit a gyors út végrehajthat: a processz hiánya miatti indítás.
FAST_ACTIONS = ("start", "restart")


def _mark(agent: str) -> Path:
    return MARK_DIR / agent


def filter_acts(agent: str, acts: list[tuple[str, str]], now: float | None = None) -> list[tuple[str, str]]:
    """Pure-ish: a `decide` döntéseiből a gyors útra illő rész. A hiány első
    látását csak jelöli; a megerősített hiányt engedi át."""
    now = time.time() if now is None else now
    down = [a for a in acts if a[0] in FAST_ACTIONS]
    p = _mark(agent)
    if not down:
        if not any(a[0].startswith("skip:") for a in acts):
            p.unlink(missing_ok=True)       # él (vagy szándékosan áll): nincs mit megerősíteni
        return []
    try:
        since = float(p.read_text())
    except (OSError, ValueError):
        MARK_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(str(now))
        return []
    if now - since < CONFIRM_S:
        return []
    p.unlink(missing_ok=True)
    return down
