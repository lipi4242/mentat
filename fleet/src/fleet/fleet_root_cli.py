"""`fleet map render|check --root`: a gyökér-CLAUDE.md. Kilépés mint a fleet_place_cli-é."""
from __future__ import annotations
from pathlib import Path

from fleet import fleet_root
from fleet.fleet_place_cli import _load

FILE = "CLAUDE.md"


def render(a) -> int:
    try:
        fmap, errs = _load()
    except (OSError, ValueError) as e:
        print(f"fleet: {e}")
        return 2
    if errs:
        print(f"fleet: a térkép nem érvényes ({len(errs)} hiba); előbb: fleet map validate")
        return 1
    path = Path(a.repo) / FILE
    try:
        new = fleet_root.render(fmap)
        old = path.read_text(encoding="utf-8") if path.exists() else None
    except fleet_root.RootError as e:
        print(f"fleet: {e}")
        return 1
    except OSError as e:
        print(f"fleet: {e}")
        return 2
    if new != old:
        path.write_text(new, encoding="utf-8")
    print(f"{path}: fleet-root" + ("" if new != old else " — változatlan"))
    return 0


def check(a) -> int:
    path = Path(a.repo) / FILE
    try:
        fmap, _ = _load()
        want = fleet_root.source_hash(fmap)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
    except (OSError, ValueError) as e:
        print(f"fleet: {e}")
        return 2
    have = fleet_root.parse_hash(text)
    if have != want:
        print(f"fleet: {path}: {'nincs fleet-root blokk' if have is None else f'elavult gyökérfájl (hash {have} != {want})'}; fleet map render --root")
        return 1
    print(f"{path}: rendben")
    return 0
