"""`fleet map audit`: 0 nincs hiba · 1 van hiba · 2 nincs/olvashatatlan térkép."""
from __future__ import annotations
import json
from pathlib import Path

from fleet import audit, audit_todo, fleet_map, registry, registry_dir


def cmd_audit(a, sink: audit_todo.TodoSink | None = None) -> int:
    d = registry_dir()
    try:
        fmap = fleet_map.load(d)
    except (OSError, ValueError) as e:
        print(json.dumps({"schema": 1, "error": str(e)}) if a.json else f"fleet: {e}")
        return 2
    agents = registry.load_agents(d / "agents.json")
    units = audit.collect(fmap, agents, d, home=Path.home(), root=Path(a.root) if a.root else None, mac_home=a.mac_home)
    cache_file = audit.state_path(a.state)
    results, measured, new_cache = audit.run(units, {} if a.no_cache else audit.load_cache(cache_file))
    findings = [f for f, _ in results]
    errors = [f for f in findings if f.severity == "error"]
    if a.todo:
        sink = sink or audit_todo.MentatTodoSink(a.project or "fleet", a.pm or "")
        audit_todo.file_todos(findings, sink)
    if not a.no_cache:
        audit.save_cache(cache_file, new_cache)
    if a.json:
        print(json.dumps({"schema": 1, "ok": not errors, "measured_units": measured,
                          "findings": [dict(f.as_dict(), cached=c) for f, c in results]}, ensure_ascii=False, indent=1))
    else:
        for f, c in results:
            print(f"{ {'error': 'HIBA', 'warning': 'FIGYELEM'}.get(f.severity, 'INFO') } [{f.code}] {f.message}" + (" (gyorsítótárból)" if c else ""))
        print(f"fleet map audit: {len(errors)} hiba, {measured}/{len(units)} egység újramérve")
    return 1 if errors else 0
