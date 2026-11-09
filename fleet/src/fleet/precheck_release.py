"""`fleet precheck release`: a kiadó ágens olcsó, nem-LLM előellenőrzője.

Egy futás: 1 GitHub GraphQL-keresés (`gh api graphql`, a box belépésével — tokent itt nem
látunk), 1 todo `/changes` (+ az első futáskor 1 `/me`), a kiadó ágens állapotfájlja CSAK
olvasva. Kimenet: egy kis dict (`observe`), amit a kapu dönt el. A „mi a munka” definíció a
release_work-ben él. A GitHub 3 s, a todo 2 s timeouttal: a teljes futás ≤ 5 s.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

from fleet import release_work as rw
from fleet.precheck_todo import todo_events

GH_TIMEOUT_S = 3   # + a todo 2 s-a: a teljes futás ≤ 5 s
QUERY = ("query($q:String!){search(query:$q,type:ISSUE,first:100){issueCount nodes{... on PullRequest"
         "{number isDraft headRefOid reviewDecision repository{nameWithOwner}"
         " commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}}")


def _path(p: str, home: Path) -> Path:
    """`%h` és `~` a megadott home-ra (nem a környezetre: a unit és a teszt ugyanazt látja)."""
    s = str(p).replace("%h", str(home))
    return home / s[2:] if s.startswith("~/") else Path(s)


def repos(rcfg: dict, home: Path) -> list[str]:
    """A kezelt repók slugjai: `repos` lista, vagy a kiadó ágens saját `repos.json`-ja (csak a slug)."""
    if rcfg.get("repos"):
        return sorted({str(r).lower() for r in rcfg["repos"]})
    doc = json.loads(_path(rcfg["repos_file"], home).read_text())
    return sorted({str(r["slug"]).lower() for r in doc.get("repos", []) if r.get("slug")})


def search_query(slugs: list[str]) -> str:
    return "is:pr is:open draft:false label:release:queue " + " ".join(f"repo:{s}" for s in slugs)


def github_prs(slugs: list[str], run=subprocess.run) -> list[dict]:
    """EGY hívás. Hiba → RuntimeError (a hívó a hálózati-hiba szabályt alkalmazza)."""
    r = run(["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"q={search_query(slugs)}"],
            capture_output=True, text=True, timeout=GH_TIMEOUT_S)
    if r.returncode:
        raise RuntimeError(f"github: gh kód {r.returncode}")
    doc = json.loads(r.stdout)
    if doc.get("errors"):   # 200-as válasz részleges adattal: nem teljes kép, nem döntök belőle
        raise RuntimeError(f"github: GraphQL-hiba ({str(doc['errors'])[:100]})")
    s = doc["data"]["search"]
    if int(s.get("issueCount") or 0) > 100:
        raise RuntimeError("github: több mint 100 sorban álló PR — a keresés csonka, nem döntök belőle")
    return s.get("nodes") or []


def observe(cfg: dict, gate: dict, *, now: float, last_tick_at: float | None, home: Path,
            run=subprocess.run, opener=urllib.request.urlopen) -> dict:
    """A megfigyelés: aktivitás, beküldési okok, a commit (mit léptet egy sikeres beküldés),
    a lease-foglaltság és a hibák. Nem dob: a hiba az `error` mezőbe kerül."""
    rc = cfg.get("release") or {}
    out = {"activity": False, "reasons": [], "error": None, "busy": None, "commit": {}}
    horizon = cfg.get("idle_s") or rw.APPROVAL_TTL_H * 3600
    try:
        state = json.loads(_path(rc["state_file"], home).read_text()) if rc.get("state_file") else {}
    except (OSError, ValueError):
        state = {}
    live, expiring = rw.approvals(state, now, horizon)
    out["activity"] |= live > 0 or bool(expiring)
    fresh = sorted(set(expiring) - set(gate.get("exp_seen") or []))
    out["reasons"] += [f"lejáró 👍-jegy: {k.split('@', 1)[0]}" for k in fresh]
    out["commit"]["exp_seen"] = expiring   # egy kérdésre egyszer; a már nem lejárók kiesnek
    if rw.lease_held(state, now, int(cfg.get("lease_ttl_min", 25))):
        out["busy"] = "a kiadó ágens lease-e él (egy kör fut)"
    errors = []
    try:
        fps = rw.fingerprints(github_prs(repos(rc, home), run))
        q = rw.queue_reasons(fps, gate.get("seen") or [])
        out["activity"] |= bool(fps) or bool(q)
        out["reasons"] += q
        out["commit"]["seen"] = fps
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as e:
        errors.append(f"github: {type(e).__name__}: {str(e)[:120]}")
    if rc.get("todo_handle"):
        try:
            seq = gate.get("todo_seq")
            t = todo_events(rc["todo_handle"], None if seq is None else int(seq), gate.get("todo_me"), home, opener)
            out["activity"] |= bool(t["events"])
            out["reasons"] += [f"todo-esemény: {len(t['events'])} db"] if t["events"] else []
            out["commit"].update(todo_seq=t["last_seq"], todo_me=t["me"])
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            errors.append(f"todo: {type(e).__name__}: {str(e)[:120]}")
    d = rw.daily_due(cfg.get("daily_at") or [], cfg["tz"], last_tick_at, now)
    out["reasons"] += [f"napi kör esedékes ({d})"] if d else []
    out["error"] = "; ".join(errors) or None
    return out
