"""ticklock — keeps two ticks apart with a Python lock, where flock(1) is not available.

    with ticklock.held() as got:
        if not got: ...   # another tick holds it: skip, do not wait

`tick --lock` uses it (the macOS LaunchAgent, the macOS cron line, `tick --once`).
The Linux cron line keeps `flock -n` on data/state/tick.lock, so this lock lives in
its own file: the two never block each other by accident.
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Iterator

from . import config


def path() -> Path:
    return config.repo_root() / "data" / "state" / "tick.run.lock"


@contextlib.contextmanager
def held() -> Iterator[bool]:
    """Non-blocking: yields True with the lock held, False when another process has it."""
    import fcntl   # here, not at the top: importing the engine must not need it

    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
