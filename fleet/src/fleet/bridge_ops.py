"""Hid-telepites tartalom-ellenorzese (sha256 drift) es visszaallitasa (rollback).

A `bridge.py` ezt importalja; kulon fajl a 150 soros keret miatt.
"""
from __future__ import annotations
import datetime
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from fleet import BRIDGE_DIR

#: Amit egy agens kap: a bejovo hid, a kimeno CLI es a kezbesitesi naplo
#: riportja (bridge/docs/delivery-log.md).
ENTRY_POINTS = ("bridge.mjs", "send.mjs", "delivery.mjs")

#: A bélyeg-sor, horgonyzottan: a 2. sor egésze, semmi más.
STAMP_RE = re.compile(rb"^// (fleet-bridge|sub-etha) \S+ installed \d{4}-\d{2}-\d{2}$")
_BAK_RE = re.compile(r"^sub-etha\.bak-\d{8}-\d{6}$")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def _names(root: Path) -> list[str]:
    root = Path(root)
    names = list(ENTRY_POINTS) + ["VERSION"]
    if (root / "lib").is_dir():
        names += [f"lib/{f.name}" for f in sorted((root / "lib").glob("*.mjs"))]
    return names


def _digest(path: Path) -> str | None:
    path = Path(path)
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except OSError:
        return None
    if path.name == "bridge.mjs" and len(lines) >= 2 \
            and STAMP_RE.match(lines[1].rstrip(b"\r\n")):
        del lines[1]
    return hashlib.sha256(b"".join(lines)).hexdigest()


def drift_files(dest: Path, root: Path = BRIDGE_DIR) -> list[str]:
    """Relativ utak, ahol a telepitett fajl sha256-ja elter, hianyzik vagy tobblet."""
    names = sorted(set(_names(root)) | set(_names(dest)))
    return [n for n in names if _digest(Path(root) / n) != _digest(Path(dest) / n)]


def _unit(entry: dict) -> str:
    return (entry.get("bridge") or {}).get("unit") or f"{entry['agent']}-telegram-bridge.service"


def rollback_bridge(entry: dict, *, dest_root: Path | None = None, run=_run) -> dict:
    """Legujabb `sub-etha.bak-*` konyvtar vissza. stop -> csere -> start; ha a
    csere dob, az eredeti visszakerul, es a unit akkor is startot kap."""
    agent = entry["agent"]
    base = (Path(dest_root) if dest_root else Path.home() / ".config") / agent
    dest = base / "sub-etha"
    baks = sorted(p for p in base.glob("sub-etha.bak-*")
                  if _BAK_RE.match(p.name) and p.is_dir() and not p.is_symlink())
    if not baks:
        raise RuntimeError(f"{agent}: nincs sub-etha.bak-* konyvtar — nincs mire visszaallni")
    bak, unit = baks[-1], _unit(entry)
    stem = f"sub-etha.rolledback-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    rolled, n = base / stem, 1
    while rolled.exists() or rolled.is_symlink():  # a move sose agyazodjon
        n += 1
        rolled = base / f"{stem}.{n}"
    stop = run(["systemctl", "--user", "stop", unit])
    if stop.returncode != 0:
        state = (getattr(run(["systemctl", "--user", "is-active", unit]), "stdout", "") or "").strip()
        if state not in ("inactive", "failed"):  # csak pozitiv bizonyitekra cserelunk
            raise RuntimeError(f"{agent}: a {unit} leallasa nem bizonyitott (stop rc={stop.returncode}, "
                               f"is-active={state or '?'}) — semmi nem mozdult")
    moved_dest = False
    try:
        if dest.exists() or dest.is_symlink():
            shutil.move(str(dest), str(rolled))
            moved_dest = True
        shutil.move(str(bak), str(dest))
    except BaseException:
        if moved_dest and not dest.exists() and rolled.exists():
            shutil.move(str(rolled), str(dest))
        raise
    finally:
        start = run(["systemctl", "--user", "start", unit])
    return {"agent": agent, "restored": bak.name, "unit": unit,
            "stop_rc": stop.returncode, "start_rc": start.returncode}
