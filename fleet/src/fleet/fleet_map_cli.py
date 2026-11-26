"""`fleet map validate`: olvas, validál, kiír. Kilépés: 0 nincs hiba · 1 van · 2 nincs/olvashatatlan fájl."""
from __future__ import annotations
import json

from fleet import fleet_map, registry, registry_dir


def cmd_map(a) -> int:
    d = registry_dir()
    try:
        fmap = fleet_map.load(d)
    except (OSError, ValueError) as e:
        print(json.dumps({"schema": 1, "error": str(e)}) if a.json else f"fleet: {e}")
        return 2
    findings = fleet_map.validate(fmap, registry.load_agents(d / "agents.json"))
    errors = [f for f in findings if f.severity == "error"]
    if a.json:
        print(json.dumps({"schema": 1, "ok": not errors, "findings": [f.as_dict() for f in findings]},
                         ensure_ascii=False, indent=1))
    else:
        for f in findings:
            print(f"{'HIBA' if f.severity == 'error' else 'FIGYELEM'} [{f.code}] {f.message}")
        print("fleet map: rendben" if not errors else f"fleet map: {len(errors)} hiba")
    return 1 if errors else 0
