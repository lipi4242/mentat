"""PROXY: a futó claude bináris még tartalmazza-e a híd pane-őrének mintáit (F-17, CISO 10-24).

A híd (bridge/lib/pane-guard.mjs) nem ír a pane-be és nem nyom Entert, ha a pane alján egy
„Do you want to …?” kérdés és egy „1. Yes” opciósor áll (2.1.310-en élőben mérve, 10-24). Egy
Claude Code-frissítés csendben átírhatja ezt a szöveget, és akkor a pane-őr semmit nem fog.

Az „1. Yes” a binárisban NINCS szó szerint (a sorszámot a választó komponens rajzolja), ezért
ez csak PROXY: a kérdés eleje (`Do you want to `) és az opció címkéje (`label:"Yes"`) megvan-e.
Ha megvan, az nem bizonyítja, hogy a pane-őr illik; ha hiányzik, szinte biztos, hogy nem.
"""
from __future__ import annotations
import mmap
import os
from pathlib import Path

#: (bájtminta a binárisban, mit jelent a pane-guard.mjs-ben)
MINTAK = ((b"Do you want to ", "QUESTION: a kérdés eleje"),
          (b'label:"Yes"', "YES_OPTION: az „1. Yes” opció címkéje"))
_CACHE: dict = {}


def missing(path: Path) -> list[str] | None:
    """A hiányzó minták leírása; None, ha a bináris nem olvasható (azt a verzió-jel már mutatja)."""
    try:
        real = os.path.realpath(path)
        st = os.stat(real)
        key = (real, st.st_size, st.st_mtime_ns)
        if key not in _CACHE:
            with open(real, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                _CACHE[key] = [why for pat, why in MINTAK if m.find(pat) == -1]
        return _CACHE[key]
    except (OSError, ValueError):
        return None


def problem(path: Path) -> str | None:
    gone = missing(path)
    if not gone:
        return None
    return ("PROXY: a claude binárisból (%s) hiányzik a híd pane-őrének mintája (%s) — egy "
            "CC-frissítés után az engedélykérő ablakot a híd lehet, hogy nem ismeri fel (F-17); "
            "élő capture-pane próba és a bridge/lib/pane-guard.mjs igazítása kell"
            % (os.path.realpath(path), "; ".join(gone)))
