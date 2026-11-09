"""A tick-kapu todo-olvasása: `GET /changes` a kapu SAJÁT kurzorával — nem ackol, az ágens
`todo-cursor.json`-jához nem nyúl. A saját írásokat (`actor_id` = a token principalja, egyszer
lekérve a `/me`-ből, a kapu nyomában cache-elve) nem számolja. Token: `~/.config/todo/<handle>.token`,
cím: `TODO_API` vagy `~/.config/todo/env`; a token sosem kerül kimenetbe.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from fleet import release_work as rw

TIMEOUT_S = 2
USER_AGENT = "mentat-fleet-tick-gate/1"


def _todo_cfg(handle: str, home: Path) -> tuple[str, str] | None:
    cfg = home / ".config" / "todo"
    api = os.environ.get("TODO_API") or ""
    if not api and (cfg / "env").is_file():
        for ln in (cfg / "env").read_text().splitlines():
            if ln.startswith("TODO_API="):
                api = ln.split("=", 1)[1].strip().strip('"')
    tok = cfg / f"{handle}.token"
    if not api or not tok.is_file():
        return None
    return api.rstrip("/"), tok.read_text().strip()


def _get(api: str, token: str, path: str, opener=urllib.request.urlopen):
    req = urllib.request.Request(api + path, headers={"X-Mentat-Token": token, "User-Agent": USER_AGENT,
                                                      "Accept": "application/json"})
    with opener(req, timeout=TIMEOUT_S) as f:
        return json.load(f)


def todo_events(handle: str, since: int | None, me: str | None, home: Path, opener=urllib.request.urlopen) -> dict:
    """{events, last_seq, me}. A kapu SAJÁT kurzorral olvas, nem ackol (az ágens kurzorát nem mozdítja)."""
    c = _todo_cfg(handle, home)
    if c is None:
        return {"events": [], "last_seq": since, "me": me, "skipped": "nincs todo-beállítás"}
    api, token = c
    if me is None:
        who = _get(api, token, "/me", opener)
        me = str(who["id"]) if isinstance(who, dict) and who.get("id") else None
    if since is None:
        # első futás: a kurzor a mostani végére áll, ébresztés nélkül — különben a teljes múlt
        # (mérve: 23+ régi esemény) egy hamis ébresztés lenne a telepítéskor
        last = 0
        for _ in range(BASELINE_PAGES):
            rows = _changes(api, token, handle, last, 500, opener)
            last = max([last, *_seqs(rows)])
            if len(rows) < 500:
                break
        return {"events": [], "last_seq": last, "me": me, "baseline": True}
    rows = _changes(api, token, handle, int(since), 50, opener)
    return {"events": rw.foreign(rows, me), "last_seq": max([int(since), *_seqs(rows)]), "me": me}


BASELINE_PAGES = 5


def _changes(api, token, handle, since, limit, opener) -> list:
    q = urllib.parse.urlencode({"for": handle, "since": since, "limit": limit})
    rows = _get(api, token, "/changes?" + q, opener)
    if not isinstance(rows, list):
        raise RuntimeError("todo: a /changes nem lista")
    return rows


def _seqs(rows: list) -> list[int]:
    return [r["seq"] for r in rows if isinstance(r, dict) and isinstance(r.get("seq"), int)]
