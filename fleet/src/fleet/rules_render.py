"""A `deliver` második renderelője: a `.claude/rules/fleet.md` és a manifest (rules_sha, verzió) frissítése.
A join/upgrade meglévő logikáját használja; a helyben módosított fájlt nem írja felül (Skip)."""
from __future__ import annotations
import datetime
import json
from pathlib import Path

from fleet import __version__, join, rules_state
from fleet.deliver import Skip


def render(work: Path, fmap: dict, agent: str) -> dict:
    st = rules_state.state(work, agent)
    if st is None:
        raise Skip("nincs .claude/fleet.json vagy .claude/rules/fleet.md — előbb `fleet join`")
    if not st["outdated"]:
        return {}
    if st["modified"]:
        raise Skip("helyi módosítás a fleet.md-ben — az új verziót nem írom felül; fésüld össze kézzel")
    m = join.read_manifest(work) or {}
    m.setdefault("components", {})["fleet"] = __version__
    m["rules_sha"] = st["want_sha"]
    m["updated"] = datetime.date.today().isoformat()
    return {rules_state.REL: st["new_text"], ".claude/fleet.json": json.dumps(m, indent=2, ensure_ascii=False) + "\n"}
