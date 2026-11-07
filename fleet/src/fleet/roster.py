"""`fleet roster` — ki van a flottában, és ezen a gépen mi fut belőle.

Két oszlop-család, szándékosan külön: a REGISTRY (kívánt állapot, host, név)
és a SZONDA (fut-e a processz itt). A harmadik forrást — a natív ListAgents
listát — a plugin `/fleet:roster` skillje adja hozzá, mert az csak egy
Claude-sessionből mérhető. A három nem keverhető: "nincs a listában", "nem
fut" és "nem mérhető" három különböző mondat.
"""
from __future__ import annotations

from fleet import signals
from fleet.registry import load_agents, local_host


def roster(host: str | None = None, probe: bool = True) -> list[dict]:
    host = host or local_host()
    procs = signals._proc_records() if probe else []
    rows = []
    for e in load_agents():
        here = e.get("host") in (None, host)
        row = {"agent": e["agent"], "status": e["status"], "host": e.get("host"),
               "rc_name": e["rc_name"], "model": e.get("model"),
               "supervision": e.get("supervision"), "role": (e.get("role") or e.get("description") or "")[:60],
               "telegram_bot": e.get("telegram_bot"), "here": here, "process": None}
        if probe and here and e.get("supervision") != "none":
            row["process"] = signals.process_signal(e, procs).state
        rows.append(row)
    return rows


def format_roster(rows: list[dict]) -> str:
    out = [f"{'ágens':24} {'kívánt':8} {'host':14} {'processz':9} {'rc-név':14} szerep"]
    for r in rows:
        proc = r["process"] or ("-" if not r["here"] else "?")
        out.append(f"{r['agent']:24} {r['status']:8} {str(r['host']):14} {proc:9} {r['rc_name']:14} {r['role']}")
    return "\n".join(out)
