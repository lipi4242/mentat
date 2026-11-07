"""Per-agent maintenance lock with expiry.

A lock file names one agent under hand-maintenance. The reconcile and the
liveness guard skip locked agents. TTL means a forgotten lock EXPIRES —
supervision silently disabled forever is worse than a raced restart.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

DEFAULT_TTL_MIN = 120

#: A lock file is named after the agent — the name must not be able to escape
#: the lock root (`../x`) or smuggle path separators.
_AGENT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _root() -> Path:
    return Path(os.environ.get("FLEET_MAINTENANCE_DIR")
                or Path.home() / ".config" / "fleet" / "maintenance")


def _check_name(agent: str) -> None:
    if not _AGENT_NAME.match(agent):
        raise ValueError(f"invalid agent name {agent!r} — must match [A-Za-z0-9._-]+")


def lock(agent: str, ttl_min: int = DEFAULT_TTL_MIN) -> Path:
    _check_name(agent)
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    p = root / agent
    p.write_text(str(time.time() + ttl_min * 60))
    return p


def unlock(agent: str) -> None:
    _check_name(agent)
    (_root() / agent).unlink(missing_ok=True)


def is_locked(agent: str) -> bool:
    """False on ANY read problem — a bad name, a permission error, a garbage
    file. Supervision loops call this; they must never abort on the lock."""
    if not _AGENT_NAME.match(agent):
        return False
    p = _root() / agent
    try:
        expires = float(p.read_text().strip())
    except (OSError, ValueError):
        return False
    if time.time() >= expires:
        try:
            p.unlink(missing_ok=True)   # self-clean: expired lock must not linger
        except OSError:
            pass
        return False
    return True
