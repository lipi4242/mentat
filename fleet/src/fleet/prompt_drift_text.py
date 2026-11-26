"""A drift-restart szövegei: ok, első üzenet, fájllista — egy szűrővel.

A fájlnevek az ágens repójából jönnek, tehát a pane-be (send-keys), a naplóba
és a Telegram-riasztásba csak szűrve mehetnek: ASCII betű/szám és `._-/~`,
minden más kiesik. Ugyanaz a szűrő mindhárom helyen.
"""
from __future__ import annotations
from pathlib import Path

MAX_SHOWN = 8
_ALLOWED = "._-/~"


def safe_name(s: str) -> str:
    return "".join(c for c in s if (c.isascii() and c.isalnum()) or c in _ALLOWED)[:120]


def _rel(path: str, entry: dict, home: Path) -> str:
    wd = Path(entry.get("workdir") or "/nonexistent")
    for base, pre in ((wd, ""), (wd.resolve(), ""), (home, "~/"), (home.resolve(), "~/")):
        try:
            return pre + str(Path(path).relative_to(base))
        except ValueError:
            continue
    return path


def shown(entry: dict, m: dict, home: Path | None = None) -> list[str]:
    """A változott fájlok kijelzésre: relatív út, szűrve."""
    home = home or Path.home()
    return [safe_name(_rel(p, entry, home)) for p in m.get("prompt_drift") or []]


def _listing(files: list[str]) -> str:
    more = f" (+{len(files) - MAX_SHOWN})" if len(files) > MAX_SHOWN else ""
    return ", ".join(files[:MAX_SHOWN]) + more


def reason(entry: dict, m: dict) -> str:
    files, parts = shown(entry, m), []
    if m.get("restart_requested"):
        parts.append("az ágens kérte")
    if files:
        parts.append(f"változott prompt: {_listing(files)}")
    block = m.get("prompt_drift_block")
    if block and block[0]:
        parts.append(block[1])
    return "; ".join(parts)


def notice_text(entry: dict, m: dict) -> str:
    """Az újraindult ágens első üzenete: egy sor, csak szűrt karakterek."""
    files = shown(entry, m)
    head = "[fleet] Újraindultál (--resume, a beszélgetés megmaradt)"
    if files:
        return f"{head}, mert a betöltött promptod megváltozott: {_listing(files)}. A friss változat már betöltve."
    return f"{head}, mert kérted (fleet request-restart). A friss prompt betöltve."
