"""`fleet doctor`: a fleet-place drift repónként, teendőként. Drift nélkül (vagy térkép / helyi repó nélkül) csend."""
from __future__ import annotations
from pathlib import Path

from fleet import RegistryNotConfigured, audit_blocks, fleet_map, registry_dir
from fleet.fleet_map import Finding

WHAT = {"block-missing": "nincs fleet-place blokk", "block-drift": "a blokk eltér a térképtől"}


def warnings_for(entry: dict) -> list:
    name = entry["agent"]
    repo = Path(str(entry.get("workdir") or "").replace("%h", str(Path.home())))
    if not entry.get("workdir") or not repo.is_dir():
        return []
    try:
        d = registry_dir()
        fmap = fleet_map.load(d)
    except (RegistryNotConfigured, OSError, ValueError):
        return []
    if not isinstance(fmap.get("agents"), dict) or name not in fmap["agents"]:
        return []
    try:
        found = audit_blocks.check_repo(name, repo, fmap, d, Finding)
    except (KeyError, TypeError, ValueError, OSError):
        return []
    codes = [f.code for f in found if f.code in WHAT]
    if not codes:
        return []
    return [f"fleet-place drift ({repo}): {WHAT[codes[0]]} — `fleet upgrade {repo} --pr`"]
