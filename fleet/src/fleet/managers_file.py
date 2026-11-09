"""flotta-menedzser: a flotta-menedzserek hozzárendelése — egy verziózott fájl (fleet-ops `fleet/managers.json`).

    path() -> Path                    FLEET_MANAGERS, különben a registry mellett: <registry>/../managers.json
    load(p) -> dict                   beolvas + validate; hibánál ManagersError (a problémák listájával)
    validate(doc) -> (norm, problémák) ugyanaz a szabály, mint a Workerben (PUT /managers)
    chain(managers, agent, box) -> [m] előnézet: lefedő hozzárendelések sorrendben, alkalmasság nélkül

Alak: {"schema": 1, "version": N, "fleet": "default", "managers": [{"handle", "agent"?, "scope", "rank"}]}.
Hatókör: `*`, `agent:<név>` vagy `box:<név>`. Sorrend: agent > box > *, azon belül rang, döntetlennél
handle; egy handle csak egyszer (a legjobb helyén). Az elérést és az alkalmasságot (néma, piros
javító-próba) csak a Worker tudja: ez az előnézet azokat nem szűri.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_MANAGERS = 50
_PREC = {"agent": 0, "box": 1, "*": 2}


class ManagersError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def path() -> Path:
    env = os.environ.get("FLEET_MANAGERS", "").strip()
    if env:
        return Path(env).expanduser()
    from fleet import registry_dir
    return registry_dir().parent / "managers.json"


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _scope_ok(s) -> bool:
    if s == "*":
        return True
    if not isinstance(s, str) or ":" not in s:
        return False
    kind, name = s.split(":", 1)
    return kind in ("agent", "box") and bool(NAME_RE.match(name))


def validate(doc) -> tuple[dict, list[str]]:
    if not isinstance(doc, dict):
        return {}, ["a managers.json gyökere objektum legyen"]
    p: list[str] = []
    if doc.get("schema") != 1:
        p.append("schema: 1 kell")
    ver = doc.get("version")
    if not _int(ver) or ver < 1:
        p.append("version: pozitív egész kell (minden változásnál emeld)")
    fleet = doc.get("fleet", "default")
    if not isinstance(fleet, str) or not NAME_RE.match(fleet):
        p.append("fleet: flotta-azonosító kell")
    ms = doc.get("managers")
    if not isinstance(ms, list) or len(ms) > MAX_MANAGERS:
        return {}, p + [f"managers: lista kell, legfeljebb {MAX_MANAGERS} elem"]
    out, seen = [], set()
    for i, m in enumerate(ms):
        if not isinstance(m, dict):
            p.append(f"managers[{i}]: objektum kell")
            continue
        h, a, s, r = m.get("handle"), m.get("agent", m.get("handle")), m.get("scope"), m.get("rank")
        if not isinstance(h, str) or not NAME_RE.match(h):
            p.append(f"managers[{i}].handle: todo-handle kell")
        if not isinstance(a, str) or not NAME_RE.match(a):
            p.append(f"managers[{i}].agent: flottabeli ágensnév kell")
        if not _scope_ok(s):
            p.append(f"managers[{i}].scope: *, agent:<név> vagy box:<név> kell")
        if not _int(r) or r < 1:
            p.append(f"managers[{i}].rank: pozitív egész kell")
        if (h, s) in seen:
            p.append(f"managers[{i}]: ismétlődő (handle, scope): {h} {s}")
        seen.add((h, s))
        out.append({"handle": h, "agent": a, "scope": s, "rank": r})
    unknown = sorted(set(doc) - {"schema", "version", "fleet", "managers"})
    if unknown:
        p.append(f"ismeretlen mező: {', '.join(unknown)}")
    return {"version": ver, "fleet": fleet, "managers": out}, p


def load(p: Path | None = None) -> dict:
    p = p or path()
    try:
        doc = json.loads(Path(p).read_text())
    except OSError as e:
        raise ManagersError([f"{p}: nem olvasható ({type(e).__name__})"])
    except ValueError as e:
        raise ManagersError([f"{p}: hibás JSON ({e})"])
    norm, problems = validate(doc)
    if problems:
        raise ManagersError(problems)
    return norm


def chain(managers: list[dict], agent: str | None, box: str) -> list[dict]:
    def covers(m):
        s = m["scope"]
        return s == "*" or s == f"box:{box}" or (agent is not None and s == f"agent:{agent}")
    key = lambda m: (_PREC["*" if m["scope"] == "*" else m["scope"].split(":", 1)[0]], m["rank"], m["handle"])
    out, seen = [], set()
    for m in sorted(filter(covers, managers), key=key):
        if m["handle"] not in seen:
            seen.add(m["handle"])
            out.append(m)
    return out
