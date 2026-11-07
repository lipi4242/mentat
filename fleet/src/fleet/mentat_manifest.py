"""mentat.json + .mentat/local.json olvasása és írása (LG1 spec, 2. szabály).

VENDOROLT, MINIMÁLIS VÁLTOZAT. A kanonikus `mentat_manifest.py` a
agyban él (reference/manifest/); amíg a flotta nem azt hívja, ez a
példány tartja be a spec szabályait, amire a flotta támaszkodik:

  1. kulcs-gazdák — a hívó csak a saját elemének szekcióját írja;
  2. írás zárral — kizárólagos `fcntl.flock` a `.mentat/lock`-on a teljes
     beolvasás → saját kulcs összefésülése (ismeretlen mezők megmaradnak) →
     tmp + rename köré;
  6. ismeretlen (nagyobb) `schema` → csak olvasás, írás nincs;
  7. ismeretlen kulcs tűrt.

Csere a kanonikusra: ugyanaz az API (`load`, `local`, `present`, `update`).
"""
from __future__ import annotations
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

KNOWN_SCHEMA = 1
ELEMS = ("brain", "engine", "fleet", "admin")


class SchemaTooNew(RuntimeError):
    """A fájl sémája újabb az ismertnél: csak diagnosztika (6. szabály)."""


def _read(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text())
        return d if isinstance(d, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load(root: Path) -> dict | None:
    """A commitolt mentat.json, vagy None, ha nincs / nem olvasható."""
    return _read(Path(root) / "mentat.json")


def local(root: Path) -> dict:
    return _read(Path(root) / ".mentat" / "local.json") or {}


def present(root: Path, elem: str) -> bool:
    """Hiányzó elem = nincs jelen (4. szabály)."""
    m = load(root) or {}
    return isinstance((m.get("components") or {}).get(elem), dict)


def schema_ok(doc: dict | None) -> bool:
    return doc is None or int(doc.get("schema") or 0) <= KNOWN_SCHEMA


@contextmanager
def _locked(root: Path):
    d = Path(root) / ".mentat"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "lock").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def update(root: Path, elem: str, section: str, data) -> None:
    """Az `elem` saját szekciójának összefésülése, zár alatt.

    section:
      "components" → mentat.json `components.<elem>` (dict, összefésülve)
      "installed"  → local.json `installed.<elem>` (verzió-string)
      "local"      → local.json `<elem>` (dict, összefésülve)
    """
    if elem not in ELEMS:
        raise ValueError(f"ismeretlen elem: {elem}")
    root = Path(root)
    with _locked(root):
        if section == "components":
            p = root / "mentat.json"
            doc = _read(p)
            if doc is None:
                raise FileNotFoundError(f"nincs mentat.json: {p} (az agy telepítője hozza létre)")
        else:
            p = root / ".mentat" / "local.json"
            doc = _read(p) or {"schema": KNOWN_SCHEMA}
        if not schema_ok(doc):
            raise SchemaTooNew(f"{p.name}: schema {doc.get('schema')} > {KNOWN_SCHEMA} — csak diagnosztika")
        if section == "installed":
            doc.setdefault("installed", {})[elem] = data
        else:
            parent = doc.setdefault("components", {}) if section == "components" else doc
            cur = parent.get(elem) if isinstance(parent.get(elem), dict) else {}
            cur.update(data)
            parent[elem] = cur
        _write(p, doc)
