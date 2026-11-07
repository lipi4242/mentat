"""A futó híd a telepített fájlok kódját futtatja-e (#35).

A `fleet bridge install` a fájlokat cseréli, újraindítást nem csinál. Ha a híd
processze a csere ELŐTT indult, a régi kódot futtatja, miközben a VERSION-bélyeg
már az újat mutatja. 11-07 éjjel négy hídnál így volt. A mérés: a híd-unit
MainPID-jének indulási ideje a bridge.mjs mtime-jához képest.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

SLACK_S = 2   # a /proc indulási ideje egész másodperc


def main_pid(unit: str, run=subprocess.run) -> int | None:
    try:
        r = run(["systemctl", "--user", "show", "-p", "MainPID", "--value", unit],
                capture_output=True, text=True)
        pid = int((r.stdout or "0").strip() or 0)
    except (OSError, ValueError):
        return None
    return pid or None


def verdict(proc_started_s: float | None, bridge_mtime: float | None) -> str | None:
    """Pure: probléma-szöveg, vagy None (friss, vagy nem mérhető)."""
    if proc_started_s is None or bridge_mtime is None:
        return None
    if proc_started_s + SLACK_S < bridge_mtime:
        return ("a futó híd a fájljainál régebbi kódot futtat (a processz a csere előtt indult) — "
                "`systemctl --user restart <híd-unit>`")
    return None


def problem(unit: str, dest: Path, procs: list[dict], run=subprocess.run) -> str | None:
    pid = main_pid(unit, run)
    if pid is None:
        return None
    started = next((p.get("started_s") for p in procs if p["pid"] == pid), None)
    try:
        mtime = (Path(dest) / "bridge.mjs").stat().st_mtime
    except OSError:
        return None
    v = verdict(started, mtime)
    return v.replace("<híd-unit>", unit) if v else None
