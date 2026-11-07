"""`fleet status <ágens>` — mit lát a flotta az ágens repójában (LG1 spec 3. pont).

Elemek: a mentat.json szándéka + a .mentat/local.json ténye ezen a gépen.
Szinergiák: agy+flotta (CLAUDE.md → AGENTS.md), motor+flotta (ki ütemez, és
az a timer tényleg aktív-e), flotta+admin (bekötve-e). A hiányzó elemet
kimondja („nincs jelen"), nem hallgat róla (4. szabály).
"""
from __future__ import annotations
from pathlib import Path

from fleet import mentat_manifest as mm
from fleet import synergy, tick_schedule
from fleet.txn import run_cmd


def _repo_for(agent: str) -> Path:
    from fleet.registry import get_agent
    e = get_agent(agent)
    if e is None:
        raise SystemExit(f"nincs ilyen ágens a registryben: {agent} (add meg: --repo)")
    return Path(e["workdir"].replace("%h", str(Path.home())))


def _active(unit: str, run) -> str:
    r = run(["systemctl", "--user", "is-active", unit])
    return (r.stdout or "").strip() or f"nem mérhető (kód {r.returncode})"


def status(agent: str, *, repo: Path | None = None, run=run_cmd, unit_dir: Path | None = None) -> dict:
    from fleet.install import UNIT_DIR
    repo = Path(repo) if repo else _repo_for(agent)
    doc, loc = mm.load(repo), mm.local(repo)
    out = {"agent": agent, "repo": str(repo), "elements": {}, "synergies": {}, "notes": []}
    if doc is None:
        out["notes"].append("nincs mentat.json — az elemek nem nyilvántartottak")
    elif not mm.schema_ok(doc):
        out["notes"].append(f"a mentat.json sémája ({doc.get('schema')}) újabb az ismertnél — csak diagnosztika")
    comps = (doc or {}).get("components") or {}
    inst = loc.get("installed") or {}
    for el in mm.ELEMS:
        out["elements"][el] = (f"jelen, telepítve: {inst.get(el) or '?'}" if isinstance(comps.get(el), dict)
                               else "nincs jelen")
    fl = loc.get("fleet") or {}
    if fl:
        out["notes"].append(f"flotta-tény: agent_id={fl.get('agent_id')} host={fl.get('host') or '?'}")
    b = synergy.claude_md_loads_agents(repo)
    out["synergies"]["agy+flotta"] = ("nincs AGENTS.md" if b is None else
                                      "a CLAUDE.md betölti az AGENTS.md-t" if b else
                                      "HIBA: a CLAUDE.md NEM tölti be az AGENTS.md-t (`fleet join --fix-claude-md`)")
    if isinstance(comps.get("engine"), dict):
        owner = comps["engine"].get("schedule_owner") or "engine"
        if owner == "fleet":
            t = f"{tick_schedule.tick_unit(agent)}.timer"
            out["synergies"]["motor+flotta"] = f"ütemezés: flotta ({t}: {_active(t, run)})"
        else:
            engines = tick_schedule.find_engine_timers(Path(unit_dir or UNIT_DIR), repo)
            names = ", ".join(f"{x.name}: {_active(x.name, run)}" for x, _ in engines) or "nincs motor-timer ezen a gépen"
            out["synergies"]["motor+flotta"] = f"ütemezés: motor ({names}) — `fleet join` átveszi"
    else:
        out["synergies"]["motor+flotta"] = "motor nincs jelen"
    from fleet.budget import line_for
    over = line_for(agent)
    if over:
        out["health"] = "unhealthy"
        out["problems"] = [over]
    out["synergies"]["flotta+admin"] = ("admin jelen; a fleet plugin (FP1) még nincs kész"
                                        if isinstance(comps.get("admin"), dict) else "admin: nincs bekötve")
    return out


def format_status(r: dict) -> str:
    lines = [f"{r['agent']} — {r['repo']}", "  elemek:"]
    lines += [f"    {k:7} {v}" for k, v in r["elements"].items()]
    lines.append("  szinergiák:")
    lines += [f"    {k:13} {v}" for k, v in r["synergies"].items()]
    lines += [f"  - {n}" for n in r["notes"]]
    lines += [f"  ! nem healthy: {p}" for p in r.get("problems", [])]
    return "\n".join(lines)
