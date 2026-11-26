"""A kért leállás jelölője: a `fleet stop` írja, a reconcile egyszer felhasználja.

2. kör, 06-flotta: a crash-loop költségvetés (3 restart/óra) minden
visszaindítást számolt, a `fleet stop` → `fleet wait-up` próbákat is. Az ágens
saját próbája + a tesztelő stop-ja + egy kill -9 után a negyedik, VALÓDI
leölésre már nem maradt keret, és az ágens egy órára kint maradt.

A kért leállás nem összeomlás: az ezt követő EGY visszaindítás nem fogy a
költségvetésből (a postcheck és a karantén ugyanúgy él). A jelölő egyszer
használható és lejár, így egy elfelejtett jelölő legfeljebb egy későbbi
indítást menthet fel, és csak VALID_S-en belül.
"""
from __future__ import annotations
import time
from pathlib import Path

from fleet import maintenance

#: ennyi ideig érvényes a jelölő a leállítás (ill. a zár lejárta) után
VALID_S = 900.0


def _path(agent: str) -> Path:
    return maintenance._root() / ".requested" / agent


def mark(agent: str, *, hold_min: int | None = None, now: float | None = None) -> None:
    now = time.time() if now is None else now
    p = _path(agent)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(now + (hold_min or 0) * 60 + VALID_S))


def clear(agent: str) -> None:
    _path(agent).unlink(missing_ok=True)


def pending(agent: str, now: float | None = None) -> bool:
    """Van-e érvényes kért leállás. Olvasási hiba → nincs (a költségvetés él)."""
    now = time.time() if now is None else now
    try:
        return now < float(_path(agent).read_text().strip())
    except (OSError, ValueError):
        return False


def take(agent: str, now: float | None = None) -> bool:
    """Egyszer felhasználja: True, ha érvényes volt. A jelölő mindenképp törlődik."""
    ok = pending(agent, now)
    try:
        clear(agent)
    except OSError:
        pass
    return ok


# ── kért újraindítás (`fleet request-restart`) ─────────────────────────────
# Az ágens nem hív saját systemctl-t: jelölőt tesz le, és a reconcile-timer
# indítja újra `--resume`-mal, amikor a kérő kör véget ért (prompt_drift).

#: ennyi ideig érvényes egy kért újraindítás, ha az ágens addig nem lesz tétlen
RESTART_VALID_S = 6 * 3600.0


def _restart_path(agent: str) -> Path:
    return maintenance._root() / ".requested" / f"{agent}.restart"


def mark_restart(agent: str, *, now: float | None = None) -> Path:
    now = time.time() if now is None else now
    p = _restart_path(agent)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(now + RESTART_VALID_S))
    return p


def restart_pending(agent: str, now: float | None = None) -> bool:
    """Érvényes-e a kérés. A beírt lejárat legfeljebb a fájl írása + RESTART_VALID_S:
    egy kézzel távoli jövőre írt jelölő sem él tovább ennél."""
    now = time.time() if now is None else now
    p = _restart_path(agent)
    try:
        until = min(float(p.read_text().strip()), p.stat().st_mtime + RESTART_VALID_S)
    except (OSError, ValueError):
        return False
    return now < until


def clear_restart(agent: str) -> None:
    try:
        _restart_path(agent).unlink(missing_ok=True)
    except OSError:
        pass
