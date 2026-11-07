"""A `fleet join` mentat.json-része (LG1 spec 3. pont + 5. szabály).

Ha a repóban van mentat.json:
  * `components.fleet` (szándék) a mentat.json-ba, `fleet` + `installed.fleet`
    (tény ezen a gépen) a `.mentat/local.json`-ba — zárral, csak a saját kulcs;
  * agy + flotta: a CLAUDE.md betölti-e az AGENTS.md-t (figyelmeztet, kérésre javít);
  * motor + flotta: ha a motor jelen van, a flotta átveszi a tick ütemezését
    (`schedule_owner: fleet`) — ez az egyetlen más elem kulcsa, amit a flotta
    ír, és csak mert az 5. szabály kifejezetten így rendeli.

Nincs mentat.json → a flotta önállóan csatlakozik (csak `.claude/fleet.json`);
ismeretlen (újabb) séma → csak diagnosztika, semmit nem ír (6. szabály).
"""
from __future__ import annotations
from pathlib import Path

from fleet import __version__, RegistryNotConfigured
from fleet import mentat_manifest as mm
from fleet import synergy, tick_schedule
from fleet.txn import Txn


def _host() -> str | None:
    from fleet.registry import local_host
    try:
        return local_host()
    except (RegistryNotConfigured, OSError):
        return None


def join_mentat(t: Txn, repo: Path, *, agent: str, fix_claude_md: bool = False,
                unit_dir: Path | None = None, host: str | None = None, run=None) -> list[str]:
    repo = Path(repo)
    doc = mm.load(repo)
    if doc is None:
        return ["mentat.json nincs: a flotta önállóan csatlakozott (.claude/fleet.json)"]
    if not mm.schema_ok(doc):
        return [f"FIGYELEM: a mentat.json sémája ({doc.get('schema')}) újabb az ismertnél "
                f"({mm.KNOWN_SCHEMA}) — csak diagnosztika, a flotta nem írja (frissítsd a Mentatot)"]
    notes: list[str] = []
    claude_md = repo / "CLAUDE.md"
    t.guard(claude_md)
    notes += synergy.check_brain(repo, fix=fix_claude_md)
    if run is not None:
        notes += synergy.gitignore_note(repo, run)
    for p in (repo / "mentat.json", repo / ".mentat" / "local.json"):
        t.guard(p)
    if mm.present(repo, "engine"):
        from fleet.install import UNIT_DIR
        engine = (doc.get("components") or {}).get("engine") or {}
        took = tick_schedule.take_over(t, agent=agent, repo=repo, engine=engine,
                                       unit_dir=Path(unit_dir or UNIT_DIR))
        notes += took
        if not any("nincs systemd" in n for n in took):
            mm.update(repo, "engine", "components", {"schedule_owner": "fleet"})
    else:
        notes.append("motor: nincs jelen — nincs átvehető ütemezés")
    mm.update(repo, "fleet", "components", {})
    local = {"agent_id": agent}
    h = host if host is not None else _host()
    if h:
        local["host"] = h
    mm.update(repo, "fleet", "local", local)
    mm.update(repo, "fleet", "installed", __version__)
    return notes
