"""The agent's change feed: GET /changes?for=<me>&since=<cursor>, and the cursor.

The cursor is the server's event `seq`. It lives beside the engine state
(data/state/todo-cursor.json), one entry per (todo API, handle): a seq means
nothing on another instance, so switching TODO_API starts that instance at 0
(events are read again, never skipped):

    {"schema": 1, "handles": {"<api> <handle>": {"acked": <seq>, "seen": <seq>}}}

    acked   everything up to here is handled; `changes` reads after it
    seen    the highest seq a `changes` run has shown (an ack may not pass it)

Reading never moves `acked`: only `changes --ack <seq>` does, after the agent
has handled the events up to that seq. So a crash means reading again, never
losing an event. Every read-modify-write holds an exclusive lock on
todo-cursor.lock, and the file is replaced atomically (tmp + fsync + rename).
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Iterator

from anytime_engine import config

from .api import Client, TodoApiError

PAGE = 100
MAX_EVENTS = 500


class CursorError(Exception):
    """The cursor file is unreadable, or an ack is not allowed."""


def path() -> Path:
    return config.state_path().parent / "todo-cursor.json"


@contextlib.contextmanager
def _locked() -> Iterator[dict[str, Any]]:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p.with_suffix(".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            doc = _read(p)
            yield doc
            _write(p, doc)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _read(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {"schema": 1, "handles": {}}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CursorError(f"{p} is unreadable ({e}); fix or remove it by hand") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("handles"), dict):
        raise CursorError(f"{p} is not a todo cursor; fix or remove it by hand")
    return doc


def _write(p: Path, doc: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".todo-cursor-", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def key(api: str, handle: str) -> str:
    """The instance (scheme://host/path, lower-cased host, no trailing slash) + the handle."""
    u = urllib.parse.urlsplit(api.strip())
    return f"{u.scheme.lower()}://{u.netloc.lower()}{u.path.rstrip('/')} {handle}"


def acked(api: str, handle: str) -> int:
    entry = _read(path()).get("handles", {}).get(key(api, handle)) or {}
    return int(entry.get("acked") or 0)


def _page(c: Client, handle: str, since: int, limit: int) -> list[dict[str, Any]]:
    rows = c.get_json("/changes", {"for": handle, "since": since, "limit": limit})
    if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("seq"), int)
                                             for r in rows):
        raise TodoApiError("todo API answered /changes with something other than events")
    return rows


def read(c: Client, handle: str) -> dict[str, Any]:
    """The un-acked events (at most MAX_EVENTS), oldest first; records `seen`."""
    since = acked(c.api, handle)
    events: list[dict[str, Any]] = []
    more = True
    while more and len(events) < MAX_EVENTS:
        rows = _page(c, handle, since, PAGE)
        events += rows
        more = len(rows) == PAGE
        if rows:
            since = rows[-1]["seq"]
    events = events[:MAX_EVENTS]
    last = events[-1]["seq"] if events else acked(c.api, handle)
    with _locked() as doc:
        entry = doc["handles"].setdefault(key(c.api, handle), {"acked": 0, "seen": 0})
        entry["seen"] = max(int(entry.get("seen") or 0), last)
    return {"handle": handle, "acked": acked(c.api, handle), "events": events, "last_seq": last,
            "more": more}


def ack(api: str, handle: str, seq: int) -> int:
    """Move the cursor to seq: never backwards, never past what was shown."""
    with _locked() as doc:
        entry = doc["handles"].setdefault(key(api, handle), {"acked": 0, "seen": 0})
        cur, seen = int(entry.get("acked") or 0), int(entry.get("seen") or 0)
        if seq < cur:
            raise CursorError(f"ack {seq} is behind the cursor ({cur}); nothing changed")
        if seq > seen:
            raise CursorError(f"ack {seq} is past the last event shown ({seen}): "
                              "run `changes` and handle the events first")
        entry["acked"] = seq
    return seq


def pending(c: Client, handle: str) -> bool:
    """Is there at least one un-acked event? One small read, no file write."""
    return bool(_page(c, handle, acked(c.api, handle), 1))
