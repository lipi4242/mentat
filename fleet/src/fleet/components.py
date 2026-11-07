"""Az agy és a motor felismerése a repóból — a `.claude/fleet.json`
`components.brain` / `components.reducer` mezőihez (06-flotta, 2. kör: a
mezők null maradtak, pedig az agy és a vendorolt motor ott volt).

Forrás: a mentat.json `components.brain` / `.engine`, különben maga a repó
(AGENTS.md, `anytime_engine/`). Az érték a verzió, ha kiolvasható, különben
a talált dolog neve; semmi sem található → None (nem találunk ki értéket).
"""
from __future__ import annotations
import re
from pathlib import Path

from fleet import mentat_manifest as mm

_VER = re.compile(r"""^__version__\s*=\s*['"]([^'"]+)['"]""", re.M)


def _s(v) -> str | None:
    return str(v) if isinstance(v, (str, int, float)) and str(v) else None


def _engine_version(repo: Path, path: str) -> str | None:
    d = repo / path
    try:
        if (d / "__init__.py").is_file():
            m = _VER.search((d / "__init__.py").read_text())
            if m:
                return m.group(1)
        v = d / "VERSION"
        if v.is_file():
            return v.read_text().strip() or None
    except OSError:
        pass
    return None


def detect(repo: Path) -> dict:
    """{"brain": str|None, "reducer": str|None} a repóból."""
    repo = Path(repo)
    comps = (mm.load(repo) or {}).get("components") or {}
    brain = comps.get("brain") if isinstance(comps.get("brain"), dict) else {}
    engine = comps.get("engine") if isinstance(comps.get("engine"), dict) else {}
    b = _s(brain.get("version")) or (
        "AGENTS.md" if (repo / "AGENTS.md").is_file() else _s(brain.get("root")))
    epath = _s(engine.get("path")) or ("anytime_engine" if (repo / "anytime_engine").is_dir() else None)
    r = None
    if epath and (repo / epath).is_dir():
        r = _engine_version(repo, epath) or epath
    elif engine:
        r = _s(engine.get("version")) or _s(engine.get("path"))
    return {"brain": b, "reducer": r}
