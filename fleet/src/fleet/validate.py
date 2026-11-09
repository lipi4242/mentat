"""A registry konzisztenciája (`fleet validate`), függvényként is: a `fleet
setup` ugyanezt hívja, és csak a saját ágensének hibáin áll meg."""
from __future__ import annotations
from pathlib import Path

from fleet import registry as reg


def validate(rdir: Path) -> tuple[int, list[str]]:
    """(ágensek száma, problémák). Egy probléma `<ágens>: …` alakú, ha egy
    ágenshez tartozik."""
    from fleet import names
    from fleet.preflight import missing_fields
    boxes = {b["key"] for b in reg.load_boxes(rdir / "boxes.json")}
    from fleet.render import validate_for_render
    problems = []
    seen = set()
    rc_seen: dict[str, str] = {}
    if not (rdir / "agents.json").is_file():
        problems.append(f"nincs agents.json a registryben: {rdir}")
    for e in reg.load_agents(rdir / "agents.json"):
        a = e["agent"]
        if a in seen:
            problems.append(f"{a}: duplikált bejegyzés")
        seen.add(a)
        if e["rc_name"] in rc_seen and e.get("host") == rc_seen.get(e["rc_name"] + "@host"):
            problems.append(f"{a}: rc_name {e['rc_name']!r} ütközik ({rc_seen[e['rc_name']]}) ugyanazon a hoston")
        rc_seen[e["rc_name"]] = a; rc_seen[e["rc_name"] + "@host"] = e.get("host")
        if e["unit_source"] == "template":
            problems += [f"{a}: {f}" for f in validate_for_render(e)]
        from fleet import tick_gate   # tick-kapu: a tick-kapu mezői (preset, időpontok, tick_cmd)
        gate = tick_gate.config(e)
        if gate is not None:
            problems += [f"{a}: {f}" for f in tick_gate.problems(gate)]
        problems += [f"{a}: {f}" for f in names.name_findings(e)]
        problems += [f"{a}: hiányzó mező {f}" for f in missing_fields(e)]
        if e.get("host") and e["host"] not in boxes:
            problems.append(f"{a}: ismeretlen host {e['host']!r} (boxes.json)")
        if e["status"] not in reg.AGENT_STATUSES:
            problems.append(f"{a}: ismeretlen status {e['status']!r}")
        rb = e.get("runbook")
        # A runbook útvonala a registry könyvtárához VAGY az azt tartalmazó repó gyökeréhez
        # relatív (egy `<repo>/fleet` registry `fleet/runbooks/<x>.md`-vel is hivatkozhat).
        if rb and not any((base / rb).exists() for base in (rdir, rdir.parent)):
            problems.append(f"{a}: runbook hiányzik: {rb} (keresve: {rdir}, {rdir.parent})")
    return len(seen), problems
