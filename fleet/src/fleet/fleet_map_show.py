"""`fleet map show`: the fleet map as a table a person reads. Read only.

Per agent: role (main + extras; a custom role by its name), owner (the person its reporting
chain ends at), whom it reports to, box (the registry's `host`: the map schema has no box),
repos, and the responsibility on the line below. --json gives the same rows.
Exit: 0 shown · 2 no map or unreadable (the same as `validate`).
"""
from __future__ import annotations
import json

from fleet import fleet_map, registry, registry_dir

COLS = (("agent", "ÁGENS"), ("role", "SZEREP"), ("owner", "GAZDA"), ("reports_to", "JELENT"),
        ("box", "BOX"), ("repos", "REPÓK"))


def _role(r) -> str:
    return r["custom"] if isinstance(r, dict) else str(r)


def roles(e: dict) -> str:
    main = e.get("custom_role") if e.get("main_role") == "custom" else e.get("main_role")
    return " + ".join([str(main)] + [_role(r) for r in e.get("extra_roles") or []])


def owner(name: str, entries: dict) -> str:
    """The person at the end of the reporting chain; "?" when it does not end in one."""
    seen, cur = {name}, name
    while True:
        rt = (entries.get(cur) or {}).get("reports_to")
        if not isinstance(rt, str):
            return "?"
        if rt.startswith("human:"):
            return rt[6:].strip()
        if rt in seen or rt not in entries:
            return "?"
        seen.add(rt)
        cur = rt


def rows(fmap: dict, agents: list[dict]) -> list[dict]:
    hosts = {a["agent"]: a.get("host") for a in agents if isinstance(a, dict) and a.get("agent")}
    entries = fmap.get("agents") if isinstance(fmap.get("agents"), dict) else {}
    out = []
    for name, e in entries.items():
        e = e if isinstance(e, dict) else {}
        rt = e.get("reports_to") or "?"
        out.append({"agent": name, "role": roles(e), "owner": owner(name, entries),
                    "reports_to": rt[6:].strip() if rt.startswith("human:") else rt,
                    "box": hosts.get(name) or "—",
                    "repos": ", ".join(f"{r.get('repo')} ({r.get('mode')})" for r in e.get("repos") or []
                                       if isinstance(r, dict)),
                    "responsibility": e.get("responsibility") or ""})
    return out


def table(fmap: dict, rs: list[dict]) -> str:
    width = {k: max([len(h)] + [len(r[k]) for r in rs]) for k, h in COLS[:-1]}

    def line(cells: dict) -> str:
        return "  ".join(cells[k].ljust(width[k]) for k, _ in COLS[:-1]) + "  " + cells["repos"]
    out = [f"Flotta: gazda {fmap.get('owner', '?')} · flottamenedzser {fmap.get('manager', '?')} · {len(rs)} ágens",
           line(dict(COLS))]
    for r in rs:
        out += [line(r), f"    ↳ {r['responsibility']}"]
    return "\n".join(out)


def cmd_map_show(a) -> int:
    d = registry_dir()
    try:
        fmap = fleet_map.load(d)
    except (OSError, ValueError) as e:
        print(json.dumps({"schema": 1, "error": str(e)}) if a.json else f"fleet: {e}")
        return 2
    rs = rows(fmap, registry.load_agents(d / "agents.json"))
    if a.json:
        print(json.dumps({"schema": 1, "owner": fmap.get("owner"), "manager": fmap.get("manager"),
                          "agents": rs}, ensure_ascii=False, indent=1))
    else:
        print(table(fmap, rs))
    return 0
