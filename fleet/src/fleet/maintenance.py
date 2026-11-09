"""Per-agent maintenance lock with expiry.

A lock file names one agent under hand-maintenance. The reconcile and the
liveness guard skip locked agents. TTL means a forgotten lock EXPIRES —
supervision silently disabled forever is worse than a raced restart.

flotta-menedzser: `lock(agent, ttl, own=True)` — a javító végrehajtó zárja. Más processz (a reconcile timere,
a tick ExecCondition-je) zárt ágenst lát, de EBBEN a processzben `is_locked` hamis rá, hogy a
végrehajtó saját `doctor --fix`-e (reconcile._may_act) ne álljon meg a saját zárján.
`unlock` a saját jelölést is törli.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

DEFAULT_TTL_MIN = 120

#: Az ebben a processzben, `own=True`-val vett zárak: ágens → a zárfájl tartalma, amit MI írtunk.
#: A kerülőút csak addig él, amíg a fájlban még pontosan ez áll (lejárat vagy más gazda után nem).
_OWNED: dict[str, str] = {}

#: A lock file is named after the agent — the name must not be able to escape
#: the lock root (`../x`) or smuggle path separators.
_AGENT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _root() -> Path:
    return Path(os.environ.get("FLEET_MAINTENANCE_DIR")
                or Path.home() / ".config" / "fleet" / "maintenance")


def _check_name(agent: str) -> None:
    if not _AGENT_NAME.match(agent):
        raise ValueError(f"invalid agent name {agent!r} — must match [A-Za-z0-9._-]+")


def lock(agent: str, ttl_min: int = DEFAULT_TTL_MIN, own: bool = False) -> Path:
    """A zár jele (a fájl tartalma) `content(agent)`-tel olvasható vissza."""
    _check_name(agent)
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    p = root / agent
    text = str(time.time() + ttl_min * 60)   # a float-szöveg egyedi: ez a mi zárunk jele
    # atomikus csere: egy olvasó (a tick ExecCondition-je, a reconcile) sosem lát üres / félkész fájlt
    tmp = root / f".{agent}.{os.getpid()}.tmp"
    try:
        tmp.write_text(text)
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)
    if own:
        _OWNED[agent] = text
    else:
        _OWNED.pop(agent, None)
    return p


def unlock(agent: str) -> None:
    """Kézi feloldás (`fleet unlock`): bármilyen zárat töröl."""
    _check_name(agent)
    _OWNED.pop(agent, None)
    (_root() / agent).unlink(missing_ok=True)


def content(agent: str) -> str | None:
    """A zárfájl mostani tartalma (None: nincs / nem olvasható)."""
    try:
        return (_root() / agent).read_text().strip() if _AGENT_NAME.match(agent) else None
    except OSError:
        return None


def release_own(agent: str, token: str | None = None) -> bool:
    """Csak a SAJÁT zárunkat törli: ha közben egy ember (vagy más) új zárat tett rá, az marad.
    `token` hiányában az ebben a processzben vett zárunk jele (`_OWNED`)."""
    _check_name(agent)
    mine = token if token is not None else _OWNED.get(agent)
    _OWNED.pop(agent, None)
    if mine is None or content(agent) != mine:
        return False
    (_root() / agent).unlink(missing_ok=True)
    return True


def is_locked(agent: str) -> bool:
    """False on ANY read problem — a bad name, a permission error, a garbage
    file. Supervision loops call this; they must never abort on the lock."""
    if not _AGENT_NAME.match(agent):
        return False
    p = _root() / agent
    try:
        raw = p.read_text().strip()
        expires = float(raw)
    except (OSError, ValueError):
        return False
    if _OWNED.get(agent) == raw and time.time() < expires:
        return False   # a saját, még élő zárunk (lejárt vagy átírt zárra a kerülőút nem él)
    if time.time() >= expires:
        try:
            p.unlink(missing_ok=True)   # self-clean: expired lock must not linger
        except OSError:
            pass
        return False
    return True
