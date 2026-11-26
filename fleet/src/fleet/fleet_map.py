"""A flottatérkép (`fleet-map.json`) beolvasása és validálása. Tiszta függvények,
semmit nem írnak. Egy hiba = egy `Finding`, kóddal és olvasható üzenettel.

A fájl a registry könyvtárában él, az `agents.json` mellett. A render és a
blokk-írás nem ennek a modulnak a dolga.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from fleet.fleet_map_graph import check_reports, check_repos
from fleet.fleet_map_schema import check_agent, is_name
from fleet.registry import is_dormant

FILENAME = "fleet-map.json"


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    severity: str = "error"  # "error" | "warning"
    agent: str | None = None
    subject: str = ""  # a lelet tárgya (út, fájl): a stabil kulcs része

    def as_dict(self) -> dict:
        return asdict(self)


def load(directory: Path) -> dict:
    """A térkép a registry-könyvtárból. Hiányzó/olvashatatlan fájl: OSError,
    nem JSON-objektum: ValueError — nem üres térkép (a mérés hibája nem adat)."""
    text = (Path(directory) / FILENAME).read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{FILENAME}: érvénytelen JSON ({e})") from e
    if not isinstance(doc, dict):
        raise ValueError(f"{FILENAME}: a gyökér nem objektum")
    return doc


def validate(fmap: dict, agents: list[dict]) -> list[Finding]:
    """Minden szabály, egyszerre. `agents` az agents.json (normalizálva vagy nyersen)."""
    out: list[Finding] = []
    known = {a["agent"]: a for a in agents if isinstance(a, dict) and a.get("agent")}
    entries = fmap.get("agents")
    for field in ("owner", "manager"):
        if not is_name(fmap.get(field)):
            out.append(Finding("bad-field", f"{field}: kötelező, nem üres szöveg", agent=None))
    if not isinstance(entries, dict):
        out.append(Finding("bad-field", "agents: kötelező objektum (ágensnév → bejegyzés)"))
        entries = {}
    for name in entries:
        if name not in known:
            out.append(Finding("unknown-agent", f"{name}: nincs az agents.json-ban", agent=name))
    for name, a in known.items():
        if name in entries:
            continue
        if is_dormant(a):
            out.append(Finding("missing-dormant-agent", f"{name}: alvó ágens, nincs a térképen",
                               severity="warning", agent=name))
        else:
            out.append(Finding("missing-active-agent", f"{name}: aktív ágens, hiányzik a térképről", agent=name))
    manager = fmap.get("manager")
    if is_name(manager) and manager not in known and manager not in entries:
        out.append(Finding("dangling-ref", f"manager: {manager} nem létező ágens"))
    valid: dict[str, dict] = {}
    for name, e in entries.items():
        out += check_agent(name, e, set(known) | set(entries), Finding)
        if isinstance(e, dict):
            valid[name] = e
    out += check_reports(valid, Finding)
    out += check_repos(valid, Finding)
    return out
