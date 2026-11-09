"""flotta-menedzser: a javító végrehajtó helyi, kizárólagos zára a célra (az 1. lépés, a Worker-ellenőrzés ELŐTT).

    held(agent | None) -> context manager; foglalt zárnál Busy

Két fcntl-zár a `~/.config/fleet/state/repair/` alatt, nem blokkolva:
  * `box.lock`      — ágens-lépésnél MEGOSZTOTT, box-szintű lépésnél (agent=None) KIZÁRÓLAGOS:
                      a box-szintű lépés így minden ágens-zárral ütközik, és fordítva;
  * `agent-<a>.lock` — ágens-lépésnél kizárólagos: egy célon egyszerre egy lépés.
A zár a processz halálával felszabadul (a Workerben a lépés határideje a „lejárat”).
"""
from __future__ import annotations
import fcntl
import os
import re
from contextlib import contextmanager
from pathlib import Path

from fleet import CONFIG_DIR

ROOT = CONFIG_DIR / "state" / "repair"
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class Busy(RuntimeError):
    pass


def _open(p: Path, mode: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, mode | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise Busy(f"foglalt: {p.name} — egy másik javító lépés fut ezen a célon")
    return fd


@contextmanager
def held(agent: str | None, root: Path | None = None):
    root = root or ROOT
    if agent is not None and not _NAME.match(agent):
        raise ValueError(f"érvénytelen ágensnév: {agent!r}")
    fds = [_open(root / "box.lock", fcntl.LOCK_EX if agent is None else fcntl.LOCK_SH)]
    try:
        if agent is not None:
            fds.append(_open(root / f"agent-{agent}.lock", fcntl.LOCK_EX))
        yield
    finally:
        for fd in reversed(fds):
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
