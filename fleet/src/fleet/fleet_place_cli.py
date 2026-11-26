"""`fleet map render|check`. render: 0 kész · 1 hiba · 2 nincs/olvashatatlan fájl.
check: 0 egyezik · 1 eltér/nincs blokk · 2 nincs/olvashatatlan fájl."""
from __future__ import annotations
from pathlib import Path

from fleet import fleet_map, fleet_place, fleet_place_file as pf, registry, registry_dir


def _load():
    d = registry_dir()
    fmap = fleet_map.load(d)
    errs = [f for f in fleet_map.validate(fmap, registry.load_agents(d / "agents.json")) if f.severity == "error"]
    return fmap, errs


def cmd_render(a) -> int:
    try:
        fmap, errs = _load()
    except (OSError, ValueError) as e:
        print(f"fleet: {e}")
        return 2
    if errs:
        print(f"fleet: a térkép nem érvényes ({len(errs)} hiba); előbb: fleet map validate")
        return 1
    if a.agent not in fmap["agents"]:
        print(f"fleet: {a.agent}: nincs a térképen")
        return 1
    path = Path(a.repo) / "AGENTS.md"
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        new = pf.place(text, pf.block(fmap, a.agent, a.mode))
    except fleet_place.TooBig as e:
        print(f"fleet: {e}")
        return 1
    except OSError as e:
        print(f"fleet: {e}")
        return 2
    if new != text:
        path.write_text(new, encoding="utf-8")
    print(f"{path}: fleet-place ({a.mode})" + ("" if new != text else " — változatlan"))
    return 0


def cmd_check(a) -> int:
    path = Path(a.repo) / "AGENTS.md"
    try:
        fmap, _ = _load()
        marker = pf.parse_marker(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"fleet: {e}")
        return 2
    agent = a.agent or (marker or {}).get("agent")
    if not marker or not agent:
        print(f"fleet: {path}: nincs fleet-place blokk")
        return 1
    if agent not in fmap["agents"] or marker.get("agent") != agent or marker.get("mode") not in fleet_place.MODES:
        print(f"fleet: {agent}: a blokk nem ehhez az ágenshez/módhoz tartozik vagy az ágens nincs a térképen")
        return 1
    try:
        want = fleet_place.source_hash(fmap, agent, marker["mode"])
    except (KeyError, TypeError):
        print(f"fleet: {agent}: a térkép bejegyzése hiányos")
        return 1
    if marker.get("hash") != want:
        print(f"fleet: {agent}: elavult fleet-place blokk (hash {marker.get('hash')} != {want}); fleet map render {agent}")
        return 1
    print(f"{agent}: rendben")
    return 0
