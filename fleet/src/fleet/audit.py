"""`fleet map audit`: a determinisztikus karbantartási kör. Egységekre (térkép, ágens-repó, gyökér,
szülőmappák) bontja a méréseket; minden egységnek ujjlenyomata van, a mérés (thunk) csak akkor fut, ha az
ujjlenyomat eltér a cache-eltől. A cache a legutóbbi leleteket is őrzi: a változatlan egység leletei
újrajátszódnak (`cached`), semmi nem tűnik el néma zöldként. Csak olvas."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from fleet import audit_blocks, audit_scope, fleet_map
from fleet.fleet_map import Finding


def _fp(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def local_repo(agent: dict, home: Path) -> Path | None:
    wd = str(agent.get("workdir") or "")
    if not wd:
        return None
    p = Path(wd.replace("%h", str(home)).replace("~", str(home), 1) if wd.startswith(("%h", "~")) else wd)
    return p if p.is_dir() else None


def collect(fmap: dict, agents: list[dict], reg: Path, *, home: Path, root: Path | None = None,
            mac_home: bool = False) -> dict[str, tuple[str, Callable[[], list[Finding]]]]:
    units: dict[str, tuple[str, Callable[[], list[Finding]]]] = {}
    mapfp = _fp(json.dumps(fmap, sort_keys=True), json.dumps(agents, sort_keys=True))
    units["map"] = (mapfp, lambda: fleet_map.validate(fmap, agents))
    by_name = {a["agent"]: a for a in agents if isinstance(a, dict) and a.get("agent")}
    skip = {root.resolve()} if root else set()
    entries = fmap.get("agents") if isinstance(fmap.get("agents"), dict) else {}
    for name in sorted(entries):
        repo = local_repo(by_name[name], home) if name in by_name else None
        if repo is None:
            units[f"agent:{name}"] = ("absent", lambda n=name: [Finding(
                "not-measurable", f"{n}: nem mérhető itt (nincs helyi munkakönyvtár)", severity="info", agent=n, subject="workdir")])
            continue
        fp = _fp(_read(repo / "AGENTS.md"), mapfp, str(reg))
        units[f"agent:{name}"] = (fp, lambda n=name, r=repo: audit_blocks.check_repo(n, r, fmap, reg, Finding))
        if mac_home:
            near = sorted(str(p) for q in repo.resolve().parents for p in (q / "CLAUDE.md", q / ".claude" / "rules") if p.exists())
            units[f"parents:{name}"] = (_fp(*near), lambda r=repo: audit_scope.check_parents(r, home, skip, Finding))
    if root is not None:
        rules = sorted(str(p) for p in (root / ".claude" / "rules").rglob("*")) if (root / ".claude" / "rules").is_dir() else []
        units["root"] = (_fp(_read(root / "CLAUDE.md"), *rules, mapfp), lambda: audit_scope.check_root(root, fmap, Finding))
    return units


def state_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "fleet" / "map-audit.json"


def load_cache(path: Path) -> dict:
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def run(units: dict, cache: dict) -> tuple[list[tuple[Finding, bool]], int, dict]:
    """(lelet, cached) lista, a ténylegesen mért egységek száma és az új cache."""
    out, measured, fresh = [], 0, {}
    for key in sorted(units):
        fp, measure = units[key]
        old = cache.get(key)
        if isinstance(old, dict) and old.get("fp") == fp:
            found, cached = [Finding(**d) for d in old.get("findings", [])], True
        else:
            found, cached, measured = measure(), False, measured + 1
        fresh[key] = {"fp": fp, "findings": [f.as_dict() for f in found]}
        out += [(f, cached) for f in found]
    return out, measured, fresh


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    os.replace(tmp, path)
