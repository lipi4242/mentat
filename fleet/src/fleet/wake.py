"""`fleet wake <ágens> --reason "…" [--pr URL]` — a kiadó (vagy bármely) ágens felébresztése a
backlogon át. Nincs új csatorna:

1. ELSŐDLEGES: todo-feladat az ágens principaljára a meglévő `mentat-todo task new`-val
   („PR #N: kapuzd/mergeld” + link). Az ágens alapból a saját labdáit figyeli: a #55
   híd-ébresztés ≤60 s alatt, a tick-kapu todo-ellenőrzése a következő tüzeléskor viszi be.
2. ELLENŐRZÉS: van-e principalja (todo-handle → /principals), és fut-e a hídja.
3. TARTALÉK: ha bármelyik hiányzik (nincs todo-példány, nincs principal, nincs/nem fut a
   híd), kiírja a peer-üzenet (`/rc`) szövegét — azt a hívó session küldi el.

Kilépési kód: 0 a feladat kész és a híd fut · 3 a tartalék kell (a szöveg a kimenetben) · 2 hiba.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fleet import precheck_todo as pt


def target_handle(entry: dict, home: Path) -> str:
    """A cél todo-handle-je: registry (`tick_gate.release.todo_handle` / `todo_handle`), a box
    `~/.config/todo/handles` sora, végül az ágens neve (a mentat-todo ugyanígy dönt)."""
    h = ((entry.get("tick_gate") or {}).get("release") or {}).get("todo_handle") or entry.get("todo_handle")
    if h:
        return str(h)
    f = home / ".config" / "todo" / "handles"
    try:
        for ln in f.read_text().splitlines():
            if ln.startswith(entry["agent"] + "="):
                return ln.split("=", 1)[1].strip()
    except OSError:
        pass
    return entry["agent"]


def my_handle(home: Path) -> str | None:
    if os.environ.get("TODO_HANDLE"):
        return os.environ["TODO_HANDLE"]
    a = os.environ.get("FLEET_AGENT")
    return target_handle({"agent": a}, home) if a else None


def principal_id(handle: str, me: str | None, home: Path, opener=None) -> str | None:
    """A cél principalja a todo-példányon (a hívó tokenjével olvasva); None: nincs / nem elérhető."""
    c = pt._todo_cfg(me, home) if me else None
    if c is None:
        return None
    try:
        rows = pt._get(*c, "/principals", **({"opener": opener} if opener else {}))
    except (OSError, ValueError):
        return None
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("handle") == handle:
            return str(r.get("id"))
    return None


def bridge_state(entry: dict, run=subprocess.run) -> str:
    """'fut' | 'nem fut' | 'nincs' | 'ismeretlen' (másik boxon nem mérhető innen)."""
    unit = (entry.get("bridge") or {}).get("unit")
    if not unit:
        return "nincs"
    from fleet.registry import host_matches, local_host
    if not host_matches(entry, local_host() or ""):
        return "ismeretlen"
    try:
        r = run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return "ismeretlen"
    return "fut" if r.stdout.strip() == "active" else "nem fut"


def peer_text(entry: dict, reason: str, url: str | None) -> str:
    return f"/rc {entry.get('rc_name') or entry['agent']} — {reason}" + (f" ({url})" if url else "")


def wake(entry: dict, reason: str, url: str | None = None, *, home: Path | None = None,
         run=subprocess.run, principal=principal_id, bridge=bridge_state) -> tuple[int, dict]:
    home = home or Path.home()
    handle = target_handle(entry, home)
    out = {"agent": entry["agent"], "handle": handle, "task": None, "bridge": bridge(entry, run), "fallback": None}
    pid = principal(handle, my_handle(home), home)
    if pid:
        title = f"{reason}"[:200]
        cmd = ["mentat-todo", "task", "new", "--title", title, "--assignee", pid,
               "--description", (f"{url}\n\n" if url else "") + "fleet wake: a kiadó ágens felébresztése."]
        try:
            r = run(cmd, capture_output=True, text=True, timeout=20)
            out["task"] = (json.loads(r.stdout) or {}).get("id") if r.returncode == 0 else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            out["task"] = None
    if out["task"] and out["bridge"] in ("fut", "ismeretlen"):
        return 0, out
    why = ("nincs todo-principal / todo-példány" if not pid else
           "a feladat nem jött létre" if not out["task"] else f"a híd: {out['bridge']}")
    out["fallback"] = {"why": why, "send": peer_text(entry, reason, url)}
    return 3, out
